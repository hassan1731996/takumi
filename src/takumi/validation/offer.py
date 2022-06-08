from takumi.models.post import PostTypes
from takumi.validation.errors import (
    GigMissingError,
    MediaMissingError,
    MultipleErrorsError,
    ValidationError,
)
from takumi.validation.media import InstagramMediaValidator


class OfferValidator:
    def __init__(self, offer):
        self.offer = offer
        self.errors = []

    def validate(self):
        """Validate a single offer

        Verify that each valid gig in the offer is valid
        """

        for post, gig in self.offer.iter_post_gigs():
            if gig is None:
                self.errors.append(GigMissingError(post))
                continue
            if gig.post.post_type == PostTypes.story:
                continue
            if gig.instagram_post is None:
                self.errors.append(MediaMissingError(gig))
                continue

            validator = InstagramMediaValidator.from_gig(gig)
            try:
                validator.validate(gig.instagram_post.ig_post_id)
            except ValidationError:
                self.errors += validator.errors

        if len(self.errors):
            raise MultipleErrorsError(self.errors)
