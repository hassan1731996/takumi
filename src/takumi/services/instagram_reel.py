from takumi.extensions import db
from takumi.models import InstagramReel
from takumi.services import Service
from takumi.services.exceptions import UnlinkGigException


class InstagramReelService(Service):
    SUBJECT = InstagramReel

    @property
    def instagram_reel(self):
        return self.subject

    @staticmethod
    def get_by_id(id):
        return db.session.query(InstagramReel).get(id)

    @classmethod
    def create(cls, gig_id, instagram_reel_id, url):
        from takumi.events.gig import GigLog
        from takumi.services import GigService

        instagram_reel = InstagramReel(instagram_reel_id=instagram_reel_id, gig_id=gig_id, link=url)

        gig = GigService.get_by_id(gig_id)

        gig_log = GigLog(gig)
        gig_log.add_event("mark_as_verified")

        db.session.add(instagram_reel)
        db.session.commit()

        instagram_reel.posted = instagram_reel.created
        db.session.commit()

        return instagram_reel

    def unlink_gig(self):
        from takumi.events.gig import GigLog

        gig = self.instagram_reel.gig
        if not gig:
            raise UnlinkGigException(
                f"<InstagramReel: {self.instagram_reel.id}> has already been unlinked"
            )

        gig_log = GigLog(gig)
        gig_log.add_event("unlink_instagram_reel", {"instagram_reel_id": self.instagram_reel.id})
        self.instagram_reel.gig = None
