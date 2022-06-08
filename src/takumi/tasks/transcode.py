from time import sleep

from core.tasktiger import MAIN_QUEUE_NAME

from takumi.convert import Converter
from takumi.extensions import db, tiger
from takumi.models import Media, Submission

TRANSCODE_QUEUE = f"{MAIN_QUEUE_NAME}.transcode"


class TranscodingError(Exception):
    pass


class TranscodingTimedOut(Exception):
    pass


MAX_WAIT = 600  # seconds
WAIT_INTERVAL = 5  # seconds


@tiger.task(unique=True, queue=TRANSCODE_QUEUE)
def transcode_submission(submission_id):
    """Transcode the media for a submission"""
    submission = Submission.query.get(submission_id)
    if not submission:
        raise Exception("Submission not found")

    videos = [
        media for media in submission.media if media.type == "video" and "-preview" not in media.url
    ]

    if not videos:
        return

    converter = Converter()

    jobs = {media.id: converter.convert_media(media) for media in videos}

    tries = MAX_WAIT / WAIT_INTERVAL
    while tries:
        print("Checking jobs...")
        for media_id, job in jobs.items():
            job_id = job["Id"]
            if job["Status"] == "COMPLETE":
                print(f"{job_id} was already complete")
                continue

            jobs[media_id] = converter.get_job(job_id)
            print(f"{job_id} status: {jobs[media_id]['Status']}")

        if all(job["Status"] == "COMPLETE" for job in jobs.values()):
            break

        if any(job["Status"] == "ERROR" for job in jobs.values()):
            raise TranscodingError()

        print(f"Sleeping for 5 seconds.. {tries} tries left")
        sleep(WAIT_INTERVAL)
        tries -= 1

    if not tries:
        raise TranscodingTimedOut()

    print("Replacing the media urls")
    for media_id, job in jobs.items():
        print(f"Media.id: {media_id}")
        media = Media.query.get(media_id)
        print(f"Old media url: {media.url}")
        new_url = converter.get_preview_output_from_job(job)
        print(f"New media url: {new_url}")

        media.url = new_url

    db.session.commit()
