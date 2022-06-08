from typing import TYPE_CHECKING

from sqlalchemy import cast, extract, func
from sqlalchemy.dialects.postgresql import ARRAY, ENUM
from sqlalchemy.orm import aliased, backref, relationship

from core.common.sqla import MutableList, UUIDString
from core.common.utils import DictObject

from takumi.extensions import db
from takumi.i18n import gettext as _
from takumi.utils import uuid4_str

from .helpers import hybrid_property_expression

if TYPE_CHECKING:
    from takumi.models import Influencer  # noqa


class InfluencerChild(db.Model):
    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)
    gender = db.Column(ENUM("female", "male", name="gender", create_type=False))
    birthday = db.Column(db.Date)
    influencer_information_id = db.Column(
        UUIDString, db.ForeignKey("influencer_information.id", ondelete="cascade"), nullable=False
    )
    influencer_information = relationship(
        "InfluencerInformation", uselist=False, back_populates="children"
    )

    @hybrid_property_expression
    def age(self):
        return cast(extract("year", func.age(self.birthday)), db.Integer)

    @hybrid_property_expression
    def is_unborn(self):
        return func.now() <= self.birthday

    @hybrid_property_expression
    def is_born(self):
        return func.now() > self.birthday


class InformationObject(DictObject):
    @classmethod
    def get(cls, id):
        return cls(**cls._all().get(id), id=id)

    @classmethod
    def all(cls):
        ids = list(cls._all().keys())
        return [cls.get(id) for id in ids]


class TagGroup(InformationObject):
    @classmethod
    def _all(cls):
        return {
            "5a5fc159-6a09-4b7e-b144-357784dc8dca": {"name": _("Appearance"), "description": ""},
            "389f478e-69df-4240-b6a7-817c27bb5db6": {
                "name": _("Dietary requirements"),
                "description": "",
            },
            "1834e7a2-6519-47a7-94d3-79a3f7133d9d": {"name": _("Occupation"), "description": ""},
            "f4a804e0-d45f-4319-b17c-d9f23f75f89f": {"name": _("Lifestyle"), "description": ""},
            "c45a0d6f-2527-4675-93f8-ca28ced97c25": {"name": _("Pets"), "description": ""},
            "b07bfa62-b3f3-4157-a332-3a453bbc0312": {"name": _("Other"), "description": ""},
        }

    @property
    def tags(self):
        return Tag.get_tags_in_group(self.id)

    def __repr__(self):
        return f"<TagGroup: {self.name} ({self.id})>"


class Tag(InformationObject):
    @classmethod
    def _all(cls):
        APPEARANCE = {
            tag_id: dict(
                name=name, group_id=TagGroup.get("5a5fc159-6a09-4b7e-b144-357784dc8dca").id
            )
            for (tag_id, name) in [
                ("e9944093-9acb-4d04-bd19-0b660576683b", _("Plus size")),
                ("8edc75dc-2ff7-40a3-a084-80fd73afac39", _("Sensitive skin")),
                ("213ffe9b-7468-4170-8fe8-3eebc0247955", _("Contact lenses")),
            ]
        }
        DIET = {
            tag_id: dict(
                name=name, group_id=TagGroup.get("389f478e-69df-4240-b6a7-817c27bb5db6").id
            )
            for (tag_id, name) in [
                ("bff8a709-700c-4868-8fcd-98a0224c530d", _("Gluten free")),
                ("cb7e0115-2328-49bf-8df6-4d531cde657a", _("Lactose intolerant")),
                ("dcbcdfe6-a13b-4b11-81d1-7166c9aefe67", _("Vegetarian")),
                ("3fc0b9a5-ebf7-465f-b7b5-4ec376ade729", _("Vegan")),
            ]
        }
        OCCUPATION = {
            tag_id: dict(
                name=name, group_id=TagGroup.get("1834e7a2-6519-47a7-94d3-79a3f7133d9d").id
            )
            for (tag_id, name) in [
                ("9721add6-3b7e-4b22-8abf-01bde4fa12f7", _("Full time job")),
                ("ad89aef9-976c-4713-9d47-05f2675f1fb4", _("Side hustler")),
                ("cfb8b453-18b4-4794-babb-ef282d3de2ab", _("Business owner")),
                ("9ec4112b-9afb-44fe-99fd-78fd7c45f151", _("Full time influencer")),
                ("30ef1cba-1ea8-4725-b6e4-1a148b4c5e9b", _("Entrepeneur")),
                ("e3138d48-076d-4beb-a061-102ea08edcca", _("Student")),
            ]
        }
        LIFESTYLE = {
            tag_id: dict(
                name=name, group_id=TagGroup.get("f4a804e0-d45f-4319-b17c-d9f23f75f89f").id
            )
            for (tag_id, name) in [
                ("d3c473e7-3662-4c08-a6df-5a23f1e669b9", _("Outdoors")),
                ("3dec9495-dfb3-41c4-897b-61c1aa7afe1c", _("Eco-friendly")),
                ("4d9edc09-17a9-4924-82df-2fa10a499ec9", _("Health oriented")),
                ("696f5591-6d99-4645-9398-fdebfbef769a", _("Homeowner")),
            ]
        }
        PETS = {
            tag_id: dict(
                name=name, group_id=TagGroup.get("c45a0d6f-2527-4675-93f8-ca28ced97c25").id
            )
            for (tag_id, name) in [
                ("2c2a4b78-878d-4c2a-b2c4-d3c587b9a11d", _("Cat")),
                ("6440e4d6-4ceb-4e48-aa6b-9d8d09870bef", _("Dog")),
                ("275da677-ddfa-41d8-9f63-1bb5ef806d6c", _("Other")),
            ]
        }
        OTHER = {
            tag_id: dict(
                name=name, group_id=TagGroup.get("b07bfa62-b3f3-4157-a332-3a453bbc0312").id
            )
            for (tag_id, name) in [
                ("b0269ad1-5e89-4696-a9e8-f2209a3e9848", _("Feminist")),
                ("03bfc8df-717b-4fd2-9649-07d4a8d4196e", _("LGBTQ activist")),
                ("7ba8ca1a-6e40-4e9e-b4a7-5c5df707d099", _("Activist")),
            ]
        }
        return dict(**APPEARANCE, **DIET, **OCCUPATION, **LIFESTYLE, **PETS, **OTHER)

    @property
    def group(self):
        return TagGroup.get(self.group_id)

    @classmethod
    def get_from_ids(cls, ids):
        objs = cls.all()
        return [obj for obj in objs if obj.id in ids]

    @classmethod
    def get_tags_in_group(cls, group_id):
        tags = cls.all()
        return [tag for tag in tags if tag.group_id == group_id]

    def __repr__(self):
        return f"<Tag: {self.name} ({self.id})>"


