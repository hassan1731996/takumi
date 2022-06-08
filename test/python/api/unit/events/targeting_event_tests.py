# encoding=utf-8

from unittest import TestCase

from takumi.events.targeting import TargetingLog
from takumi.models import Targeting
from takumi.utils import uuid4_str


class TargetingLogTests(TestCase):
    def setUp(self):
        self.targeting = Targeting()
        self.log = TargetingLog(self.targeting)

    def test_create_targeting(self):
        campaign_id = uuid4_str()
        self.log.add_event("create", {"campaign_id": campaign_id, "region_id": False})
        assert self.targeting.campaign_id == campaign_id
        assert self.targeting.regions == []

    def test_set_ages_sets_none(self):
        self.log.add_event("set_ages", {"ages": []})
        assert self.targeting.ages is None

    def test_set_ages_sets_ages(self):
        self.log.add_event("set_ages", {"ages": [1, 2, 3]})
        assert self.targeting.ages == [1, 2, 3]

    def test_set_gender_sets_none_if_all(self):
        self.log.add_event("set_gender", {"gender": "all"})
        assert self.targeting.gender is None

    def test_set_gender_sets_gender(self):
        self.log.add_event("set_gender", {"gender": "male"})
        assert self.targeting.gender == "male"

    def test_set_interests_sets_none(self):
        self.log.add_event("set_interests", {"interest_ids": []})
        assert self.targeting.interest_ids is None

    def test_set_interests_sets_interests(self):
        self.log.add_event("set_interests", {"interest_ids": ["some_id"]})
        assert self.targeting.interest_ids == ["some_id"]

    def test_set_regions_sets_empty_list(self):
        self.log.add_event("set_regions", {"regions": None})
        assert self.targeting.regions == []
