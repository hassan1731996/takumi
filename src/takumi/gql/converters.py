import graphene
from graphene_sqlalchemy.converter import (
    convert_sqlalchemy_type,
    get_column_doc,
    is_column_nullable,
)
from sqlalchemy_utc import UtcDateTime

from core.common.sqla import SimpleTSVectorType, UUIDString


@convert_sqlalchemy_type.register(UtcDateTime)
@convert_sqlalchemy_type.register(UUIDString)
@convert_sqlalchemy_type.register(SimpleTSVectorType)
def convert_column_to_string(type, column, registry=None):
    return graphene.String(
        description=get_column_doc(column), required=not is_column_nullable(column)
    )
