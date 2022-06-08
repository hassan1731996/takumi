import re
from typing import Any, Callable, Dict, List

from takumi.services.exceptions import ServiceException

ig_username_pattern = r"(?!.*\.\.)(?!.*\.$)[^\W][\w.]{0,29}"
ig_hashtag_pattern = r"[A-Za-z0-9_]{1,30}"

Section = Dict[str, str]
BriefSanitiser = Callable[[Section], Dict[str, Any]]


def _strip_edges(string: str) -> str:
    """Strip white space and <br> tags from either side of strings"""
    pattern = r"(^(\s|<br>)+|(\s|<br>)+$)"
    return re.sub(pattern, "", string)


def _replace_nbsp(string: str) -> str:
    """Replace non breaking spaces that seem to be added often in macs"""
    return string.replace("&nbsp;", " ")


def _href_items(string: str) -> str:
    """Fix hrefs in strings

    Does the following:
        * Will move spaces outside of tags
        * Will take @mentions and #hashtags and wrap them in "a href" tags.
        * Will take normal URLs and wrap them automatically in "a href" tags.

    The regex for URLs doesn't try to be perfect and expects urls to start with http(s)
    """
    # Fix spacing in tags
    value = re.sub(r"<(.+?)([^<]*)>(\s*)([^<]*?)(\s*)</(\1)>", r"\3<\1\2>\4</\1>\5", string)

    # Wrap mentions
    value = re.sub(
        rf"(?<!>)@({ig_username_pattern})",
        r'<a href="https://www.instagram.com/\1/">@\1</a>',
        value,
    )

    # Wrap hashtags
    value = re.sub(
        rf"(?<!>)#({ig_hashtag_pattern})",
        r'<a href="https://www.instagram.com/explore/tags/\1/">#\1</a>',
        value,
    )

    # Wrap urls
    value = re.sub(r"(\s|^)(https?://\w+\.\w+[^\s]*)(\s|$)", r'\1<a href="\2">\2</a>\3', value)

    return value


def _sanitize(string: str, convert_tags: bool = True) -> str:
    """Process a string, to clean up and optionally convert tags"""
    # Strip the string
    value = _strip_edges(string)
    value = _replace_nbsp(value)

    if convert_tags:
        value = _href_items(value)

    return value


def _validate_value(section: Section, convert_tags: bool = True) -> Dict[str, str]:
    if "value" not in section:
        raise ServiceException("'value' is missing")

    return {"value": _sanitize(section["value"], convert_tags=convert_tags)}


def _validate_dos_and_donts(section: Section) -> Dict[str, List[str]]:
    if "dos" not in section:
        raise ServiceException("'dos' is missing")
    if "donts" not in section:
        raise ServiceException("'donts' is missing")
    return {
        "dos": [_sanitize(item) for item in section["dos"]],
        "donts": [_sanitize(item) for item in section["donts"]],
    }


def _validate_items(section: Section) -> Dict[str, List[str]]:
    if "items" not in section:
        raise ServiceException("'items' is missing")
    return {"items": [_sanitize(item) for item in section["items"]]}


BRIEF_TYPES: Dict[str, BriefSanitiser] = {
    "heading": lambda section: _validate_value(section, convert_tags=False),
    "sub_heading": lambda section: _validate_value(section, convert_tags=False),
    "paragraph": _validate_value,
    "important": _validate_value,
    "divider": lambda section: {},
    "dos_and_donts": _validate_dos_and_donts,
    "ordered_list": _validate_items,
    "unordered_list": _validate_items,
}
