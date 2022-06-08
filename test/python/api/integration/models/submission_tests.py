from takumi.models import Image, Submission, Video
from takumi.utils import uuid4_str


def test_submission_with_single_image_media(gig_factory, db_session):
    gig = gig_factory()
    submission_id = uuid4_str()
    submission = Submission(
        id=submission_id,
        caption="This is my caption",
        media=[Image(url="http://", owner_id=submission_id, owner_type="submission")],
        gig=gig,
    )

    db_session.add(submission)
    db_session.commit()

    assert gig.submission.media[0].url == "http://"


def test_submission_with_single_video_media(gig_factory, db_session):
    gig = gig_factory()
    submission_id = uuid4_str()
    submission = Submission(
        caption="This is my caption",
        media=[
            Video(
                url="http://video",
                thumbnail="http://thumbnail",
                owner_id=submission_id,
                owner_type="submission",
            )
        ],
        gig=gig,
    )

    db_session.add(submission)
    db_session.commit()

    assert gig.submission.media[0].url == "http://video"
    assert gig.submission.media[0].thumbnail == "http://thumbnail"


def test_submission_with_multiple_media(gig_factory, db_session):
    gig = gig_factory()
    submission_id = uuid4_str()
    submission = Submission(
        id=submission_id,
        caption="This is my caption",
        media=[
            Image(url="http://image1", owner_id=submission_id, owner_type="submission", order=1),
            Video(
                url="http://video2",
                thumbnail="http://thumbnail",
                owner_id=submission_id,
                owner_type="submission",
                order=2,
            ),
            Image(url="http://image3", owner_id=submission_id, owner_type="submission", order=3),
        ],
        gig=gig,
    )

    db_session.add(submission)
    db_session.commit()

    assert len(gig.submission.media) == 3

    media = gig.submission.media

    assert media[0].url == "http://image1"
    assert media[1].url == "http://video2"
    assert media[2].url == "http://image3"

    assert isinstance(media[0], Image)
    assert isinstance(media[1], Video)
    assert isinstance(media[2], Image)
