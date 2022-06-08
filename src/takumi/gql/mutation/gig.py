from flask_login import current_user
from sentry_sdk import capture_exception

from core.facebook.instagram import InstagramError

from takumi import slack
from takumi.emails import ResubmitGigEmail
from takumi.extensions import instascrape
from takumi.facebook_account import unlink_on_permission_error
from takumi.gql import arguments, fields
from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.base import Mutation
from takumi.gql.utils import get_gig_or_404, get_influencer_or_404, get_post_or_404
from takumi.i18n import gettext as _
from takumi.i18n import locale_context
from takumi.ig.instascrape import NotFound
from takumi.models.gig import STATES as GIG_STATES
from takumi.models.influencer import FacebookPageDeactivated, MissingFacebookPage
from takumi.models.post import PostTypes
from takumi.notifications import NotificationClient
from takumi.roles import permissions, provide_advertiser_access_need
from takumi.services import (
    GigService,
    InstagramPostService,
    InstagramReelService,
    InstagramStoryService,
    OfferService,
    TiktokPostService,
)
from takumi.utils.instagram import parse_shortcode_from_url
from takumi.utils.tiktok import follow_redirects, parse_id_from_url
from takumi.validation.errors import MultipleErrorsError
from takumi.validation.media import ConditionsValidator


class MediaType(arguments.Enum):
    video = "video"
    image = "image"


class MediaInput(arguments.InputObjectType):
    type = MediaType(required=True)
    url = arguments.String(required=True)
    thumbnail = arguments.String()


class ReviewGig(Mutation):
    """Mark a gig as reviewed"""

    class Arguments:
        id = arguments.UUID(required=True, description="The id of the gig being reviewed")

    gig = fields.Field("Gig")

    @permissions.review_gig.require()
    def mutate(root, info, id, reviewer_id=None):
        gig = get_gig_or_404(id)

        if reviewer_id is None or not permissions.developer.can():
            reviewer_id = current_user.id

        with GigService(gig) as service:
            if gig.state == GIG_STATES.APPROVED:
                service.review_approved_gig(reviewer_id)
            else:
                service.review_gig(reviewer_id)

        return ReviewGig(gig=gig, ok=True)


class VerifyGig(Mutation):
    """Mark a gig as verified"""

    class Arguments:
        id = arguments.UUID(required=True, description="The id of the gig being verified")

    gig = fields.Field("Gig")

    @permissions.review_gig.require()
    def mutate(root, info, id, reviewer_id=None):
        gig = get_gig_or_404(id)

        if reviewer_id is None or not permissions.developer.can():
            reviewer_id = current_user.id

        with GigService(gig) as service:
            service.verify_gig(reviewer_id=reviewer_id)

        return VerifyGig(gig=gig, ok=True)


class ApproveGig(Mutation):
    class Arguments:
        id = arguments.UUID(required=True, description="The id of the gig being approved")

    gig = fields.Field("Gig")

    @permissions.public.require()
    def mutate(root, info, id, approver_id=None):
        gig = get_gig_or_404(id)

        if not permissions.developer.can():
            provide_advertiser_access_need(current_user, gig.post.campaign.advertiser_id)
            permissions.advertiser_member.test()

        if not gig.post.campaign.brand_safety:
            raise MutationException(
                "This campaign does not have a brand safety, so it cannot be approved"
            )

        with GigService(gig) as service:
            if approver_id is not None and permissions.developer.can():
                service.approve_gig(approver_id)
            else:
                service.approve_gig(current_user.id)

        return ApproveGig(gig=gig, ok=True)


class ReportGig(Mutation):
    """Report a gig"""

    class Arguments:
        id = arguments.UUID(required=True, description="The id of the gig being reported")
        reason = arguments.String(required=True, description="The report reason")

    gig = fields.Field("Gig")

    # TODO: Find a suitable solution to brand access level permission
    @permissions.report_gig.require()
    def mutate(root, info, id, reason):
        gig = get_gig_or_404(id)
        provide_advertiser_access_need(current_user, gig.offer.campaign.advertiser_id)
        permissions.advertiser_member.test()

        if gig.is_claimable:
            raise MutationException("Unable to report a gig that's claimable")

        with GigService(gig) as service:
            service.report_gig(reason=reason, reporter=current_user)

        return ReportGig(gig=gig, ok=True)


