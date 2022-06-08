from takumi.events import Event, TableLog
from takumi.models import AudienceInsightEvent


class SetOcrValues(Event):
    def apply(self, insight):
        insight.top_locations.ocr_values = self.properties.get("top_locations", {})
        insight.ages_men.ocr_values = self.properties.get("ages_men", {})
        insight.ages_women.ocr_values = self.properties.get("ages_women", {})
        insight.gender.ocr_values = self.properties.get("gender", {})


class SetBoundary(Event):
    def apply(self, insight):
        insight.top_locations.boundary = self.properties.get("top_locations", [])
        insight.ages_men.boundary = self.properties.get("ages_men", [])
        insight.ages_women.boundary = self.properties.get("ages_women", [])
        insight.gender.boundary = self.properties.get("gender", [])


class SetFollowers(Event):
    def apply(self, insight):
        insight.top_locations.followers = self.properties["followers"]
        insight.gender.followers = self.properties["followers"]

        insight.ages_men.followers = self.properties.get("followers_men", 0)
        insight.ages_women.followers = self.properties.get("followers_women", 0)


class SetErrors(Event):
    def apply(self, insight):
        insight.top_locations.errors = self.properties.get("top_locations", {})
        insight.ages_men.errors = self.properties.get("ages_men", {})
        insight.ages_women.errors = self.properties.get("ages_women", {})
        insight.gender.errors = self.properties.get("gender", {})


class AudienceInsightLog(TableLog):
    event_model = AudienceInsightEvent
    relation = "audience_insight"
    type_map = {
        "set_ocr_values": SetOcrValues,
        "set_boundary": SetBoundary,
        "set_followers": SetFollowers,
        "set_errors": SetErrors,
    }