class HairColour(InformationObject):
    @classmethod
    def _all(cls):
        return {
            "058f2c4b-c0fe-4da7-ad85-19d476ba1e6f": {
                "name": "Midnight Black",
                "category": "black",
                "hex": "#090806",
            },
            "e1a85cff-963c-4d9d-b559-ebf0070f264c": {
                "name": "Off Black",
                "category": "black",
                "hex": "#2c222b",
            },
            "466f1955-3b84-41dd-b78b-a55bd67e65d6": {
                "name": "Darkest Brown",
                "category": "brown",
                "hex": "#3b3024",
            },
            "1a646649-fd6c-41a5-9985-a709313f8a28": {
                "name": "Medium Dark Brown",
                "category": "brown",
                "hex": "#4e433f",
            },
            "b846bfee-8e12-4d79-b566-adaf0da7a92f": {
                "name": "Chestnut Brown",
                "category": "brown",
                "hex": "#504444",
            },
            "11d350ef-4bd1-423b-81a2-c43964bafa03": {
                "name": "Light Chestnut Brown",
                "category": "brown",
                "hex": "#6a4e42",
            },
            "b8803ecd-e9ae-4aa5-83da-4b4b6c78a072": {
                "name": "Dark Golden Brown",
                "category": "brown",
                "hex": "#554838",
            },
            "1187fc22-b75a-423c-93d8-457162622936": {
                "name": "Light Golden Brown",
                "category": "brown",
                "hex": "#a7856a",
            },
            "3703e266-10b5-4d02-865c-870c6ff7a484": {
                "name": "Dark Honey Blonde",
                "category": "brown",
                "hex": "#b89778",
            },
            "911946e3-00ae-48f3-89af-7338c7b74c4d": {
                "name": "Bleached Blonde",
                "category": "brown",
                "hex": "#dcd0ba",
            },
            "e835a394-dd4e-40a0-bbdc-fd2eeec072b0": {
                "name": "Light Ash Blonde",
                "category": "blonde",
                "hex": "#debc99",
            },
            "169309af-84e4-48c7-b145-9a3a24dadfa4": {
                "name": "Light Ash Brown",
                "category": "blonde",
                "hex": "#977961",
            },
            "18ee4b14-1c4d-4798-82eb-e83538ba6ccc": {
                "name": "Lightest Blonde",
                "category": "blonde",
                "hex": "#e6cea8",
            },
            "3008bf77-1639-4ade-835a-48e3a80ff3d1": {
                "name": "Pale Golden Blonde",
                "category": "blonde",
                "hex": "#e5c8a8",
            },
            "5effc813-ddf4-4a92-afeb-69cdf4765f13": {
                "name": "Strawberry Blonde",
                "category": "red",
                "hex": "#a56b46",
            },
            "2640b7b3-def2-4bbc-b89e-48b796112a5c": {
                "name": "Light Auburn",
                "category": "red",
                "hex": "#91553d",
            },
            "d931cc9d-1a9e-48e5-95b1-cfbf6680aa77": {
                "name": "Dark Auburn",
                "category": "brown",
                "hex": "#533d32",
            },
            "977cb988-d994-49db-93d4-ceceeddc4ef4": {
                "name": "Darkest Grey",
                "category": "grey",
                "hex": "#71635a",
            },
            "bd1e4d19-f296-4951-a5f0-4f2936560f90": {
                "name": "Medium Grey",
                "category": "grey",
                "hex": "#b7a69e",
            },
            "f3f01231-d395-4bd1-a487-7f5625b2868c": {
                "name": "Light Grey",
                "category": "grey",
                "hex": "#d6c4c2",
            },
            "9603da57-5749-43eb-a02a-450d2f2d4a0a": {
                "name": "White Blonde",
                "category": "blonde",
                "hex": "#fff5e1",
            },
            "eb785aaf-acb9-4f85-8027-6f268c39f6bb": {
                "name": "Platinum Blonde",
                "category": "blonde",
                "hex": "#cabfb1",
            },
            "6848eeaa-f315-4714-b247-707ca17ee8ec": {
                "name": "Russet Red",
                "category": "red",
                "hex": "#8d4a43",
            },
            "8e1a80f1-259c-4295-8b4c-92624e84fe60": {
                "name": "Terra Cotta",
                "category": "red",
                "hex": "#b55239",
            },
        }


