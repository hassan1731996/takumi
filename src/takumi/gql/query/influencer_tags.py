from takumi.gql import fields
from takumi.models.influencer_information import EyeColour, HairColour, HairType, TagGroup
from takumi.roles import permissions


class InfluencerTagsQuery:
    influencer_tags = fields.List("InfluencerTagsGroup")
    influencer_hair_colours = fields.List("InfluencerHairColour")
    influencer_hair_types = fields.List("InfluencerHairType")
    influencer_eye_colours = fields.List("InfluencerEyeColour")

    @permissions.public.require()
    def resolve_influencer_tags(root, info):
        return TagGroup.all()

    @permissions.public.require()
    def resolve_influencer_hair_colours(root, info):
        return HairColour.all()

    @permissions.public.require()
    def resolve_influencer_hair_types(root, info):
        return HairType.all()

    @permissions.public.require()
    def resolve_influencer_eye_colours(root, info):
        return EyeColour.all()
