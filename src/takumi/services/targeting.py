from takumi.events.targeting import TargetingLog
from takumi.extensions import db
from takumi.models import Region, Targeting
from takumi.models.children_targeting import ChildrenTargeting
from takumi.services import Service
from takumi.services.exceptions import ServiceException


class TargetingService(Service):
    """
    Represents the business model for Targeting. This is the bridge between
    the database and the application.
    """

    SUBJECT = Targeting
    LOG = TargetingLog

    @property
    def targeting(self):
        return self.subject

    # POST
    @staticmethod
    def create_targeting(campaign_id, market, advertiser):
        targeting = Targeting()
        targeting_log = TargetingLog(targeting)

        if market.slug == "test":
            region_id = Region.query.filter(Region.name == "Takumiland").first().id
        elif advertiser.primary_region.market == market:
            region_id = advertiser.primary_region.id
        else:
            region_id = None

        targeting_log.add_event("create", {"campaign_id": campaign_id, "region_id": region_id})
        db.session.add(targeting)
        db.session.commit()

        return targeting

    # PUT
    def update_regions(self, regions):
        if self.targeting.campaign.market_slug == "test":
            raise ServiceException("Unable to change regions in demo/test market")

        self.log.add_event("set_regions", {"regions": regions})

    def update_gender(self, gender):
        self.log.add_event("set_gender", {"gender": gender})

    def update_ages(self, ages):
        self.log.add_event("set_ages", {"ages": ages})

    def update_interests(self, interests):
        self.log.add_event("set_interests", {"interest_ids": interests})

    def update_followers(self, *, min_followers, max_followers):
        """Set the follower range for targeting

        If both ends of the range are set, then we just verify that the max is
        higher than the min. If only one is being set, then it's compared to
        the existing range.
        """
        # Validate the values
        if min_followers is not None:
            if max_followers is not None and min_followers > max_followers:
                raise ServiceException("Minimum followers can't be higher than maximum followers")
            if min_followers < self.targeting.absolute_min_followers:
                raise ServiceException(
                    f"Minimum followers can't be below {self.targeting.absolute_min_followers}"
                )
        if max_followers is not None:
            if max_followers < self.targeting.absolute_min_followers:
                raise ServiceException(
                    f"Maximum followers can't be below {self.targeting.absolute_min_followers}"
                )

        # Only update if they changed
        if min_followers != self.targeting.min_followers:
            self.log.add_event("set_min_followers", {"min_followers": min_followers})

        if max_followers != self.targeting.max_followers:
            self.log.add_event("set_max_followers", {"max_followers": max_followers})

    def update_verified_only(self, verified_only):
        self.log.add_event("set_verified_only", {"verified_only": verified_only})

    def update_hair_type_ids(self, hair_type_ids):
        self.log.add_event("set_hair_types", {"hair_type_ids": hair_type_ids})

    def update_hair_colour_categories(self, hair_colour_categories):
        self.log.add_event(
            "set_hair_colour_categories", {"hair_colour_categories": hair_colour_categories}
        )

    def update_eye_colour_ids(self, eye_colour_ids):
        self.log.add_event("set_eye_colours", {"eye_colour_ids": eye_colour_ids})

    def update_languages(self, languages):
        self.log.add_event("set_languages", {"languages": languages})

    def update_has_glasses(self, has_glasses):
        self.log.add_event("set_has_glasses", {"has_glasses": has_glasses})

    def update_self_tag_ids(self, self_tag_ids):
        self.log.add_event("set_self_tags", {"self_tag_ids": self_tag_ids})

    def update_children_targeting(
        self,
        has_born_child=None,
        has_unborn_child=None,
        min_children_count=None,
        max_children_count=None,
        children_ages=None,
        child_gender=None,
    ):
        updated_children_targeting_values = [
            has_born_child,
            has_unborn_child,
            min_children_count,
            max_children_count,
            children_ages,
            child_gender,
        ]

        if not self.targeting.children_targeting:
            if not any(updated_children_targeting_values):
                # Not set and setting all to none, don't create
                return

            self.targeting.children_targeting = ChildrenTargeting()
        children_targeting = self.targeting.children_targeting

        current_children_targeting_values = [
            children_targeting.has_born_child,
            children_targeting.has_unborn_child,
            children_targeting.min_children_count,
            children_targeting.max_children_count,
            children_targeting.ages,
            children_targeting.child_gender,
        ]

        if updated_children_targeting_values != current_children_targeting_values:
            self.log.add_event(
                "set_children_targeting",
                {
                    "min_children_count": min_children_count,
                    "max_children_count": max_children_count,
                    "ages": children_ages,
                    "child_gender": child_gender,
                    "has_born_child": has_born_child,
                    "has_unborn_child": has_unborn_child,
                },
            )
