from takumi.events import Event, TableLog
from takumi.models import Region, TargetingEvent


class CreateTargeting(Event):
    def apply(self, targeting):
        targeting.campaign_id = self.properties["campaign_id"]
        if self.properties["region_id"]:
            targeting.regions = [Region.query.get(self.properties["region_id"])]


class SetAges(Event):
    def apply(self, targeting):
        targeting.ages = sorted(self.properties["ages"]) if self.properties["ages"] else None


class SetGender(Event):
    def apply(self, targeting):
        targeting.gender = (
            None if self.properties["gender"].lower() == "all" else self.properties["gender"]
        )


class SetInterests(Event):
    def apply(self, targeting):
        targeting.interest_ids = self.properties["interest_ids"] or None


class SetRegions(Event):
    def apply(self, targeting):
        targeting.regions = (
            Region.query.filter(Region.id.in_(self.properties["regions"])).all()
            if self.properties["regions"]
            else []
        )


class SetMaxFollowers(Event):
    def apply(self, targeting):
        targeting.max_followers = self.properties["max_followers"]


class SetMinFollowers(Event):
    def apply(self, targeting):
        targeting.min_followers = self.properties["min_followers"]


class SetVerifiedOnly(Event):
    def apply(self, targeting):
        targeting.verified_only = self.properties["verified_only"]


class SetHairTypes(Event):
    def apply(self, targeting):
        targeting.hair_type_ids = self.properties["hair_type_ids"]


class SetHairColourCategories(Event):
    def apply(self, targeting):
        targeting.hair_colour_categories = self.properties["hair_colour_categories"]


class SetEyeColours(Event):
    def apply(self, targeting):
        targeting.eye_colour_ids = self.properties["eye_colour_ids"]


class SetLanguages(Event):
    def apply(self, targeting):
        targeting.languages = self.properties["languages"]


class SetHasGlasses(Event):
    def apply(self, targeting):
        targeting.has_glasses = self.properties["has_glasses"]


class SetSelfTags(Event):
    def apply(self, targeting):
        targeting.self_tag_ids = self.properties["self_tag_ids"]


class SetChildrenTargeting(Event):
    def apply(self, targeting):

        # XXX: Fix in web
        ages = self.properties["ages"]
        if ages and len(ages) == 2 and max(ages) - min(ages) != 1:
            ages = list(range(min(ages), max(ages)))

        children_targeting = targeting.children_targeting
        children_targeting.min_children_count = self.properties["min_children_count"]
        children_targeting.max_children_count = self.properties["max_children_count"]
        children_targeting.ages = ages
        children_targeting.child_gender = self.properties["child_gender"]
        children_targeting.has_unborn_child = self.properties["has_unborn_child"]
        children_targeting.has_born_child = self.properties["has_born_child"]


class TargetingLog(TableLog):
    event_model = TargetingEvent
    relation = "targeting"
    type_map = {
        "create": CreateTargeting,
        "set_ages": SetAges,
        "set_gender": SetGender,
        "set_interests": SetInterests,
        "set_max_followers": SetMaxFollowers,
        "set_min_followers": SetMinFollowers,
        "set_verified_only": SetVerifiedOnly,
        "set_regions": SetRegions,
        "set_hair_types": SetHairTypes,
        "set_hair_colour_categories": SetHairColourCategories,
        "set_eye_colours": SetEyeColours,
        "set_languages": SetLanguages,
        "set_has_glasses": SetHasGlasses,
        "set_self_tags": SetSelfTags,
        "set_children_targeting": SetChildrenTargeting,
    }
