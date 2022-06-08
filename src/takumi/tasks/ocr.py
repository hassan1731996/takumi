from core.tasktiger import MAIN_QUEUE_NAME

from takumi.extensions import db, tiger
from takumi.models import AudienceInsight, PostInsight
from takumi.models.audience_insight import STATES as AUDIENCE_INSIGHT_STATES
from takumi.services import AudienceInsightService, InsightService

OCR_QUEUE = f"{MAIN_QUEUE_NAME}.ocr"


@tiger.task(unique=True, lock_key="textract", queue=OCR_QUEUE)
def analyse_post_insight(insight_id):
    """Run textract OCR analysis on the insights"""

    insight = PostInsight.query.get(insight_id)
    if not insight:
        raise Exception("Insight not found")

    if len(insight.media) > 10:
        return

    try:
        with InsightService(insight) as service:
            service.run_ocr()
    except Exception:
        pass


@tiger.task(unique=True, lock_key="textract", queue=OCR_QUEUE)
def analyse_audience_insight(insight_id):
    insight = AudienceInsight.query.get(insight_id)

    if not insight:
        raise Exception("Audience insights not found")

    try:
        with AudienceInsightService(insight) as service:
            service.run_ocr()
    except Exception as e:
        insight.state = AUDIENCE_INSIGHT_STATES.INVALID
        db.session.commit()
        raise e
