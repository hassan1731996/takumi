from graphene import ObjectType

from takumi.gql import fields


class Interests(ObjectType):
    id = fields.UUID()


class ChildrenTargeting(ObjectType):
    id = fields.UUID()
    min_children_count = fields.Int()
    max_children_count = fields.Int()
    ages = fields.List(fields.Int)
    child_gender = fields.String()
    has_unborn_child = fields.Boolean()
    has_born_child = fields.Boolean()


class Targeting(ObjectType):
    regions = fields.List("Region")
    interests = fields.List(Interests)
    ages = fields.List(fields.Int)
    gender = fields.String()
    max_followers = fields.Int()
    min_followers = fields.Int()
    absolute_min_followers = fields.Int()
    verified_only = fields.Boolean()

    hair_types = fields.List("InfluencerHairType")
    hair_colour_categories = fields.List(fields.String)
    eye_colours = fields.List("InfluencerEyeColour")
    has_glasses = fields.Boolean()
    languages = fields.List(fields.String)
    self_tags = fields.List("InfluencerTag")

    children_targeting = fields.Field(ChildrenTargeting)


class TargetingEstimate(ObjectType):
    verified = fields.Int()
    eligible = fields.Int()
    total = fields.Int()
