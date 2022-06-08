from typing import Any, List, Optional, Type, TypeVar, Union

from . import validators  # noqa


class SchemaException(Exception):
    pass


class ValidationSchema:
    """
    Define a class based schema that inherits from the ValidationSchema.
    All class attributes should be of type tuple with as many validators
    as wanted, before ending with the error message.

    ```python
    from takumi.services.validation import validators, ValidationSchema

    class InstanceValidationSchema(ValidationSchema):
        name = validators.IsRequired(), 'The error message'
        description = validators.IsEqual('Must equal me'), 'Messages can be formattible "{}"'
    ```

    Nested attributes should be defined with `__`, e.g. let's say we want all gigs of a campaign
    to have exactly 100 likes:
    ```python
    class CampaignValidationSchema(ValidationSchema):
        posts__gigs__likes = IsEqual(100), 'All gigs need to have `100` likes. Received "{}" likes'
    ```
    """

    @classmethod
    def get_fields(cls) -> List[str]:
        attrs = []
        for attr_name, field_obj in cls.__dict__.items():
            if attr_name.startswith("__"):
                continue
            if not isinstance(field_obj, tuple):
                raise SchemaException(
                    'Schema attributes must be of type "tuple". "{}" is of type "{}"'.format(
                        attr_name, type(field_obj)
                    )
                )
            attrs.append(attr_name)
        return attrs


T = TypeVar("T")


def _get_attr(obj: T, lis: List[str]) -> Union[T, List]:
    """
    This function can get attributes of nested fields, even
    for many to many relations.

    ```python
    Validate._get_attr(obj, ['posts', 'gigs', 'likes'])
    ```
    """
    if obj is not None and len(lis):
        if isinstance(obj, list):
            attrs = []
            for o in obj:
                attr = _get_attr(getattr(o, lis[0]), lis[1:])
                attrs.extend(attr if isinstance(attr, list) else [attr])
            return attrs
        return _get_attr(getattr(obj, lis.pop(0)), lis)
    return obj


def Validate(
    obj: Any, schema: Type[ValidationSchema], ignore_validators: Optional[List[str]] = None
) -> List[str]:
    if ignore_validators is None:
        ignore_validators = []

    errors = []
    attr_name: str
    for attr_name in schema.get_fields():
        if attr_name in ignore_validators:
            continue
        field_obj = _get_attr(obj, attr_name.split("__"))
        for validator in getattr(schema, attr_name)[:-1]:
            if not validator.validate(field_obj):
                errors.append(getattr(schema, attr_name)[-1].format(field_obj))
                break
    return errors
