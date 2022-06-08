from graphene import ObjectType

from takumi.gql import fields


class InfluencerTag(ObjectType):
    id = fields.UUID()
    name = fields.String()


class InfluencerTagsGroup(ObjectType):
    id = fields.UUID()
    name = fields.String()
    description = fields.String()
    tags = fields.List(InfluencerTag)


class InfluencerEyeColour(ObjectType):
    id = fields.UUID()
    name = fields.String()
    hex = fields.String()


class InfluencerHairColour(ObjectType):
    id = fields.UUID()
    name = fields.String()
    category = fields.String()
    hex = fields.String()


class InfluencerHairType(ObjectType):
    id = fields.UUID()
    name = fields.String()


class InfluencerChild(ObjectType):
    id = fields.UUID()
    gender = fields.String()  # XXX: Enum
    born = fields.Boolean(source="is_born")
    birthday = fields.Date()


class InfluencerInformation(ObjectType):
    # Appearance info
    hair_colour = fields.Field(InfluencerHairColour)
    eye_colour = fields.Field(InfluencerEyeColour)
    hair_type = fields.Field(InfluencerHairType)
    account_type = fields.String()
    glasses = fields.Boolean()

    # Children
    children = fields.List(InfluencerChild)

    # Languages
    languages = fields.List(fields.String)

    # Other base tags
    tags = fields.List(InfluencerTag)
