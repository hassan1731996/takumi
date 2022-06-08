from tasktiger.exceptions import TaskNotFound

from core.tasktiger import MAIN_QUEUE_NAME

from takumi.events.influencer import InfluencerLog
from takumi.extensions import db, tiger
from takumi.models.influencer import STATES as INFLUENCER_STATES
from takumi.models.influencer import Influencer

COOLDOWN_QUEUE = f"{MAIN_QUEUE_NAME}.cooldown"


def clear_cooldown(influencer):
    task = tiger.get_unique_task(end_cooldown, [influencer.id], queue=COOLDOWN_QUEUE)
    try:
        task.cancel()
    except TaskNotFound:
        pass


def schedule_end_cooldown(influencer):
    clear_cooldown(influencer)
    tiger.tiger.delay(
        end_cooldown,
        queue=COOLDOWN_QUEUE,
        args=[influencer.id],
        unique=True,
        when=influencer.cooldown_ends,
    )


@tiger.task(unique=True)
def end_cooldown(id):
    influencer = Influencer.query.get_or_404(id)
    if influencer.state == INFLUENCER_STATES.COOLDOWN:
        log = InfluencerLog(influencer)
        log.add_event("end_cooldown")
    db.session.add(influencer)
    db.session.commit()