class RequestGigResubmission(Mutation):
    class Arguments:
        id = arguments.UUID(
            required=True, description="The id of the gig to request resubmission for"
        )
        send_email = arguments.Boolean(
            description="Whether to send an email to the influencer or not", default_value=True
        )
        reason = arguments.String(
            required=True, description='Reason for requesting resubmission, ie. "Off Brief"'
        )
        explanation = arguments.String(
            description="Further explanation for requesting resubmission"
        )

    gig = fields.Field("Gig")

    @permissions.request_gig_resubmission.require()
    def mutate(root, info, id, send_email, reason=None, explanation=None):
        gig = get_gig_or_404(id)

        with GigService(gig) as service:
            service.request_resubmission(reason=reason, explanation=explanation)
            if send_email:
                with locale_context(gig.offer.influencer.user.request_locale):
                    ResubmitGigEmail(
                        {
                            "reason": reason or "",
                            "explanation": explanation or "",
                            "campaign_name": gig.offer.campaign.name,
                        }
                    ).send(gig.offer.influencer.email)

        return RequestGigResubmission(gig=gig, ok=True)


class RejectGig(Mutation):
    class Arguments:
        id = arguments.UUID(required=True, description="The id of the gig being rejected")
        reason = arguments.String(
            required=True, description='Reason for requesting resubmission, ie. "Off Brief"'
        )

    gig = fields.Field("Gig")

    @permissions.reject_gig.require()
    def mutate(root, info, id, reason):
        gig = get_gig_or_404(id)

        with GigService(gig) as service:
            service.reject(reason=reason)

        if gig.offer.influencer.has_device:
            with locale_context(gig.offer.influencer.user.request_locale):
                client = NotificationClient.from_influencer(gig.offer.influencer)
                client.send_rejection(
                    _(
                        "Your post for %(advertiser)s was rejected",
                        advertiser=gig.post.campaign.advertiser.name,
                    ),
                    gig.post.campaign,
                )

        if gig.offer.has_all_gigs():
            with OfferService(gig.offer) as service:
                service.last_gig_submitted()

        return RejectGig(gig=gig, ok=True)


class DismissGigReport(Mutation):
    class Arguments:
        id = arguments.UUID(
            required=True, description="The id of the gig to dismiss the report for"
        )

    gig = fields.Field("Gig")

    @permissions.dismiss_gig_report.require()
    def mutate(root, info, id):
        gig = get_gig_or_404(id)

        with GigService(gig) as service:
            service.dismiss_report()

        return DismissGigReport(gig=gig, ok=True)


class RevertGigReport(Mutation):
    class Arguments:
        id = arguments.UUID(required=True, description="The id of the gig to revert the report for")

    gig = fields.Field("Gig")

    @permissions.campaign_manager.require()
    def mutate(root, info, id: str) -> "RevertGigReport":
        gig = get_gig_or_404(id)

        with GigService(gig) as service:
            service.revert_report()

        return RevertGigReport(gig=gig, ok=True)


class SetSkipInsights(Mutation):
    class Arguments:
        id = arguments.UUID(required=True, description="The id of the gig to set skip_insights for")
        skip_insights = arguments.Boolean(
            required=True, description="Whether to allow skipping insights or not"
        )

    gig = fields.Field("Gig")

    @permissions.manage_influencers.require()
    def mutate(root, info, id, skip_insights):
        gig = get_gig_or_404(id)

        with GigService(gig) as service:
            service.set_skip_insights(skip_insights)

        return SetSkipInsights(gig=gig, ok=True)


