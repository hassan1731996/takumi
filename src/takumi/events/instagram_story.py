import datetime as dt

from takumi.events import Event, TableLog
from takumi.models import InstagramStoryEvent


class CreateInstagramStory(Event):
    def apply(self, instagram_story):
        instagram_story.gig_id = self.properties["gig_id"]
        instagram_story.followers = self.properties["followers"]


class LinkFrame(Event):
    def apply(self, instagram_story):
        pass


class UnlinkFrame(Event):
    def apply(self, instagram_story):
        story_frame = next(
            s for s in instagram_story.story_frames if s.id == self.properties["story_frame_id"]
        )
        story_frame.instagram_story_id = None


class UnlinkGig(Event):
    def apply(self, instagram_story):
        instagram_story.gig = None


class AddStoryFrames(Event):
    def apply(self, instagram_story):
        pass


class MarkAsPosted(Event):
    def apply(self, instagram_story):
        instagram_story.marked_posted = dt.datetime.now(dt.timezone.utc)


class InstagramStoryLog(TableLog):
    event_model = InstagramStoryEvent
    relation = "instagram_story"
    type_map = {
        "create": CreateInstagramStory,
        "add_story_frames": AddStoryFrames,
        "link_frame": LinkFrame,
        "mark_as_posted": MarkAsPosted,
        "unlink_frame": UnlinkFrame,
        "unlink_gig": UnlinkGig,
    }
