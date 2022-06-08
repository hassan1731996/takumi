import pytest

from takumi.utils import has_analyzable_text, is_emaily, is_uuid, ratelimit_user
from takumi.utils.user_agent import get_ios_version_from_user_agent

EMOJIS = "🔥🔥❤️👩‍👩‍👦‍👦"


def test_has_analyzable_text_with_only_emojis_is_false():
    text = "{} ".format(EMOJIS)
    assert has_analyzable_text(text) is False


def test_has_analyzable_text_with_only_text_is_true():
    text = "This is great!"
    assert has_analyzable_text(text) is True


def test_has_analyzable_text_with_emojis_and_text_is_true():
    text = "This is great ! {}".format(EMOJIS)
    assert has_analyzable_text(text) is True


def test_has_analyzable_text_with_only_hashtags_is_false():
    text = "#yolo #yeye   #woo"
    assert has_analyzable_text(text) is False


def test_has_analyzable_text_with_only_mentions_is_false():
    text = "@takumihq @instagram"
    assert has_analyzable_text(text) is False


def test_has_analyzable_text_with_hashtags_and_text_is_true():
    text = "Wunderbar! #fantastistich"
    assert has_analyzable_text(text) is True


def test_has_analyzable_text_with_only_hashtags_and_emojis_is_false():
    text = "#Hash#tags #are #awesome {}".format(EMOJIS)
    assert has_analyzable_text(text) is False


def test_has_analyzable_text_with_emojis_hashtags_and_text_is_true():
    text = "This is a text #texts {}".format(EMOJIS)
    assert has_analyzable_text(text) is True


def test_ratelimit_user_returns_id(influencer_user):
    assert ratelimit_user(influencer_user) == str(influencer_user.id)


def test_ratelimit_user_raises_exception_if_no_id_attribute():
    obj = object()
    with pytest.raises(Exception, match="Default ratelimiting only supports logged in users"):
        ratelimit_user(obj)


def test_get_ios_version_from_user_agent_with_iphone_string(app):
    agent = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 10_3_3 like Mac OS X) AppleWebKit/603.3.8 (KHTML, like Gecko) Mobile"
        "/14G60 [FBAN/FBIOS;FBAV/136.0.0.29.91;FBBV/67565708;FBDV/iPhone9,1;FBMD/iPhone;FBSN/iOS;FBSV/10.3.3;FBS"
        "S/2;FBCR/Verizon;FBID/phone;FBLC/en_US;FBOP/5;FBRV/0]"
    )
    assert get_ios_version_from_user_agent(agent) == [10, 3, 3]


def test_get_ios_version_from_user_agent_with_ipad_string(app):
    agent = (
        "Mozilla/5.0 (iPad; CPU OS 9_3 like Mac OS X) AppleWebKit/601.1.46 (KHTML, like Gecko) Version/9.0 Mo"
        "bile/13F69 Safari/601.1"
    )
    assert get_ios_version_from_user_agent(agent) == [9, 3]


def test_get_ios_version_from_user_agent_with_other_string(app):
    agent = (
        "Mozilla/5.0 (Linux; Android 7.0; SM-G955F Build/NRD90M) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/"
        "64.0.3282.137 Mobile Safari/537.36"
    )
    assert get_ios_version_from_user_agent(agent) is None


def test_get_ios_version_from_user_agent_with_none(app):
    agent = None
    assert get_ios_version_from_user_agent(agent) is None


def test_is_uuid():
    valid_uuid = "deadbeef-dead-dead-dead-feeddeadbeef"
    invalid_uuid = "12345678-this-isnt-good-foolssomeone"
    assert is_uuid(valid_uuid) is True, "{} *is* a valid uuid".format(valid_uuid)
    assert is_uuid(invalid_uuid) is False, "{} *is NOT* a valid uuid".format(invalid_uuid)


def test_is_emaily():
    assert is_emaily("@") is False
    assert is_emaily(" ") is False
    assert is_emaily("@handle") is False
    assert is_emaily("this is a string with an email@inside") is False
    assert is_emaily("this@email") is True
    assert is_emaily("this@email ") is True
    assert is_emaily(" this@email") is True
    assert is_emaily(" this@email ") is True
