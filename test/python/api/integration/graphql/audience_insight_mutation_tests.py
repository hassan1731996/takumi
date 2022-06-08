from takumi.gql.mutation.audience_insight import SubmitAudienceInsight


def test_submit_audience_insights_creates_insights(client, db_influencer):
    with client.user_request_context(db_influencer.user):
        response = SubmitAudienceInsight().mutate(
            "info",
            top_locations="top_locations",
            ages_men="ages_men",
            ages_women="ages_women",
            gender="gender",
        )

    insight = response.insight

    assert insight.top_locations.media_path == "top_locations"
    assert insight.ages_men.media_path == "ages_men"
    assert insight.ages_women.media_path == "ages_women"
    assert insight.gender.media_path == "gender"
