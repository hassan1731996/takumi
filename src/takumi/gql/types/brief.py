from graphene import Interface, ObjectType
from graphene.utils.str_converters import to_camel_case

from takumi.gql import fields


def _resolve_type(section, info):
    return to_camel_case(section["type"])


class BriefSectionInterface(Interface):
    type = fields.String(resolver=_resolve_type)

    @classmethod
    def resolve_type(cls, section, info):
        if section.get("type") == "heading":
            return BriefHeading
        if section.get("type") == "sub_heading":
            return BriefSubHeading
        if section.get("type") == "paragraph":
            return BriefParagraph
        if section.get("type") == "important":
            return BriefImportant
        if section.get("type") == "divider":
            return BriefDivider
        if section.get("type") == "dos_and_donts":
            return BriefDosAndDonts
        if section.get("type") == "unordered_list":
            return BriefUnorderedList
        if section.get("type") == "ordered_list":
            return BriefOrderedList


class BriefHeading(ObjectType):
    class Meta:
        interfaces = (BriefSectionInterface,)

    value = fields.String()


class BriefSubHeading(ObjectType):
    class Meta:
        interfaces = (BriefSectionInterface,)

    value = fields.String()


class BriefParagraph(ObjectType):
    class Meta:
        interfaces = (BriefSectionInterface,)

    value = fields.String()


class BriefImportant(ObjectType):
    class Meta:
        interfaces = (BriefSectionInterface,)

    value = fields.String()


class BriefDivider(ObjectType):
    class Meta:
        interfaces = (BriefSectionInterface,)


class BriefUnorderedList(ObjectType):
    class Meta:
        interfaces = (BriefSectionInterface,)

    items = fields.List(fields.String)


class BriefOrderedList(ObjectType):
    class Meta:
        interfaces = (BriefSectionInterface,)

    items = fields.List(fields.String)


class BriefDosAndDonts(ObjectType):
    class Meta:
        interfaces = (BriefSectionInterface,)

    dos = fields.List(fields.String)
    donts = fields.List(fields.String)


brief_types = [
    BriefHeading,
    BriefSubHeading,
    BriefParagraph,
    BriefImportant,
    BriefDivider,
    BriefDosAndDonts,
    BriefOrderedList,
    BriefUnorderedList,
]


class BriefTemplate(ObjectType):
    type = fields.String()
    template = fields.List(BriefSectionInterface)
