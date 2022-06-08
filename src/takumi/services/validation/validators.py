from abc import ABCMeta, abstractmethod
from collections import Iterable
from typing import Any, List, Optional, TypeVar, Union

T = TypeVar("T")


class ValidatorException(Exception):
    pass


class Validator:
    __meta__ = ABCMeta

    @abstractmethod
    def validate(self, field: Any) -> bool:
        """The function that runs the validator validation on the field"""
        pass


class WithEvery(Validator):
    def __init__(self, validator: Validator) -> None:
        self._validator = validator

    def validate(self, fields: Any) -> bool:
        for field in fields:
            if not self._validator.validate(field):
                return False
        return True


class Required(Validator):
    def validate(self, field: Any) -> bool:
        if isinstance(field, Iterable):
            return bool(field)
        return field is not None


class Equals(Validator):
    def __init__(self, value: T) -> None:
        self._value = value

    def validate(self, field: T) -> bool:
        return field == self._value


class OneOf(Validator):
    def __init__(self, values: List[T]) -> None:
        self._values = values

    def validate(self, field: T) -> bool:
        return field in self._values


class Range(Validator):
    """
    ```python
    validators.Range(10, 20)        # 10 >= number <= 20
    validators.Range(10)            # number >= 10
    validators.Range(None, 10)      # number <= 10
    ```
    """

    def __init__(self, min_value: Optional[int] = None, max_value: Optional[int] = None) -> None:
        self._min = min_value
        self._max = max_value

    def validate(self, field: Optional[int]) -> bool:
        if field is None:
            return False

        if self._min is not None and field < self._min:
            return False
        if self._max is not None and field > self._max:
            return False
        return True


class Length(Validator):
    """
    ```python
    validators.Length(10, 20)       # 10 >= length <= 20
    validators.Length(10)           # length == 10
    validators.Length(10, None)     # length >= 10
    validators.Length(None, 10)     # length <= 10
    ```
    """

    def __init__(self, *args: Union[int, None]) -> None:
        if len(args) == 2:
            self._min = args[0]
            self._max = args[1]
        elif len(args) == 1:
            self._length = args[0]
        else:
            raise ValidatorException("Must pass either 1 or 2 arguments to the Length validator")

    def validate(self, field: Optional[str]) -> bool:
        if field is None:
            return False

        if hasattr(self, "_length"):
            return len(field) == self._length

        is_valid = False
        if self._min is not None:
            is_valid = len(field) >= self._min
        if self._max is not None:
            is_valid = len(field) <= self._max
        return is_valid