class EyeColour(InformationObject):
    @classmethod
    def _all(cls):
        return {
            "f34984ae-2157-4c63-ad36-bb1c535ab9bd": {"name": "blue", "hex": "#6AA7DE"},
            "52a16859-e1dd-439a-8dae-c685524bdb41": {"name": "blue-grey", "hex": "#BED3E6"},
            "bea11e5f-142d-4a3e-908c-96188ad60415": {"name": "grey", "hex": "#B7C5D2"},
            "fe81dcbb-e925-486b-b70c-db931b8e7c00": {"name": "green-grey", "hex": "#C6C9B3"},
            "2734a7b4-4866-4df6-8cd6-3a7a4568ec38": {"name": "green", "hex": "#B8B178"},
            "b6ef605e-a700-468a-993a-065bc2be5fbe": {"name": "hazel", "hex": "#D6B29B"},
            "1ea273ce-d672-4fe1-b0f8-1b6ce6289184": {"name": "medium brown", "hex": "#B29683"},
            "1430cd32-3057-4926-8333-592a8d603b33": {"name": "dark-brown", "hex": "#73564E"},
            "67f67670-04a1-4d9d-9358-69c6cba02419": {"name": "black", "hex": "#534744"},
        }

    def __repr__(self):
        return f"<EyeColour: {self.name} ({self.id})>"


class HairType(InformationObject):
    @classmethod
    def _all(cls):
        return {
            "ea769c27-a210-4fb3-8341-a0c3174b2124": {"name": _("Curly")},
            "0e7fb575-4184-48b9-b3b7-8e054c6f1e9a": {"name": _("Straight")},
        }

    def __repr__(self):
        return f"<HairType: {self.name} ({self.id})>"


class InfluencerInformation(db.Model):
    id = db.Column(UUIDString, primary_key=True, default=uuid4_str)

    account_type = db.Column(db.String)
    children = relationship("InfluencerChild", back_populates="influencer_information")

    hair_colour_id = db.Column(UUIDString)
    eye_colour_id = db.Column(UUIDString)
    hair_type_id = db.Column(UUIDString)

    glasses = db.Column(db.Boolean)
    languages = db.Column(MutableList.as_mutable(ARRAY(db.String)), default=[])

    tag_ids = db.Column(MutableList.as_mutable(ARRAY(UUIDString)))

    influencer_id = db.Column(
        UUIDString, db.ForeignKey("influencer.id", ondelete="cascade"), nullable=False, index=True
    )
    influencer = relationship(
        "Influencer", backref=backref("information", uselist=False), uselist=False
    )

    @property
    def hair_colour(self):
        return HairColour.get(self.hair_colour_id)

    @property
    def eye_colour(self):
        return EyeColour.get(self.eye_colour_id)

    @property
    def hair_type(self):
        return HairType.get(self.hair_type_id)

    @property
    def tags(self):
        return Tag.get_from_ids(self.tag_ids)

    @hybrid_property_expression
    def children_count(cls):
        from takumi.models.influencer_information import InfluencerChild

        AliasedInfluencerInformation = aliased(cls)

        return (
            db.session.query(func.count(InfluencerChild.id))
            .join(AliasedInfluencerInformation)
            .filter(AliasedInfluencerInformation.id == cls.id)
        )
