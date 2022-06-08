import datetime as dt

import requests
from exponent_server_sdk import DeviceNotRegisteredError, PushClient, PushMessage
from sentry_sdk import capture_exception
from tasktiger.exceptions import RetryException
from tasktiger.retry import fixed

from core.common.chunks import chunks
from core.common.utils import States
from core.tasktiger import MAIN_QUEUE_NAME

from takumi.extensions import db, tiger
from takumi.models import Device


class TYPES(States):
    NEW_CAMPAIGN = "new_campaign"
    PAYABLE = "payable"
    PAYOUT_FAILED = "payout_failed"
    RECRUIT = "recruit"
    REJECTION = "rejection"
    RESERVATION_REMINDER = "reservation_reminder"
    SETTINGS = "settings"
    RELINK_FACEBOOK = "relink_facebook"


MAX_MESSAGE_COUNT = 100
STAGGER_MINUTES = 5


class NotificationException(Exception):
    def __init__(self, *args, errors=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.errors = errors


class UnknownPlatform(NotificationException):
    pass


class UnparsableToken(NotificationException):
    pass


class NoDeviceException(NotificationException):
    pass


@tiger.task(queue=MAIN_QUEUE_NAME)
def _send_message(tokens, body, data):
    # Message is not available when handling notifications in the
    # foreground, so add body into the data payload as well.
    data["body"] = body

    messages = [
        PushMessage(to=token, body=body, data=data)
        for token in tokens
        if token is not None and token != "removed_token" and not token.endswith("-removed")
    ]
    if not messages:
        return

    # Might raise on connection issues or expo server issues, which will be
    # handled by tiger
    try:
        responses_chunk = PushClient().publish_multiple(messages)
    except requests.exceptions.HTTPError as exc:
        if exc.response and exc.response.status_code >= 500:
            raise RetryException(method=fixed(delay=600, max_retries=5))
        raise exc

    for response in responses_chunk:
        try:
            response.validate_response()
        except DeviceNotRegisteredError:
            token = response.push_message.to
            device = Device.query.filter(Device.device_token == token).first()

            if device is not None:
                device.active = False
                db.session.commit()

        except Exception as exc:
            print(exc)
            capture_exception()


class NotificationClient:
    def __init__(self, devices):
        self.devices = devices

    @classmethod
    def from_influencer(cls, influencer):
        if not influencer.has_device:
            raise NotificationException("Influencer doesn't have a device")
        return cls([influencer.device])

    def __repr__(self):
        return f"<NotificationClient ({len(self.devices)} devices)>"

    def send_message(self, body, data):
        # Chunk message sending to max 100 per chunk, since the expo api only
        # supports max 100 at a time.
        # Each chunk is staggered by 5 minutes, to prevent too much traffic
        # from influencers at the same time when being notified
        when = dt.datetime.now(dt.timezone.utc)
        for chunk in chunks(self.devices, MAX_MESSAGE_COUNT):
            tiger.tiger.delay(
                _send_message,
                args=[[device.device_token for device in chunk], body, data],
                queue=MAIN_QUEUE_NAME,
                unique=True,
                when=when,
            )
            when += dt.timedelta(minutes=STAGGER_MINUTES)

    def build_campaign_payload(self, campaign):
        payload = {"campaign_id": campaign.id}

        if len(campaign.posts) == 1:
            payload["post_id"] = campaign.posts[0].id

        return payload

    def send_relink_facebook(self, message):
        return self.send_message(message, {"type": TYPES.RELINK_FACEBOOK, "payload": {}})

    def send_rejection(self, message, campaign):
        return self.send_message(
            message, {"type": TYPES.REJECTION, "payload": self.build_campaign_payload(campaign)}
        )

    def send_payable(self, message, campaign):
        return self.send_message(
            message, {"type": TYPES.PAYABLE, "payload": self.build_campaign_payload(campaign)}
        )

    def send_payout_failed(self, message, campaign):
        return self.send_message(
            message, {"type": TYPES.PAYOUT_FAILED, "payload": self.build_campaign_payload(campaign)}
        )

    def send_reservation_reminder(self, message, campaign):
        return self.send_message(
            message,
            {"type": TYPES.RESERVATION_REMINDER, "payload": self.build_campaign_payload(campaign)},
        )

    def send_offer(self, offer, message):
        return self.send_message(
            message,
            {"type": TYPES.NEW_CAMPAIGN, "payload": self.build_campaign_payload(offer.campaign)},
        )

    def send_campaign(self, message, campaign, token=None):
        payload = self.build_campaign_payload(campaign)
        payload["token"] = token

        return self.send_message(message, {"type": TYPES.NEW_CAMPAIGN, "payload": payload})

    def send_influencer_push_notification(self, influencer_push_notification, message, token=None):
        # unused
        return self.send_message(
            message,
            {
                "type": TYPES.NEW_CAMPAIGN,
                "payload": {
                    "campaign_id": influencer_push_notification.push_notification.campaign.id,
                    "influencer_push_notification_id": influencer_push_notification.id,
                    "token": token,
                },
            },
        )

    def send_settings(self, message):
        return self.send_message(message, {"type": TYPES.SETTINGS})

    def send_instagram_view_profile(self, username, text):
        message = f"Open to view {username}'s profile"

        return self.send_message(
            message, {"type": TYPES.RECRUIT, "payload": {"username": username, "text": str(text)}}
        )

    def send_instagram_direct_message(self, username, text):
        message = f"Open to send DM to {username}"

        return self.send_message(
            message, {"type": TYPES.RECRUIT, "payload": {"username": username, "text": str(text)}}
        )