class SubmitMedia(Mutation):
    class Arguments:
        media = arguments.List(MediaInput, required=True, description="List of the media to submit")
        caption = arguments.String(
            required=True, description="The intended caption of the instagram post"
        )
        post_id = arguments.UUID(required=True, description="Post to submit gig into")
        influencer_id = arguments.UUID(description="Campaign manager only: Submit as a influencer")

    gig = fields.Field("Gig")

    @permissions.influencer.require()
    def mutate(root, info, media, caption, post_id, influencer_id=None):
        if influencer_id is not None and permissions.campaign_manager.can():
            # Support submitting for review for an individual influencer if user is a campaign manager
            influencer = get_influencer_or_404(influencer_id)
        else:
            influencer = current_user.influencer

        caption = caption.strip()

        post = get_post_or_404(post_id)
        offer = OfferService.get_for_influencer_in_campaign(influencer.id, post.campaign.id)

        if offer is None:
            raise MutationException("Offer not found when submitting gig")

        if post.post_type != PostTypes.story:
            validator = ConditionsValidator(post.conditions, post.start_first_hashtag)
            try:
                validator.validate(caption)
            except MultipleErrorsError:
                raise MutationException("Caption is invalid", errors=validator.errors)

        gig = GigService.get_by_offer_and_post(offer.id, post.id)
        if not gig:
            # Create the gig if it doesn't exist already
            gig = GigService.create(offer.id, post.id)

        if post.post_type == PostTypes.story and gig.instagram_story == None:
            InstagramStoryService.create(gig.id)

        media = [{k: v for k, v in m.items()} for m in media]
        with GigService(gig) as service:
            service.create_submission(caption, media)

        if not post.requires_review_before_posting:
            # Event posts skip normal reviewing and approving
            with GigService(gig) as service:
                service.skip_review_and_approval()

        slack.gig_submit(gig)

        return SubmitMedia(gig=gig, ok=True)


class UpdateLatestSubmissionCaption(Mutation):
    class Arguments:
        id = arguments.UUID(
            required=True,
            description="The id of the gig to update the latest submission caption for",
        )
        caption = arguments.String(required=True, description="The new caption")

    gig = fields.Field("Gig")

    @permissions.manage_influencers.require()
    def mutate(root, info, id, caption):
        gig = get_gig_or_404(id)

        with GigService(gig) as service:
            service.update_latest_submission_caption(caption)

        return UpdateLatestSubmissionCaption(ok=True, gig=gig)


