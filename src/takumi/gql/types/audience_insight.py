from graphene import ObjectType

from takumi.gql import fields

from .media import MediaInterface


class OCRResult(ObjectType):
    name = fields.String()
    value = fields.Field("Percent")
    confidence = fields.Field("Percent")
    followers = fields.Int()

    def resolve_value(root, info):
        return root["value"] / 100

    def resolve_confidence(root, info):
        return root["confidence"] / 100


class OCRError(ObjectType):
    type = fields.String()
    message = fields.String()


class AudienceSection(ObjectType):
    id = fields.UUID()
    created = fields.DateTime()

    url = fields.String()
    boundary = fields.List(fields.Int)
    values = fields.List(OCRResult)
    errors = fields.Field(OCRError)
    has_errors = fields.Boolean()

    def resolve_url(section, info):
        return f"https://takumi.imgix.net/{section.media_path}"

    def resolve_values(section, info):
        section_type = len(info.path) == 4 and info.path[2]
        if section_type == "topLocations":
            reverse = True
            key = "value"
        elif section_type in ("agesMen", "agesWomen"):
            reverse = False
            key = "name"
        else:
            reverse = False
            key = None

        values = [
            {
                "name": key,
                "value": result["value"],
                "confidence": result["confidence"],
                "followers": int(section.followers * result["value"] / 100),
            }
            for key, result in section.ocr_values.items()
        ]

        if key:
            return sorted(values, reverse=reverse, key=lambda item: item[key])

        return values

    def resolve_has_errors(section, info):
        return len(section.errors) > 0


class AudienceInsight(ObjectType):
    id = fields.UUID()
    created = fields.DateTime()

    media = fields.List(MediaInterface)
    expired = fields.Boolean()
    state = fields.String()

    top_locations = fields.Field(AudienceSection)
    ages_men = fields.Field(AudienceSection)
    ages_women = fields.Field(AudienceSection)
    gender = fields.Field(AudienceSection)
