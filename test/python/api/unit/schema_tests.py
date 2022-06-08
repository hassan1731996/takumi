import datetime as dt

import pytest
from dateutil.relativedelta import relativedelta
from marshmallow import fields
from marshmallow.exceptions import ValidationError

from takumi.schemas import Schema
from takumi.schemas.fields import RemovedWhitespaceStringField, StrippedStringField
from takumi.schemas.post import GigStateField
from takumi.schemas.signup import validate_birthday
from takumi.schemas.user import SelfInfluencerSchema


class GigSchemaTestSchema(Schema):
    state = GigStateField()


class _TestObjWithState:
    def __init__(self, state):
        self.state = state


def test_gig_schema_state_masks_reported_to_submitted():
    obj = _TestObjWithState("reported")
    dump = GigSchemaTestSchema().dump(obj).data
    assert dump["state"] == "submitted"


def test_gig_schema_state_masks_payment_processing_to_paid():
    obj = _TestObjWithState("reported")
    dump = GigSchemaTestSchema().dump(obj).data
    assert dump["state"] == "submitted"


def test_gig_schema_state_does_not_mask_states_not_found_in_mask():
    obj = _TestObjWithState("submitted")
    dump = GigSchemaTestSchema().dump(obj).data
    assert dump["state"] == "submitted"

    obj = _TestObjWithState("this is definitely not a state")
    dump = GigSchemaTestSchema().dump(obj).data
    assert dump["state"] == "this is definitely not a state"


def test_gig_schema_state_does_mask_new_gig_state_names():
    obj = _TestObjWithState("awaiting_submission")

    dump = GigSchemaTestSchema().dump(obj).data
    assert dump["state"] == "reserved"


def test_validate_birthday_too_young():
    day_before_18th_birthday = dt.date.today() - relativedelta(years=18) + dt.timedelta(days=1)

    with pytest.raises(ValidationError):
        validate_birthday(day_before_18th_birthday)


def test_stripped_string_field_strips_data():
    data = {"id": "none stripped", "value": "   hey I need some stripping    \n\n"}

    class TestSchema(Schema):
        id = fields.String()
        value = StrippedStringField()

    assert TestSchema().dump(data).data == {
        "id": "none stripped",
        "value": "hey I need some stripping",
    }


def test_trimmed_string_field_trims_data():
    data = {"id": "none trimmed", "value": "   hey I need some trimming    \n\n"}

    class TestSchema(Schema):
        id = fields.String()
        value = RemovedWhitespaceStringField()

    assert TestSchema().dump(data).data == {"id": "none trimmed", "value": "heyIneedsometrimming"}


def test_influencer_user_schema_contains_team_member_if_user_has_access_dev_menu_need(
    influencer_user,
):
    influencer_user.needs = ["access_app_development_menu"]
    dumped = SelfInfluencerSchema(context={"user": influencer_user}).dump(influencer_user).data
    assert dumped["is_team_member"] is True
