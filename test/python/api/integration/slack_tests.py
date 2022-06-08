from takumi.slack.channels.influencers import influencer_report


def test_slack_influencer_report(es_influencer, elasticsearch, slack_post):
    influencer_report()
    assert slack_post.called
