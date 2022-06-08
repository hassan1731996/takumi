import pytest
from flask_sqlalchemy import Model
from sqlalchemy import Column

from core.common.sqla import SoftEnum


def test_soft_enum_raises_type_error_on_no_choice():
    with pytest.raises(TypeError):

        class TestObject(Model):
            col = Column(SoftEnum())


def test_soft_enum_raises_type_error_on_invalid_choice():
    class TestObject(Model):
        col = Column(SoftEnum("a", "b"))

    with pytest.raises(TypeError):
        TestObject(col="c")


def test_soft_enum_raises_no_error_on_valid_choice():
    class TestObject(Model):
        col = Column(SoftEnum("a"))

    with pytest.raises(TypeError):
        TestObject(col="a")
