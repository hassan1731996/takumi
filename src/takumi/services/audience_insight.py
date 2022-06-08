from takumi.events.audience_insight import AudienceInsightLog
from takumi.extensions import db
from takumi.models import AudienceInsight, AudienceSection
from takumi.models.audience_insight import STATES as INSIGHT_STATES
from takumi.ocr import analyse_audience_insight
from takumi.services import Service


class AudienceInsightService(Service):
    """
    Represents the business model for AudienceInsight. This isolates the database
    from the application.
    """

    SUBJECT = AudienceInsight
    LOG = AudienceInsightLog

    @property
    def insight(self):
        return self.subject

    # POST
    @staticmethod
    def create(influencer, *, top_locations_url, ages_men_url, ages_women_url, gender_url):
        if "imgix.net/" in top_locations_url:
            top_locations_url = top_locations_url.split("imgix.net/", maxsplit=1)[1]
        if "imgix.net/" in ages_men_url:
            ages_men_url = ages_men_url.split("imgix.net/", maxsplit=1)[1]
        if "imgix.net/" in ages_women_url:
            ages_women_url = ages_women_url.split("imgix.net/", maxsplit=1)[1]
        if "imgix.net/" in gender_url:
            gender_url = gender_url.split("imgix.net/", maxsplit=1)[1]

        insight = AudienceInsight(
            influencer=influencer,
            top_locations=AudienceSection(media_path=top_locations_url),
            ages_men=AudienceSection(media_path=ages_men_url),
            ages_women=AudienceSection(media_path=ages_women_url),
            gender=AudienceSection(media_path=gender_url),
        )

        db.session.add(insight)
        db.session.commit()

        return insight

    def run_ocr(self):
        result = analyse_audience_insight(self.insight)

        ocr_values = {}
        errors = {}
        boundary = {}
        followers = {"followers": self.insight.influencer.followers}

        for section, value in result.items():
            if "error" in value:
                errors[section] = value["error"]
            else:
                ocr_values[section] = {
                    key: {"value": ocr.value, "confidence": ocr.confidence}
                    for key, ocr in value["values"].items()
                }
                boundary[section] = value["boundary"]

                if section == "gender":
                    # Ages sections will have partial followers set based on genders
                    followers["followers_men"] = int(
                        value["values"]["Men"].value / 100 * followers["followers"]
                    )
                    followers["followers_women"] = (
                        followers["followers"] - followers["followers_men"]
                    )

        self.log.add_event("set_ocr_values", ocr_values)
        self.log.add_event("set_boundary", boundary)
        self.log.add_event("set_followers", followers)
        self.log.add_event("set_errors", errors)

        if len(errors):
            self.insight.state = INSIGHT_STATES.INVALID
        else:
            self.insight.state = INSIGHT_STATES.PROCESSED
