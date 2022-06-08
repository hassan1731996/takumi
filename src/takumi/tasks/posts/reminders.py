import datetime as dt

from tasktiger import TaskNotFound

from core.tasktiger import MAIN_QUEUE_NAME

from takumi.extensions import tiger
from takumi.models import Influencer, Offer, Post
from takumi.models.offer import STATES as OFFER_STATES
from takumi.models.post import Reminder
from takumi.notifications import NotificationClient

REMINDER_QUEUE = f"{MAIN_QUEUE_NAME}.reminder"


def clear_reminders(post: Post) -> None:
    for reminder in post.get_reminder_schedule:
        task = tiger.get_unique_task(
            task_tiger_reminders, [post.id, reminder.label], queue=REMINDER_QUEUE
        )
        try:
            task.cancel()
        except TaskNotFound:
            pass


def get_reminder_task(post: Post, reminder: Reminder):
    if reminder.date is None:
        return
    if reminder.date < dt.datetime.now(dt.timezone.utc):
        return
    task = tiger.get_unique_task(
        task_tiger_reminders, [post.id, reminder.label], queue=REMINDER_QUEUE
    )
    return task


def schedule_post_reminders(post: Post) -> None:
    clear_reminders(post)
    for reminder in post.get_reminder_schedule:
        task = get_reminder_task(post=post, reminder=reminder)
        if task is not None:
            task.delay(when=reminder.date)


def verify_reminder_for_influencer(post: Post, influencer: Influencer, reminder: Reminder) -> str:
    from takumi.gql.utils import influencer_post_step

    post_step = influencer_post_step(post, influencer)
    return reminder.condition(post_step)


@tiger.task()
def task_tiger_reminders(post_id: str, label: str) -> None:
    post = Post.query.get(post_id)
    if post is None:
        return
    reminder = next((r for r in post.get_reminder_schedule if r.label == label))
    offers = Offer.query.filter(
        Offer.campaign == post.campaign, Offer.state == OFFER_STATES.ACCEPTED
    )
    for offer in offers:
        if verify_reminder_for_influencer(post, offer.influencer, reminder):
            message = reminder.message
            if offer.influencer.has_device:
                client = NotificationClient.from_influencer(offer.influencer)
                client.send_campaign(message, post.campaign)
    return
