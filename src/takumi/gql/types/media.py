from graphene import Interface, ObjectType, Union

from takumi.gql import fields


class MediaInterface(Interface):
    id = fields.UUID()
    url = fields.String()

    @classmethod
    def resolve_type(cls, instance, info):
        if isinstance(instance, Image):
            return Image
        if isinstance(instance, Video):
            return Video

        return None


class Image(ObjectType):
    class Meta:
        interfaces = (MediaInterface,)

    @classmethod
    def is_type_of(cls, root, info):
        from takumi.models.media import Image

        return isinstance(root, Image)


class Video(ObjectType):
    class Meta:
        interfaces = (MediaInterface,)

    thumbnail = fields.String()

    @classmethod
    def is_type_of(cls, root, info):
        from takumi.models.media import Video

        return isinstance(root, Video)


class Gallery(ObjectType):
    items = fields.List(MediaInterface)

    def resolve_items(root, info):
        return root

    @classmethod
    def is_type_of(cls, root, info):
        from takumi.models.media import Media

        return isinstance(root, list) and all([isinstance(item, Media) for item in root])


class MediaResult(Union):
    class Meta:
        types = (Image, Video, Gallery)
