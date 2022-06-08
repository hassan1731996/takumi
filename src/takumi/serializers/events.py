import datetime as dt

from dateutil import parser as date_parser

from takumi.models import GigEvent, InfluencerEvent, OfferEvent


def parse_date(date):
    result = date_parser.parse(date)

    if result.tzinfo is None:
        result = result.replace(tzinfo=dt.timezone.utc)

    result = result.astimezone(dt.timezone.utc)

    return result.strftime("%B %d, %Y")


class HistorySerializer:
    def serialize(self, item):
        raise NotImplementedError


SYSTEM_USER = dict(
    id="6ed8aee7-6cdc-445e-9ddf-e204ead75828",
    full_name="System",
    profile_picture="https://s3-eu-west-1.amazonaws.com/takumi-static-assets/web/photoman_superhero__3__1024.png",
)


class InfluencerEventsSerializer(HistorySerializer):
    def serialize(self, event):
        influencer_event = InfluencerEvent.query.get(event.key)

        return {
            "created": event.created,
            "text": self._text(influencer_event),
            "type": event.type,
            "user": self._user(influencer_event),
        }

    def _text(self, event):
        if event.type == "comment":
            return event.event["comment"]

        if event.type == "disable":
            return event.event.get("reason", None)

        if event.type == "send-instagram-direct-message":
            return event.event.get("text", None)

        if event.type == "send-email":
            return event.event.get("body", None)

        if event.type == "signup":
            return "Influencer signed up"

        if event.type == "review":
            return "Influencer was reviewed by {} ({})".format(
                event.creator_user.full_name, event.creator_user.email
            )

        if event.type == "enable":
            return "Influencer was enabled by {} ({})".format(
                event.creator_user.full_name, event.creator_user.email
            )

        return ""

    def _user(self, event):
        if event.type == "signup":
            return event.influencer.user

        return event.creator_user or SYSTEM_USER


class InfluencerOffersSerializer(HistorySerializer):
    def serialize(self, event):
        offer_event = OfferEvent.query.get(event.key)

        return {
            "created": event.created,
            "text": self._text(offer_event),
            "type": offer_event.type,
            "user": self._user(offer_event),
        }

    def _user(self, event):
        if event.type == "send_push_notification" or event.type == "revoke":
            return event.creator_user or SYSTEM_USER

        return event.offer.influencer.user

    def _text(self, event):
        if event.type == "send_push_notification":
            full_name = (
                event.creator_user.full_name
                if event.creator_user is not None
                else SYSTEM_USER["full_name"]
            )
            return '"{message}" sent by {creator} for {advertiser}`s campaign, "{campaign}"'.format(
                message=event.offer.campaign.push_notification_message,
                creator=full_name,
                campaign=event.offer.campaign.name,
                advertiser=event.offer.campaign.advertiser.name,
            )
        if event.type == "reject":
            return 'Influencer rejected their offer in the {advertiser}`s "{campaign}" campaign'.format(
                advertiser=event.offer.campaign.advertiser.name, campaign=event.offer.campaign.name
            )
        if event.type == "reserve":
            return 'Influencer reserved in the {advertiser}`s "{campaign}" campaign'.format(
                advertiser=event.offer.campaign.advertiser.name, campaign=event.offer.campaign.name
            )
        if event.type == "revoke":
            full_name = (
                event.creator_user.full_name
                if event.creator_user is not None
                else SYSTEM_USER["full_name"]
            )
            return 'Influencer`s offer revoked by {creator} for {advertiser}`s "{campaign}" campaign'.format(
                creator=full_name,
                advertiser=event.offer.campaign.advertiser.name,
                campaign=event.offer.campaign.name,
            )
        return ""


class InfluencerGigsSerializer(HistorySerializer):
    def serialize(self, event):
        gig_event = GigEvent.query.get(event.key)

        return {
            "created": event.created,
            "text": self._text(gig_event),
            "type": self._type(gig_event),
            "user": self._user(gig_event),
        }

    def _text(self, event):
        if event.type == "report" or event.type == "reject":
            return "Gig in '{}' from '{}' was {} on {} for: '{}'".format(
                event.gig.post.campaign.name,
                event.gig.post.campaign.advertiser.name,
                "reported" if event.type == "report" else "rejected",
                event.created,
                event.event.get("reason", "Unknown"),
            )
        if event.type == "dismiss_report":
            return "Gig report for {}`s {} campaign was dismissed by {}".format(
                event.gig.post.campaign.advertiser.name,
                event.gig.post.campaign.name,
                event.creator_user.full_name
                if event.creator_user is not None
                else SYSTEM_USER["full_name"],
            )
        if event.type == "request_resubmission":
            return 'A resubmission was requested by {} for {}`s "{}" campaign'.format(
                event.creator_user.full_name
                if event.creator_user is not None
                else SYSTEM_USER["full_name"],
                event.gig.post.campaign.advertiser.name,
                event.gig.post.campaign.name,
            )
        if event.type == "review":
            return 'Gig was reviewed by {} for {}`s "{}" campaign'.format(
                event.creator_user.full_name
                if event.creator_user is not None
                else SYSTEM_USER["full_name"],
                event.gig.post.campaign.advertiser.name,
                event.gig.post.campaign.name,
            )
        if event.type == "approve":
            return 'Gig was approved by {} for {}`s "{}" campaign'.format(
                event.creator_user.full_name
                if event.creator_user is not None
                else SYSTEM_USER["full_name"],
                event.gig.post.campaign.advertiser.name,
                event.gig.post.campaign.name,
            )
        if event.type == "submit":
            return 'Gig was submitted for {}`s "{}" campaign'.format(
                event.gig.post.campaign.advertiser.name, event.gig.post.campaign.name
            )

        return ""

    def _user(self, event):
        if event.type == "submit":
            return event.gig.offer.influencer.user
        return event.creator_user

    def _type(self, event):
        return f"gig-{event.type}"


class InfluencerHistorySerializer:
    def __init__(self, events):
        self._events = events
        self._influencer_serializer = InfluencerEventsSerializer()
        self._gig_serializer = InfluencerGigsSerializer()
        self._offer_serializer = InfluencerOffersSerializer()

    def serialize(self):
        events = [
            (
                self._offer_serializer.serialize(event)
                if event.type == "offer"
                else self._gig_serializer.serialize(event)
                if event.type == "gig"
                else self._influencer_serializer.serialize(event)
            )
            for event in self._events
        ]
        return events
