from takumi.extensions import tiger
from takumi.instagram_account import (
    create_or_get_instagram_account_by_username,
    refresh_instagram_account,
)


@tiger.task(unique=True)
def refresh_mention_ig_metadata(mention):
    account = create_or_get_instagram_account_by_username(mention)
    if account is not None:
        refresh_instagram_account(account)
