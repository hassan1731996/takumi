import datetime as dt
from typing import List, Optional

from takumi.extensions import db
from takumi.models import InstagramPostComment
from takumi.sentiment import Sentiment
from takumi.services import Service
from takumi.services.exceptions import InstagramPostNotFoundException


class InstagramPostCommentService(Service):
    """
    Represents the business model for InstagramPost. This isolates the database
    from the application.
    """

    SUBJECT = InstagramPostComment

    @property
    def instagram_post_comment(self) -> InstagramPostComment:
        return self.subject

    # GET
    @staticmethod
    def get_by_id(id) -> Optional[InstagramPostComment]:
        return InstagramPostComment.query.get(id)

    @staticmethod
    def get_by_ig_comment_id(id) -> Optional[InstagramPostComment]:
        return InstagramPostComment.query.filter(
            InstagramPostComment.ig_comment_id == id
        ).one_or_none()

    # POST
    @staticmethod
    def create(
        ig_comment_id: str,
        username: str,
        text: str,
        instagram_post_id: str,
        hashtags: List[str],
        emojis: List[str],
        scraped: dt.datetime,
    ) -> InstagramPostComment:
        from takumi.services.instagram_post import InstagramPostService

        instagram_post = InstagramPostService.get_by_id(instagram_post_id)
        if instagram_post is None:
            raise InstagramPostNotFoundException(
                f"InstagramPost with id {instagram_post_id} not found"
            )

        instagram_post_comment = InstagramPostComment(
            ig_comment_id=ig_comment_id,
            username=username,
            text=text,
            instagram_post=instagram_post,
            hashtags=hashtags,
            emojis=emojis,
            scraped=scraped,
        )

        db.session.add(instagram_post_comment)
        db.session.commit()

        return instagram_post_comment

    # PUT
    def update_sentiment(self, sentiment: Sentiment) -> None:
        self.instagram_post_comment.sentiment_type = sentiment.sentiment
        self.instagram_post_comment.sentiment_language_code = sentiment.language_code
        self.instagram_post_comment.sentiment_positive_score = sentiment.positive_score
        self.instagram_post_comment.sentiment_neutral_score = sentiment.neutral_score
        self.instagram_post_comment.sentiment_negative_score = sentiment.negative_score
        self.instagram_post_comment.sentiment_mixed_score = sentiment.mixed_score
        self.instagram_post_comment.sentiment_checked = True

    def set_sentiment_checked(self, checked: bool = True) -> None:
        self.instagram_post_comment.sentiment_checked = checked

    def set_instagram_post(self, instagram_post_id: str) -> None:
        if self.instagram_post_comment.instagram_post_id != instagram_post_id:
            self.instagram_post_id = instagram_post_id
