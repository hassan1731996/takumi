from takumi.events import Event, TableLog
from takumi.models import InstagramPostEvent


class CreateInstagramPost(Event):
    def apply(self, instagram_post):
        instagram_post.gig_id = self.properties["gig_id"]
        instagram_post.gig.post_serialized = self.properties["post"]
        instagram_post.caption = self.properties["caption"]
        instagram_post.shortcode = self.properties["shortcode"]
        instagram_post.ig_post_id = self.properties["ig_post_id"]
        instagram_post.link = self.properties["link"]
        instagram_post.deleted = self.properties["deleted"]
        instagram_post.sponsors = self.properties["sponsors"]
        instagram_post.likes = self.properties["likes"]
        instagram_post.comments = self.properties["comments"]
        instagram_post.posted = self.properties["posted"]
        instagram_post.followers = self.properties["followers"]
        instagram_post.video_views = self.properties["video_views"]
        instagram_post.scraped = self.properties["scraped"]


class SetCaption(Event):
    def apply(self, instagram_post):
        instagram_post.caption = self.properties["caption"]


class SetComments(Event):
    def apply(self, instagram_post):
        instagram_post.comments = self.properties["comments"]


class SetFollowers(Event):
    def apply(self, instagram_post):
        instagram_post.followers = self.properties["followers"]


class SetIsDeleted(Event):
    def apply(self, instagram_post):
        instagram_post.deleted = self.properties["deleted"]


class SetLikes(Event):
    def apply(self, instagram_post):
        instagram_post.likes = self.properties["likes"]


class SetMediaUrl(Event):
    def apply(self, instagram_post):
        media = next(m for m in instagram_post.media if m.id == self.properties["media_id"])
        media.url = self.properties["url"]


class SetMediaThumbnail(Event):
    def apply(self, instagram_post):
        media = next(m for m in instagram_post.media if m.id == self.properties["media_id"])
        media.thumbnail = self.properties["thumbnail"]


class SetScraped(Event):
    def apply(self, instagram_post):
        instagram_post.scraped = self.properties["scraped"]


class SetSentiment(Event):
    def apply(self, instagram_post):
        instagram_post.sentiment = self.properties["sentiment"]


class SetVideoViews(Event):
    def apply(self, instagram_post):
        instagram_post.video_views = self.properties["video_views"]


class UnlinkGig(Event):
    def apply(self, instagram_post):
        instagram_post.gig = None


class InstagramPostLog(TableLog):
    event_model = InstagramPostEvent
    relation = "instagram_post"
    type_map = {
        "create": CreateInstagramPost,
        "set_caption": SetCaption,
        "set_comments": SetComments,
        "set_followers": SetFollowers,
        "set_is_deleted": SetIsDeleted,
        "set_likes": SetLikes,
        "set_media_thumbnail": SetMediaThumbnail,
        "set_media_url": SetMediaUrl,
        "set_scraped": SetScraped,
        "set_sentiment": SetSentiment,
        "set_video_views": SetVideoViews,
        "unlink_gig": UnlinkGig,
    }
