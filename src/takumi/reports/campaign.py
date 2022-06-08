from sqlalchemy import and_, func

from takumi.extensions import db


class CampaignReport:
    def __init__(self, campaign):
        self.campaign = campaign

    @property
    def insights(self):
        return self.campaign.insights_count

    @property
    def participating_influencer_count(self):
        from takumi.models import Influencer, Offer
        from takumi.models.offer import STATES as OFFER_STATES

        return (
            db.session.query(func.count(Influencer.id))
            .join(Offer)
            .filter(Offer.campaign_id == self.campaign.id, Offer.state == OFFER_STATES.ACCEPTED)
        ).scalar()

    @property
    def live_gig_count(self):
        from takumi.models import Gig, Offer

        return (
            db.session.query(func.count(Gig.id))
            .join(Offer)
            .filter(Offer.campaign_id == self.campaign.id, Gig.is_live)
        ).scalar()

    @property
    def live_media_count(self):
        from takumi.models import Gig, InstagramPost, InstagramStory, Media, Offer, StoryFrame

        gig_subq = (
            db.session.query(Gig.id)
            .join(Offer)
            .filter(Offer.campaign_id == self.campaign.id, Gig.is_live)
        ).subquery()

        story_frames_q = (
            db.session.query(StoryFrame.id)
            .join(InstagramStory)
            .filter(InstagramStory.gig_id.in_(gig_subq))
        )

        posts_subq = (
            db.session.query(InstagramPost.id).filter(InstagramPost.gig_id.in_(gig_subq))
        ).subquery()

        posts_asset_count_q = db.session.query(func.count(Media.id)).filter(
            and_(Media.owner_id.in_(posts_subq), Media.owner_type == "instagram_post")
        )

        return posts_asset_count_q.scalar() + story_frames_q.count()

    @property
    def accepted_followers(self):
        """The number of followers of all accepted influencers when they apply"""
        from takumi.models import Offer
        from takumi.models.offer import STATES as OFFER_STATES

        return (
            db.session.query(func.sum(Offer.followers_per_post)).filter(
                Offer.state == OFFER_STATES.ACCEPTED, Offer.campaign_id == self.campaign.id
            )
        ).scalar()

    @property
    def live_gig_followers(self):
        """The combined followers for every live gig"""
        from takumi.models import Gig, InstagramPost, InstagramStory, Offer

        gig_subq = (
            db.session.query(Gig.id)
            .join(Offer)
            .filter(Offer.campaign_id == self.campaign.id, Gig.is_live)
        ).subquery()

        stories = (
            db.session.query(func.sum(InstagramStory.followers)).filter(
                InstagramStory.gig_id.in_(gig_subq)
            )
        ).scalar() or 0

        posts = (
            db.session.query(func.sum(InstagramPost.followers)).filter(
                InstagramPost.gig_id.in_(gig_subq)
            )
        ).scalar() or 0

        return stories + posts
