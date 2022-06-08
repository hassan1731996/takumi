import json
import os
from typing import Any, Iterator, List, Optional, Tuple


class MissingEnvironmentVariables(Exception):
    pass


class Config:
    def __getattribute__(self, attr: str) -> Any:
        value = super().__getattribute__(attr)
        if attr.startswith("_") or not attr.isupper():
            return value
        elif callable(value):
            return value()
        return value

    def get_vars(self) -> Iterator[Tuple[str, Any]]:
        for k in sorted(dir(self)):
            if k.startswith("_"):
                continue
            if not k.isupper():
                continue
            yield k, getattr(self, k)

    def allow_overrides(self, key: str) -> bool:
        return True

    def __repr__(self) -> str:
        return "<Config (release stage:{})\n{}\n>".format(
            self.RELEASE_STAGE,
            "\n".join([f"{key}: {value}" for key, value in self.get_vars()]),
        )

    def __add__(self, cfg: "Config") -> "Config":
        new = self.__class__()

        for key, var in self.get_vars():
            setattr(new, key, var)

        for key, var in cfg.get_vars():
            if hasattr(new, key):
                if not self.allow_overrides(key):
                    continue  # XXX: would be nice to log something here
            setattr(new, key, var)

        return new


class ProtectedConfig(Config):
    """A Config object which does not accept new values for any of it's variables"""

    _allow_overrides: List[str] = []

    def allow_overrides(self, key: str) -> bool:
        return key in self._allow_overrides


class EnvConfig(Config):
    def _load(self, key: str) -> None:
        value = os.environ[key]
        try:
            value = json.loads(value)  # try to treat this as json
        except Exception:
            pass  # if it's not json, the previous value is used
        setattr(self, key, value)

    def __init__(self, keys: Optional[List[str]] = None) -> None:
        if keys is None:
            keys = []
        _missing = []
        for k in keys:
            try:
                self._load(k)
            except KeyError:
                _missing.append(k)
        self._missing = _missing


class StrictEnvConfig(EnvConfig):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if self._missing:
            raise MissingEnvironmentVariables(
                "Missing environment vars:\n{}".format("\n".join([f"\t{k}" for k in self._missing]))
            )


class OptionalEnvConfig(EnvConfig):
    pass
