from tasktiger.exceptions import TaskNotFound

from core.tasktiger import MAIN_QUEUE_NAME

from takumi.extensions import tiger
from takumi.models import Influencer

DELETING_QUEUE = f"{MAIN_QUEUE_NAME}.deleting"


def clear_deletion(influencer):
    task = tiger.get_unique_task(delete_influencer, [influencer.id], queue=DELETING_QUEUE)
    try:
        task.cancel()
    except TaskNotFound:
        pass


def schedule_deletion(influencer):
    clear_deletion(influencer)
    tiger.tiger.delay(
        delete_influencer,
        queue=DELETING_QUEUE,
        args=[influencer.id],
        unique=True,
        when=influencer.deletion_date,
    )


@tiger.task(unique=True)
def delete_influencer(id):
    from takumi.services import InfluencerService

    influencer = Influencer.query.get_or_404(id)

    with InfluencerService(influencer) as service:
        service.delete()
