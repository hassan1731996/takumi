from typing import Dict

from takumi.gql import arguments


class InfluencerInformationGraphQLMixin:
    INFORMATION_RANGE_PARAMS = {"child_count": dict(type=arguments.Int())}
    MIN_INFORMATION_PARAMS = {"min_" + k: v for k, v in INFORMATION_RANGE_PARAMS.items()}
    MAX_INFORMATION_PARAMS = {"max_" + k: v for k, v in INFORMATION_RANGE_PARAMS.items()}

    INFORMATION_PARAMS: Dict[str, Dict] = {
        "account_type": dict(type=arguments.String()),
        "tag_ids": dict(type=arguments.List(arguments.UUID)),
        "has_glasses": dict(default=None, type=arguments.Boolean()),
        "hair_colour": dict(type=arguments.List(arguments.UUID)),
        "hair_colour_category": dict(type=arguments.List(arguments.String)),
        "eye_colour": dict(type=arguments.List(arguments.UUID)),
        "hair_type": dict(type=arguments.List(arguments.UUID)),
        "has_born_child": dict(default=None, type=arguments.Boolean()),
        "has_unborn_child": dict(default=None, type=arguments.Boolean()),
        "languages": dict(type=arguments.List(arguments.String)),
        "children_ages": dict(default=None, type=arguments.List(arguments.Int)),
        "child_gender": dict(type=arguments.String()),
        **MAX_INFORMATION_PARAMS,
        **MAX_INFORMATION_PARAMS,
    }

    def _filter_information_account_type(self, gql_params):
        account_type = gql_params.get("account_type")
        if account_type:
            return self.filter_information_account_type(account_type)
        return self

    def _filter_information_glasses(self, gql_params):
        has_glasses = gql_params.get("has_glasses")

        if has_glasses is None:
            return self

        if has_glasses:
            return self.filter_information_has_glasses()

        return self.filter_information_has_no_glasses()

    def _filter_information_hair_colour_category(self, gql_params):
        hair_colour_categories = gql_params.get("hair_colour_category")
        if hair_colour_categories:
            return self.filter_information_hair_colour_category(hair_colour_categories)
        return self

    def _filter_information_hair_colour(self, gql_params):
        hair_colour_ids = gql_params.get("hair_colour")
        if hair_colour_ids:
            return self.filter_information_hair_colour(hair_colour_ids)
        return self

    def _filter_information_eye_colour(self, gql_params):
        eye_colour_ids = gql_params.get("eye_colour")
        if eye_colour_ids:
            return self.filter_information_eye_colour(eye_colour_ids)
        return self

    def _filter_information_hair_type(self, gql_params):
        hair_type = gql_params.get("hair_type")
        if hair_type:
            return self.filter_information_hair_type(hair_type)
        return self

    def _filter_information_has_born_child(self, gql_params):
        has_born_child = gql_params.get("has_born_child")
        if has_born_child is True:
            return self.filter_information_has_born_child()
        return self

    def _filter_information_has_unborn_child(self, gql_params):
        has_unborn_child = gql_params.get("has_unborn_child")
        if has_unborn_child is True:
            return self.filter_information_has_unborn_child()
        return self

    def _filter_information_child_gender(self, gql_params):
        child_gender = gql_params.get("child_gender")
        if child_gender:
            return self.filter_information_child_gender(child_gender)
        return self

    def _filter_information_languages(self, gql_params):
        languages = gql_params.get("languages")
        if languages:
            return self.filter_information_languages(languages)
        return self

    def _filter_information_child_age(self, gql_params):
        children_ages = gql_params.get("children_ages")
        # XXX: Fix in web
        if (
            children_ages
            and len(children_ages) == 2
            and max(children_ages) - min(children_ages) != 1
        ):
            children_ages = list(range(min(children_ages), max(children_ages)))

        if children_ages:
            return self.filter_information_child_age(children_ages)
        return self

    def _filter_information_tag_ids(self, gql_params):
        tag_ids = gql_params["tag_ids"]
        if tag_ids:
            return self.filter_information_tags(tag_ids)
        return self

    def _filter_information(self, gql_params):
        default_values = {k: v.get("default") for k, v in self.INFORMATION_PARAMS.items()}
        gql_params = dict(default_values, **gql_params)
        return (
            self._filter_information_glasses(gql_params)
            ._filter_information_account_type(gql_params)
            ._filter_information_hair_colour(gql_params)
            ._filter_information_hair_colour_category(gql_params)
            ._filter_information_eye_colour(gql_params)
            ._filter_information_hair_type(gql_params)
            ._filter_information_has_born_child(gql_params)
            ._filter_information_has_unborn_child(gql_params)
            ._filter_information_child_gender(gql_params)
            ._filter_information_child_age(gql_params)
            ._filter_information_languages(gql_params)
            ._filter_information_tag_ids(gql_params)
        )


class InformationParams(arguments.InputObjectType):
    for k, v in InfluencerInformationGraphQLMixin.INFORMATION_PARAMS.items():
        locals()[k] = v["type"]
