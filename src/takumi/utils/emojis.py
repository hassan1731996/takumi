from typing import List

import regex
from emoji import UNICODE_EMOJI_ALIAS_ENGLISH


def find_emojis(text: str) -> List[str]:
    """Return all emojis from a string

    Utilised the regex library, which is an extension on the built in re
    library and knows how to handle invisible joiners used in emojis, such as
    the family emoji, which is 3-4 emojis combined with invisible joiners
    """
    return [char for char in regex.findall(r"\X", text) if char in UNICODE_EMOJI_ALIAS_ENGLISH]


def remove_emojis(text: str) -> str:
    """Returns the string without any emojis in it"""
    return "".join(
        [char for char in regex.findall(r"\X", text) if char not in UNICODE_EMOJI_ALIAS_ENGLISH]
    )