class LinkGig(Mutation):
    class Arguments:
        id = arguments.UUID(required=True, description="The id of the gig being linked")
        shortcode = arguments.String(
            description=(
                "The instagram post shortcode or id, if not provided, "
                "we will try to automatically find the post"
            )
        )
        url = arguments.String(
            description="The instagram post url, if provided, will try to link to that post"
        )
        force = arguments.Boolean(
            description="Force link, ignoring all validation", default_value=False
        )

    gig = fields.Field("Gig")

    @staticmethod
    def _get_shortcode_from_gig(gig):
        try:
            influencer = gig.offer.influencer
            with unlink_on_permission_error(influencer.instagram_account.facebook_page):
                raw_media = influencer.instagram_api.get_post_by_caption(
                    gig.submission.caption, nocache=True
                )
                if raw_media:
                    shortcode = raw_media["shortcode"]
        except (
            MissingFacebookPage,
            InstagramError,
            FacebookPageDeactivated,
        ) as e:
            if isinstance(e, InstagramError):
                capture_exception()
            try:
                raw_media = instascrape.get_post_by_caption(
                    gig.offer.influencer.username, gig.submission.caption, nocache=True
                )
                if raw_media:
                    shortcode = raw_media["code"]
            except NotFound:
                raise MutationException("User not public on Instagram")
        if raw_media is None:
            raise MutationException("Post not found on Instagram")
        return shortcode

    @permissions.public.require()
    def mutate(root, info, id, shortcode=None, url=None, force=False):  # noqa: C901
        gig = get_gig_or_404(id)
        post = gig.post
        influencer = gig.offer.influencer

        if not permissions.link_gig.can() and gig.offer.influencer.user != current_user:
            raise MutationException(f"You don't have a permission to link <Gig: {id}>")

        if gig.post.post_type == PostTypes.youtube:
            raise MutationException("Not supported yet")

        if post.post_type == PostTypes.tiktok:
            if url is None:
                raise MutationException("Tiktok post url is missing!")

            tiktok_username = None
            if influencer.tiktok_account:
                tiktok_username = influencer.tiktok_account.username
            elif influencer.user.tiktok_username:
                tiktok_username = influencer.user.tiktok_username

            if tiktok_username is None:
                raise MutationException("Tiktok username missing")

            if "vm.tiktok.com" in url:
                url = follow_redirects(url)
            tiktok_id = parse_id_from_url(tiktok_username, url)
        elif url is not None:
            shortcode = parse_shortcode_from_url(url)
            if shortcode is None:
                raise MutationException(f"Invalid instagram post url: {url}")

        if post.post_type == PostTypes.story:
            instagram_story = gig.instagram_story
            if instagram_story is None:
                instagram_story = InstagramStoryService.create(gig.id)
            else:
                InstagramStoryService.download_story_frames(gig.offer.influencer_id)

            with InstagramStoryService(instagram_story) as service:
                service.mark_as_posted()

            with GigService(gig) as service:
                service.mark_as_posted(True)

            slack.gig_story_posted(gig)
        elif gig.post.post_type == PostTypes.reel:
            if gig.instagram_reel:
                with InstagramReelService(gig.instagram_reel) as service:
                    service.unlink_gig()
            InstagramReelService.create(gig.id, shortcode, url)

            with GigService(gig) as service:
                service.mark_as_posted(True)

        elif gig.post.post_type == PostTypes.tiktok:
            if tiktok_id is None:
                raise MutationException(f"Invalid Tiktok post url: {url}")
            if gig.tiktok_post:
                with TiktokPostService(gig.tiktok_post) as service:
                    service.unlink_gig()
            TiktokPostService.create(gig.id, tiktok_id, url)

            with GigService(gig) as service:
                service.mark_as_posted(True)

        else:
            if shortcode is None:
                shortcode = LinkGig._get_shortcode_from_gig(gig)

            if gig.instagram_post:
                with InstagramPostService(gig.instagram_post) as service:
                    service.unlink_gig()

            InstagramPostService.create(gig.id, shortcode)

        if gig.offer.has_all_gigs():
            with OfferService(gig.offer) as service:
                service.last_gig_submitted()

        return LinkGig(gig=gig, ok=True)


class MarkAsPosted(Mutation):
    class Arguments:
        id = arguments.UUID(required=True, description="The id of the gig to set is_posted for")
        is_posted = arguments.Boolean(required=True, description="Whether the gig is posted or not")

    gig = fields.Field("Gig")

    @permissions.manage_influencers.require()
    def mutate(root, info, id, is_posted):
        gig = get_gig_or_404(id)

        with GigService(gig) as service:
            service.mark_as_posted(is_posted)

        return MarkAsPosted(gig=gig, ok=True)


class MarkAsVerified(Mutation):
    class Arguments:
        id = arguments.UUID(required=True, description="The id of the gig to set is_verified for")
        is_verified = arguments.Boolean(
            required=True, description="Whether the gig is posted or not"
        )

    gig = fields.Field("Gig")

    @permissions.manage_influencers.require()
    def mutate(root, info, id, is_verified):
        gig = get_gig_or_404(id)

        with GigService(gig) as service:
            service.mark_as_verified(is_verified)

        return MarkAsVerified(gig=gig, ok=True)


class GigMutation:
    approve_gig = ApproveGig.Field()
    dismiss_gig_report = DismissGigReport.Field()
    link_gig = LinkGig.Field()
    mark_as_posted = MarkAsPosted.Field()
    mark_as_verified = MarkAsVerified.Field()
    reject_gig = RejectGig.Field()
    report_gig = ReportGig.Field()
    request_gig_resubmission = RequestGigResubmission.Field()
    revert_gig_report = RevertGigReport.Field()
    review_gig = ReviewGig.Field()
    set_skip_insights = SetSkipInsights.Field()
    submit_media = SubmitMedia.Field(description="Submit a media for review in a post")
    update_latest_submission_caption = UpdateLatestSubmissionCaption.Field()
    verify_gig = VerifyGig.Field()
