import operator
from functools import reduce

from elasticsearch_dsl import Q

from core.targeting.targeting import age_es_query_filters


class InformationSearchMixin:
    def _filter_glasses(self, val):
        return self.filter("nested", path="information", query=Q("term", information__glasses=val))

    def filter_information_account_type(self, account_type):
        return self.filter(
            "nested", path="information", query=Q("term", information__account_type=account_type)
        )

    def filter_information_has_glasses(self):
        return self._filter_glasses(True)

    def filter_information_has_no_glasses(self):
        return self._filter_glasses(False)

    def filter_information_hair_colour_category(self, hair_colour_categories):
        return self.filter(
            "nested",
            path="information",
            query=Q("terms", information__hair_colour__category=hair_colour_categories),
        )

    def filter_information_hair_colour(self, hair_colour_ids):
        return self.filter(
            "nested",
            path="information",
            query=Q("terms", information__hair_colour__id=hair_colour_ids),
        )

    def filter_information_eye_colour(self, eye_colour_ids):
        return self.filter(
            "nested",
            path="information",
            query=Q("terms", information__eye_colour__id=eye_colour_ids),
        )

    def filter_information_hair_type(self, hair_type_id):
        return self.filter(
            "nested", path="information", query=Q("terms", information__hair_type__id=hair_type_id)
        )

    def filter_information_languages(self, languages):
        return self.filter(
            "nested", path="information", query=Q("terms", information__languages=languages)
        )

    def filter_information_tags(self, tag_ids):
        return self.query(
            "nested",
            path="information",
            query=reduce(
                operator.and_, (Q("term", information__tags__id=tag_id) for tag_id in tag_ids)
            ),
        )

    def _filter_children(self, query):
        return self.filter(
            "nested",
            path="information",
            query=Q("nested", path="information.children", query=query),
        )

    def filter_information_child_count(self, min_count=None, max_count=None):
        child_count = 'doc["information"]["children"].size()'
        _self = self
        if min_count:
            _self = _self.filter({"script": {"script": f"{child_count} >= {min_count}"}})
        if max_count:
            _self = _self.filter({"script": {"script": f"{child_count} <= {max_count}"}})
        return _self

    def filter_information_child_gender(self, gender):
        return self._filter_children(Q("term", information__children__gender=gender))

    def filter_information_has_born_child(self):
        return self._filter_children(Q("term", information__children__born=True))

    def filter_information_has_unborn_child(self):
        return self._filter_children(Q("term", information__children__born=False))

    def filter_information_child_age(self, ages):
        return self._filter_children(age_es_query_filters(ages, "information__children__birthday"))
