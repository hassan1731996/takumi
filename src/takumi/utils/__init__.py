import re
import unicodedata
import uuid
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Union
from unicodedata import normalize

import requests
from flask import current_app, g
from itp import itp

from takumi.utils.emojis import find_emojis

if TYPE_CHECKING:
    from takumi.models.user import User


def uuid4_str() -> str:
    return str(uuid.uuid4())


def is_uuid(subject: str) -> bool:
    try:
        uuid.UUID(subject)
    except ValueError:
        return False
    return True


def is_emaily(subject: str) -> bool:
    """Determine if a string might be an email.

    definition:
    adjective, emailier, emailiest
    1. A string contains an '@' symbol in it, but not at the start or the end, and no spaces
    Example:
     This string is definitely *emaily*, but it doesn't end in a valid TLD .. whatever that means these days.
    """
    stripped = subject.strip()
    if (
        "@" in stripped
        and " " not in stripped
        and (not stripped.startswith("@") and not stripped.endswith("@"))
    ):
        return True
    return False


def purge_imgix_url(url: str):
    """Purge the cache for the url on imgix. Useful when updating an image in our S3 bucket for example"""
    purge_endpoint = "https://api.imgix.com/v2/image/purger"
    api_key = current_app.config["IMGIX_APIKEY"]
    requests.post(purge_endpoint, auth=(api_key, ""), data={"url": url})


def normalize_str(string: str) -> Optional[str]:
    """Return a normalized string for safe comparisons"""
    if string is not None:
        return unicodedata.normalize("NFKC", str(string))
    return None


def has_analyzable_text(text: str) -> bool:
    """Check wether text has any sentimentally analyzable text

    We remove hashtags and emojis from the text, if nothing is
    left, then there's nothing to analyze.
    """
    emojis = set(find_emojis(text))
    text = normalize("NFC", text)
    parsed = itp.Parser().parse(text)
    hashtags = {f"#{tag}" for tag in parsed.tags}
    mentions = {f"@{mention}" for mention in parsed.users}

    pattern = "|".join(emojis.union(hashtags).union(mentions))

    text = re.sub(pattern, "", text)

    return len(text.strip()) > 0


def ratelimit_user(user: "User") -> str:
    try:
        return str(user.id)
    except AttributeError:
        raise Exception("Default ratelimiting only supports logged in users")


class CursorException(Exception):
    pass


def record_cost(key: str, value: int):
    """Minimal structured interface to record costs of executing a flask request"""
    if not hasattr(g, "cost"):
        g.cost = {}
    g.cost[key] = value


def get_cost_headers() -> List[Tuple[str, int]]:
    if not hasattr(g, "cost"):
        return []
    headers = []
    for key in sorted(g.cost.keys()):
        headers.append((f"X-Takumi-Cost-{key}", g.cost[key]))
    return headers


def construct_cursor_from_items(
    items: List[str], target_item: Optional[str] = None
) -> Dict[str, Union[int, str]]:
    count = len(items)

    result: Dict[str, Union[int, str]] = {"count": count}

    has_next = count > 0

    if has_next:
        index = items.index(target_item) + 1 if target_item in items else 0
        next_item = items[index % count]
        if count > 1 or next_item != target_item:
            result["next"] = next_item

    return result
