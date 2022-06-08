from graphene import Interface

from takumi.gql import fields


class HistoryInterface(Interface):
    created = fields.DateTime()
    user = fields.Field("User", source="creator_user")

    @classmethod
    def resolve_type(cls, instance, info):
        from .gig import history_items as gig_history_items

        for history_type, history_class in gig_history_items.items():
            if instance.type == history_type:
                return history_class
