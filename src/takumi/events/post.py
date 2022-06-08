from takumi.events import ColumnLog, Event, EventApplicationException


class PictureNotFoundException(EventApplicationException):
    pass


class UnableToModifyException(EventApplicationException):
    pass


class PostScheduleException(EventApplicationException):
    pass


class PostTypeImpossibleException(EventApplicationException):
    pass


class Create(Event):
    def apply(self, post):
        post.campaign_id = self.properties["campaign_id"]
        post.post_type = self.properties["post_type"]
        post.conditions = self.properties["conditions"]


class SetArchived(Event):
    def apply(self, post):
        post.archived = self.properties["archived"]


class SetGalleryPhotoCount(Event):
    def apply(self, post):
        post.gallery_photo_count = self.properties["gallery_photo_count"]


class SetInstructions(Event):
    def apply(self, post):
        post.instructions = self.properties["instructions"]


class SetConditions(Event):
    def apply(self, post):
        conditions = []

        mention = self.properties.get("mention")
        if mention is not None:
            if mention.startswith("@"):
                mention = mention[1:]
            if len(mention):
                conditions.append({"type": "mention", "value": mention})

        hashtags = self.properties.get("hashtags")
        if hashtags is not None:
            for hashtag in hashtags:
                if hashtag.startswith("#"):
                    hashtag = hashtag[1:]
                if not len(hashtag):
                    continue
                conditions.append({"type": "hashtag", "value": hashtag})

        swipe_up_link = self.properties.get("swipe_up_link")
        if swipe_up_link is not None and len(swipe_up_link):
            conditions.append({"type": "swipe_up_link", "value": swipe_up_link})

        post.conditions = conditions
        post.start_first_hashtag = self.properties["start_first_hashtag"]


class PostDelCondition(Event):
    def _find_index(self, conditions, id):
        for i, condition in enumerate(conditions):
            if condition["id"] == id:
                return i

    def apply(self, post):
        index = self._find_index(post.conditions, self.properties["id"])
        post.conditions.pop(index)


class SetPostType(Event):
    def apply(self, post):
        post.post_type = self.properties["post_type"]


class SetRequiresReviewBeforePosting(Event):
    def apply(self, post):
        post.requires_review_before_posting = self.properties["requires_review_before_posting"]


class SetSchedule(Event):
    def apply(self, post):
        post.opened = self.properties["opened"]
        post.submission_deadline = self.properties["submission_deadline"]
        post.deadline = self.properties["deadline"]


class SetPrice(Event):
    def apply(self, post):
        post.price = self.properties["price"]


class SetBrief(Event):
    def apply(self, post):
        post.brief = self.properties["brief"]


class PostLog(ColumnLog):
    """The PostLog implements the AOL (append-only-log) logic of
    constructing the post.  The stateful fields stored on a Post
    SQL object are only outside of the `events` log for convenience
    (cache / querying), the true state may always be derived by building
    the object from the event log.

    :param post:  the underlying SQL Post object to work on
    """

    type_map = {
        "create": Create,
        "set_archived": SetArchived,
        "set_brief": SetBrief,
        "set_conditions": SetConditions,
        "set_gallery_photo_count": SetGalleryPhotoCount,
        "set_instructions": SetInstructions,
        "set_post_type": SetPostType,
        "set_price": SetPrice,
        "set_requires_review_before_posting": SetRequiresReviewBeforePosting,
        "set_schedule": SetSchedule,
    }
