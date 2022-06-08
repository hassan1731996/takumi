from takumi.extensions import db
from takumi.models import TiktokPost
from takumi.services import Service
from takumi.services.exceptions import UnlinkGigException


class TiktokPostService(Service):
    SUBJECT = TiktokPost

    @property
    def tiktok_post(self):
        return self.subject

    @staticmethod
    def get_by_id(id):
        return db.session.query(TiktokPost).get(id)

    @classmethod
    def create(cls, gig_id, tiktok_post_id, url):
        from takumi.events.gig import GigLog
        from takumi.services import GigService

        tiktok_post = TiktokPost(tiktok_post_id=tiktok_post_id, gig_id=gig_id, link=url)

        gig = GigService.get_by_id(gig_id)

        gig_log = GigLog(gig)
        gig_log.add_event("mark_as_verified")

        db.session.add(tiktok_post)
        db.session.commit()

        tiktok_post.posted = tiktok_post.created
        db.session.commit()

        return tiktok_post

    def unlink_gig(self):
        from takumi.events.gig import GigLog

        gig = self.tiktok_post.gig
        if not gig:
            raise UnlinkGigException(
                f"<TiktokPost: {self.tiktok_post.id}> has already been unlinked"
            )

        gig_log = GigLog(gig)
        gig_log.add_event("unlink_tiktok_post", {"tiktok_post_id": self.tiktok_post.id})
        self.tiktok_post.gig = None
