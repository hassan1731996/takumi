import os
from copy import deepcopy

import mock
import pytest

from core.config import (
    Config,
    MissingEnvironmentVariables,
    OptionalEnvConfig,
    ProtectedConfig,
    StrictEnvConfig,
)


def test_strict_envconfig_raises_missing_env_var_exception():
    with pytest.raises(MissingEnvironmentVariables):
        StrictEnvConfig(["THIS_IS_A_NON_EXISTENT_ENV_VAR_NAME"])


def test_strict_envconfig_missing_env_var_exception_has_all_missing_vars():
    with pytest.raises(MissingEnvironmentVariables) as exc:
        StrictEnvConfig(["THIS_IS_A_NON_EXISTENT_ENV_VAR_NAME", "THIS_IS_ANOTHER_ONE"])

    assert "THIS_IS_A_NON_EXISTENT_ENV_VAR_NAME" in str(exc.value)
    assert "THIS_IS_ANOTHER_ONE" in str(exc.value)


def test_optional_envconfig_skips_missing():
    env = deepcopy(os.environ)
    os.environ["THIS_EXISTS"] = "1"
    cfg = OptionalEnvConfig(["THIS_EXISTS", "THIS_DOES_NOT_EXIST"])
    assert cfg.THIS_EXISTS == 1
    assert not hasattr(cfg, "THIS_DOES_NOT_EXIST")
    os.environ = env


def test_envconfig_json_parses_values():
    env = deepcopy(os.environ)
    os.environ["FALSE_BOOLEAN"] = "false"
    os.environ["TRUE_BOOLEAN"] = "true"
    os.environ["INTEGER"] = "100"
    os.environ["ARRAY"] = "[1, 2, 3, 4]"
    os.environ["DICT"] = '{"a": 1, "b": 2}'
    os.environ["STRING"] = '"100"'
    os.environ["NON_JSON"] = "this is just some string which is not json"

    cfg = OptionalEnvConfig(
        ["FALSE_BOOLEAN", "TRUE_BOOLEAN", "INTEGER", "ARRAY", "DICT", "STRING", "NON_JSON"]
    )
    assert cfg.FALSE_BOOLEAN is False
    assert cfg.TRUE_BOOLEAN is True
    assert cfg.INTEGER == 100
    assert cfg.STRING == "100"
    assert cfg.ARRAY == [1, 2, 3, 4]
    assert cfg.DICT == {"a": 1, "b": 2}
    assert cfg.NON_JSON == "this is just some string which is not json"
    os.environ = env


def test_config_get_vars():
    class TestConfig(Config):
        this_should_not_be_included = 1
        THIS_SHOULD_BE_INCLUDED = 1
        _this_should_not_be_included = 1

    test = TestConfig()
    test_vars = dict(list(test.get_vars()))
    assert "THIS_SHOULD_BE_INCLUDED" in test_vars
    assert "this_should_not_be_included" not in test_vars
    assert "_this_should_not_be_included" not in test_vars


def test_config_overrides():
    cfg = Config()
    cfg.SQLALCHEMY_ECHO = False

    with mock.patch("core.config.os.environ", {"SQLALCHEMY_ECHO": "true"}):
        overrides = OptionalEnvConfig(["SQLALCHEMY_ECHO"])
        assert overrides.SQLALCHEMY_ECHO is True

    cfg2 = cfg + overrides
    assert cfg2.SQLALCHEMY_ECHO is True


def test_protected_config_does_not_accept_additive_overrides():
    # Arrange
    cfg = ProtectedConfig()
    cfg.IMPORTANT = True
    overrides = Config()
    overrides.IMPORTANT = False

    # Act
    new = cfg + overrides
    # Assert
    assert new.IMPORTANT is True


def test_protected_config_accepts_new_additive_values():
    # Arrange
    cfg = ProtectedConfig()
    overrides = Config()
    overrides.SOMETHING = "new"

    # Act
    new = overrides + cfg
    # Assert
    assert new.SOMETHING == "new"


def test_additive_merging_of_configs_uses_left_side_class():
    # Arrange
    protected_config = ProtectedConfig()
    config = Config()

    assert isinstance(protected_config + config, ProtectedConfig)
    assert isinstance(config + protected_config, Config)


def test_callable_config_var_gets_called_for_value():
    class SomeConfig(Config):
        RELEASE_STAGE = "testing"

        @staticmethod
        def TEST_VAR():
            return "1234"

        def TEST_VAR2(self):
            return "4321"

    cfg = SomeConfig()
    assert cfg.TEST_VAR == "1234"
    assert cfg.TEST_VAR2 == "4321"
