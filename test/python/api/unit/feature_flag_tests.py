from takumi.feature_flags import FLAGS, RolloutFlag, UserFlag


def test_rollout_flag_feature_peer_group(influencer_user):
    class TestFlag(RolloutFlag):
        key = "KEY"
        chance = 0.0

    influencer_user.id = "e2f08878-36e8-489f-bcf9-5ee36123309a"
    flag = TestFlag(influencer_user)

    flag.key = "FEATURE"
    assert flag.feature_peer_group == 10

    flag.key = "FOR"
    assert flag.feature_peer_group == 5

    flag.key = "TAKUMI"
    assert flag.feature_peer_group == 9

    flag.key = "INFLUENCERS"
    assert flag.feature_peer_group == 12


def test_rollout_flag_enabled(influencer_user):
    class TestFlag(RolloutFlag):
        enable_for_takumi = False
        key = "KEY"
        chance = 0.0

    influencer_user.id = "e2f08878-36e8-489f-bcf9-5ee36123309a"
    flag = TestFlag(influencer_user)

    flag.key = "FEATURE"
    flag.chance = 0.0
    assert not flag.enabled

    flag.key = "FOR"
    flag.chance = 0.3
    assert not flag.enabled

    flag.key = "TAKUMI"
    flag.chance = 0.7
    assert flag.enabled

    flag.key = "INFLUENCERS"
    flag.chance = 1.0
    assert flag.enabled


def test_user_flag_enabled(influencer_user, influencer):
    class TestFlag(UserFlag):
        enable_for_takumi = False
        key = "KEY"

    flag = TestFlag(influencer_user)

    assert not flag.enabled

    influencer_user.influencer.info[flag.key] = False

    assert not flag.enabled

    influencer_user.influencer.info[flag.key] = True

    assert flag.enabled


def test_rollout_flags_chance_range():
    for flag in FLAGS:
        if RolloutFlag not in flag.mro():
            continue
        assert (
            0.0 <= flag.chance <= 1.0
        ), f"RolloutFlag chance has to be between 0.0 and 1.0. {flag.__name__} is {flag.chance}"
