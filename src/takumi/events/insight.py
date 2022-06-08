from takumi.events import Event, TableLog
from takumi.models import Image, InsightEvent
from takumi.models.insight import STATES as INSIGHT_STATES


class CreateInsight(Event):
    def apply(self, insight):
        pass


class AddMedia(Event):
    end_state = INSIGHT_STATES.SUBMITTED

    def apply(self, insight):
        for url in self.properties["urls"]:
            insight.media.append(
                Image(url=url, owner_type=insight.__tablename__, owner_id=insight.id)
            )


class RemoveMedia(Event):
    end_state = INSIGHT_STATES.REQUIRES_RESUBMIT

    def apply(self, insight):
        pass


class SetReach(Event):
    def apply(self, insight):
        insight.reach = self.properties["reach"]


class SetNonFollowersReach(Event):
    def apply(self, insight):
        insight.non_followers_reach = self.properties["non_followers_reach"]


class SetViews(Event):
    def apply(self, insight):
        insight.views = self.properties["views"]


class SetReplies(Event):
    def apply(self, insight):
        insight.replies = self.properties["replies"]


class SetImpressions(Event):
    def apply(self, insight):
        insight.impressions = self.properties["impressions"]


class SetLinkClicks(Event):
    def apply(self, insight):
        insight.link_clicks = self.properties["link_clicks"]


class SetStickerTaps(Event):
    def apply(self, insight):
        insight.sticker_taps = self.properties["sticker_taps"]


class SetBackNavigations(Event):
    def apply(self, insight):
        insight.back_navigations = self.properties["back_navigations"]


class SetForwardNavigations(Event):
    def apply(self, insight):
        insight.forward_navigations = self.properties["forward_navigations"]


class SetNextStoryNavigations(Event):
    def apply(self, insight):
        insight.next_story_navigations = self.properties["next_story_navigations"]


class SetExitedNavigations(Event):
    def apply(self, insight):
        insight.exited_navigations = self.properties["exited_navigations"]


class SetLikes(Event):
    def apply(self, insight):
        insight.likes = self.properties["likes"]


class SetComments(Event):
    def apply(self, insight):
        insight.comments = self.properties["comments"]


class SetShares(Event):
    def apply(self, insight):
        insight.shares = self.properties["shares"]


class SetBookmarks(Event):
    def apply(self, insight):
        insight.bookmarks = self.properties["bookmarks"]


class SetCalls(Event):
    def apply(self, insight):
        insight.calls = self.properties["calls"]


class SetEmails(Event):
    def apply(self, insight):
        insight.emails = self.properties["emails"]


class SetGetDirections(Event):
    def apply(self, insight):
        insight.get_directions = self.properties["get_directions"]


class SetProfileVisits(Event):
    def apply(self, insight):
        insight.profile_visits = self.properties["profile_visits"]


class SetWebsiteClicks(Event):
    def apply(self, insight):
        insight.website_clicks = self.properties["website_clicks"]


class SetFollows(Event):
    def apply(self, insight):
        insight.follows = self.properties["follows"]


class SetFromHashtagsImpressions(Event):
    def apply(self, insight):
        insight.from_hashtags_impressions = self.properties["from_hashtags_impressions"]


class SetFromHomeImpressions(Event):
    def apply(self, insight):
        insight.from_home_impressions = self.properties["from_home_impressions"]


class SetFromExploreImpressions(Event):
    def apply(self, insight):
        insight.from_explore_impressions = self.properties["from_explore_impressions"]


class SetFromProfileImpressions(Event):
    def apply(self, insight):
        insight.from_profile_impressions = self.properties["from_profile_impressions"]


class SetFromOtherImpressions(Event):
    def apply(self, insight):
        insight.from_other_impressions = self.properties["from_other_impressions"]


class SetFromLocationImpressions(Event):
    def apply(self, insight):
        insight.from_location_impressions = self.properties["from_location_impressions"]


class RequestResubmitInsight(Event):
    end_state = INSIGHT_STATES.REQUIRES_RESUBMIT

    def apply(self, insight):
        pass


class ApproveInsight(Event):
    end_state = INSIGHT_STATES.APPROVED

    def apply(self, insight):
        pass


class SetOcrValues(Event):
    def apply(self, insight):
        insight.ocr_values = self.properties["values"]


class InsightLog(TableLog):
    event_model = InsightEvent
    relation = "insight"
    type_map = {
        "add_media": AddMedia,
        "approve": ApproveInsight,
        "create": CreateInsight,
        "remove_media": RemoveMedia,
        "request_resubmit": RequestResubmitInsight,
        "set_back_navigations": SetBackNavigations,
        "set_bookmarks": SetBookmarks,
        "set_calls": SetCalls,
        "set_comments": SetComments,
        "set_emails": SetEmails,
        "set_exited_navigations": SetExitedNavigations,
        "set_follows": SetFollows,
        "set_forward_navigations": SetForwardNavigations,
        "set_from_explore_impressions": SetFromExploreImpressions,
        "set_from_hashtags_impressions": SetFromHashtagsImpressions,
        "set_from_home_impressions": SetFromHomeImpressions,
        "set_from_location_impressions": SetFromLocationImpressions,
        "set_from_other_impressions": SetFromOtherImpressions,
        "set_from_profile_impressions": SetFromProfileImpressions,
        "set_get_directions": SetGetDirections,
        "set_impressions": SetImpressions,
        "set_likes": SetLikes,
        "set_link_clicks": SetLinkClicks,
        "set_next_story_navigations": SetNextStoryNavigations,
        "set_non_followers_reach": SetNonFollowersReach,
        "set_ocr_values": SetOcrValues,
        "set_profile_visits": SetProfileVisits,
        "set_reach": SetReach,
        "set_replies": SetReplies,
        "set_shares": SetShares,
        "set_sticker_taps": SetStickerTaps,
        "set_views": SetViews,
        "set_website_clicks": SetWebsiteClicks,
    }
