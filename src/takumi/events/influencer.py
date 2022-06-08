import datetime as dt

from marshmallow import ValidationError

from takumi.events import Event, EventApplicationException, TableLog
from takumi.models.influencer import STATES, Influencer, InfluencerEvent
from takumi.models.interest import Interest
from takumi.schemas.signup import validate_birthday


class BirthdayException(EventApplicationException):
    pass


class GenderException(EventApplicationException):
    pass


class InfluencerDelete(Event):
    end_state = STATES.DISABLED

    def apply(self, influencer):
        removed = self.properties["removed"]

        instagram_account = influencer.instagram_account

        influencer.interests = []
        influencer.disabled_reason = "User has been removed from Takumi"
        influencer.is_signed_up = False
        if instagram_account:
            instagram_account.verified = False
            instagram_account.info = {}
            instagram_account.influencer = None

        influencer.user.tiktok_username = None
        influencer.user.youtube_channel_url = None

        # Email still has to be a valid email
        if influencer.user.email_login:
            influencer.user.email_login.email = f"{removed}@removed.takumi.com"
        influencer.user.full_name = removed
        influencer.user.active = False
        influencer.deletion_date = dt.datetime.now(dt.timezone.utc)


class InfluencerSetAudienceInsightExpires(Event):
    def apply(self, influencer):
        influencer.audience_insight_expires = self.properties["expires"]


class InfluencerDisabled(Event):
    """Disables the user and sets a disabled reason.
    The disabled reason is not shown to the influencer.
    """

    start_state = (STATES.NEW, STATES.REVIEWED, STATES.VERIFIED)
    end_state = STATES.DISABLED

    def apply(self, influencer):
        influencer.disabled_reason = self.properties["reason"]


class InfluencerEnabled(Event):
    start_state = STATES.DISABLED
    end_state = STATES.REVIEWED

    def apply(self, influencer):
        influencer.disabled_reason = None


class InfluencerReviewed(Event):
    start_state = STATES.NEW
    end_state = STATES.REVIEWED

    def apply(self, influencer):
        pass


class InfluencerVerified(Event):
    start_state = STATES.REVIEWED
    end_state = STATES.VERIFIED

    def apply(self, influencer):
        pass


class InfluencerCooldown(Event):
    start_state = (STATES.REVIEWED, STATES.VERIFIED)
    end_state = STATES.COOLDOWN

    def apply(self, influencer):
        days = self.properties["days"]
        influencer.cooldown_ends = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=days)


class InfluencerEndCooldown(Event):
    start_state = STATES.COOLDOWN
    end_state = STATES.REVIEWED

    def apply(self, influencer):
        influencer.cooldown_ends = None


class InfluencerUnverified(Event):
    start_state = STATES.VERIFIED
    end_state = STATES.REVIEWED

    def apply(self, influencer):
        pass


class InfluencerComment(Event):
    def apply(self, influencer):
        pass


class InfluencerRestore(Event):
    start_state = STATES.DISABLED
    end_state = STATES.NEW

    def apply(self, influencer):
        influencer.deletion_date = None
        influencer.disabled_reason = None


class InfluencerSetAddress(Event):
    def apply(self, influencer):
        if "name" in self.properties:
            influencer.address.name = self.properties["name"]
        if "address1" in self.properties:
            influencer.address.address1 = self.properties["address1"]
        if "address2" in self.properties:
            influencer.address.address2 = self.properties["address2"]
        if "city" in self.properties:
            influencer.address.city = self.properties["city"]
        if "postal_code" in self.properties:
            influencer.address.postal_code = self.properties["postal_code"]
        if "is_pobox" in self.properties:
            influencer.address.is_pobox = self.properties["is_pobox"]
        if "state" in self.properties:
            influencer.address.state = self.properties["state"]
        if "phonenumber" in self.properties:
            influencer.address.phonenumber = self.properties["phonenumber"]
        influencer.address.modified = dt.datetime.now(dt.timezone.utc)


class InfluencerSetBirthday(Event):
    def apply(self, influencer):
        birthday = self.properties["birthday"]
        try:
            validate_birthday(birthday)
        except ValidationError as e:
            raise BirthdayException(e.args[0])
        influencer.user.birthday = birthday

        # Update the properties to include a serializable date for the log
        self.properties["birthday"] = self.properties["birthday"].isoformat()


class InfluencerSetGender(Event):
    def apply(self, influencer):
        gender = self.properties["gender"]
        if gender is not None and gender.lower() == "all":
            gender = None
        influencer.user.gender = gender


class InfluencerSetInterests(Event):
    def apply(self, influencer):
        influencer.interests = Interest.query.filter(
            Interest.id.in_(self.properties["interests"])
        ).all()


class InfluencerSignedUp(Event):
    def apply(self, influencer):
        pass


class InfluencerChangeEmail(Event):
    def apply(self, influencer):
        pass


class InfluencerSetDeletionDate(Event):
    start_state = (STATES.NEW, STATES.REVIEWED, STATES.VERIFIED, STATES.COOLDOWN, STATES.DISABLED)

    def apply(self, influencer):
        influencer.deletion_date = self.properties["deletion_date"]


class InfluencerSetEmail(Event):
    def apply(self, influencer):
        influencer.user.email_login.email = self.properties["email"]


class InfluencerSetTargetRegion(Event):
    def apply(self, influencer):
        influencer.target_region_id = self.properties["region_id"]


class InfluencerSetCurrentRegion(Event):
    def apply(self, influencer):
        influencer.current_region_id = self.properties["region_id"]


class InfluencerSetVatNumber(Event):
    def apply(self, influencer: Influencer) -> None:
        influencer.is_vat_registered = self.properties["is_vat_registered"]
        influencer.vat_number = self.properties["vat_number"]
        # At this point we're only setting validated numbers on the influencer
        influencer.vat_number_validated = self.properties["is_vat_registered"]


class InfluencerSendInstagramDirectMessage(Event):
    def apply(self, influencer):
        pass


class InfluencerSendEmail(Event):
    def apply(self, influencer):
        pass


class InfluencerSetImpressionsRatio(Event):
    def apply(self, influencer):
        influencer.instagram_account.impressions_ratio = self.properties["ratio"]


class InfluencerLog(TableLog):
    event_model = InfluencerEvent
    relation = "influencer"
    type_map = {
        "audience_insight_expires": InfluencerSetAudienceInsightExpires,
        "birthday": InfluencerSetBirthday,
        "cancel_cooldown": InfluencerEndCooldown,
        "change_email": InfluencerChangeEmail,
        "comment": InfluencerComment,
        "cooldown": InfluencerCooldown,
        "delete": InfluencerDelete,
        "disable": InfluencerDisabled,
        "enable": InfluencerEnabled,
        "end_cooldown": InfluencerEndCooldown,
        "gender": InfluencerSetGender,
        "interests": InfluencerSetInterests,
        "restore": InfluencerRestore,
        "review": InfluencerReviewed,
        "send-email": InfluencerSendEmail,
        "send-instagram-direct-message": InfluencerSendInstagramDirectMessage,
        "vat_number": InfluencerSetVatNumber,
        "set_address": InfluencerSetAddress,
        "set_current_region": InfluencerSetCurrentRegion,
        "set_deletion_date": InfluencerSetDeletionDate,
        "set_email": InfluencerSetEmail,
        "set_impressions_ratio": InfluencerSetImpressionsRatio,
        "set_target_region": InfluencerSetTargetRegion,
        "signup": InfluencerSignedUp,
        "unverify": InfluencerUnverified,
        "verify": InfluencerVerified,
    }
