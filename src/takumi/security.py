import hashlib

import requests
from sentry_sdk import capture_exception

API_URL = "https://api.pwnedpasswords.com/range/{first5}"


def check_if_password_leaked(password: str) -> bool:
    """Check if a password has been reported as leaked on haveibeenpwned.com"""

    digest = hashlib.sha1(password.encode("utf-8")).hexdigest()
    first5, rest = digest[:5], digest[5:]

    response = requests.get(API_URL.format(first5=first5))

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError:
        # Just capture the exception and move on without blocking
        capture_exception()
        return False

    results = response.text.split()

    for result in results:
        match, count = result.split(":")
        if rest.lower() == match.lower():
            return True
    return False
