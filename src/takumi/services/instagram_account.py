import datetime as dt
import statistics
from typing import List

from sqlalchemy import Integer, func

from takumi.constants import MIN_ANOMALY_FOLLOWER_COUNT
from takumi.events.instagram_account import InstagramAccountLog
from takumi.extensions import db
from takumi.models import InstagramAccount, InstagramAccountEvent
from takumi.services import Service


class InstagramAccountService(Service):
    """
    Represents the business model for InstagramAccount. This isolates the database
    from the application.
    """

    SUBJECT = InstagramAccount
    LOG = InstagramAccountLog

    @property
    def instagram_account(self):
        return self.subject

    # GET
    @staticmethod
    def get_by_id(id):
        return InstagramAccount.query.get(id)

    @staticmethod
    def get_by_ig_id(id):
        return InstagramAccount.query.filter(InstagramAccount.ig_user_id == str(id)).one_or_none()

    @staticmethod
    def get_by_username(username):
        return InstagramAccount.by_username(username)

    @staticmethod
    def get_followers_history(ig_account_id):
        return (
            db.session.query(
                func.date(InstagramAccountEvent.created).label("date"),
                func.min(InstagramAccountEvent.event["followers"].astext.cast(Integer)).label(
                    "min"
                ),
                func.max(InstagramAccountEvent.event["followers"].astext.cast(Integer)).label(
                    "max"
                ),
            )
            .filter(
                InstagramAccountEvent.type == "instagram-update",
                InstagramAccountEvent.instagram_account_id == ig_account_id,
            )
            .group_by(func.date(InstagramAccountEvent.created))
            .order_by(func.date(InstagramAccountEvent.created))
        )

    @staticmethod
    def get_followers_history_anomalies(ig_account_id):
        follower_values = InstagramAccountService.get_followers_history(ig_account_id).all()

        changes = [
            max((second.max or 0) - (first.max or 0), 0)
            for (first, second) in zip(follower_values, follower_values[1:])
        ]
        if len(changes) < 10:
            return []

        mean = statistics.mean(changes)
        std = statistics.stdev(changes)
        ignored_dates = [
            a["date"]
            for a in (InstagramAccountService.get_by_id(ig_account_id).followers_history_anomalies)
            if a["ignore"]
        ]

        return [
            dict(
                date=follower_values[i][0].strftime("%Y-%m-%d"),
                follower_increase=changes[i],
                ignore=follower_values[i][0].strftime("%Y-%m-%d") in ignored_dates,
                anomaly_factor=(val - mean) / std,
            )
            for i, val in enumerate(changes)
            if (val - mean) > 2 * std and val > MIN_ANOMALY_FOLLOWER_COUNT
        ]

    # POST
    @staticmethod
    def create_instagram_account(profile):
        ig_account = InstagramAccount(
            ig_user_id=profile["id"],
            ig_username=profile["username"],
            ig_is_private=profile["is_private"],
            ig_biography=profile["biography"],
            ig_media_id="",
            token="",
            followers=profile["followers"],
            follows=profile["following"],
            media_count=profile["media_count"],
            verified=False,
            profile_picture=profile["profile_picture"],
        )

        db.session.add(ig_account)
        db.session.commit()

        return ig_account

    def dismiss_followers_anomalies(self):
        self.log.add_event("dismiss-followers-anomalies")

    def update_recent_media(self, medias: List) -> None:
        self.log.add_event(
            "update-recent-media", {"recent_media": medias, "now": dt.datetime.now(dt.timezone.utc)}
        )
