from contextlib import contextmanager
from typing import TYPE_CHECKING, Iterator

from takumi.events.campaign import CampaignLog
from takumi.extensions import db, redis

if TYPE_CHECKING:
    from takumi.models import Campaign


@contextmanager
def campaign_reserve_state(campaign: "Campaign") -> Iterator[bool]:
    with redis.get_lock(f"campaign-{campaign.id}"):
        reserved: bool = campaign.is_fully_reserved()

        yield reserved

        was_reserved = reserved
        is_reserved = campaign.is_fully_reserved()
        if was_reserved != is_reserved:
            log = CampaignLog(campaign)
            if is_reserved:
                # Is now fully reserved
                log.add_event("full")
            else:
                # Is now not reserved
                log.add_event("not_full")
            db.session.add(campaign)
            db.session.commit()
