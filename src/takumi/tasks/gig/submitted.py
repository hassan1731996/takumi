from takumi.extensions import tiger
from takumi.models import Gig
from takumi.validation.errors import ValidationError
from takumi.validation.media import InstagramMediaValidator

from .utils import report_gig


@tiger.task(unique=True)
def gig_check_submitted(gig_id: str) -> None:
    gig: Gig = Gig.query.get_or_404(gig_id)

    if gig.offer.is_claimable:
        return  # if the gig is payable, we can't report it / the window is over

    validator = InstagramMediaValidator.from_gig(gig)
    try:
        validator.validate(gig.instagram_post.ig_post_id)
    except ValidationError:
        # Not optimal, but set report reason to all the error messages
        report_gig(gig, ", ".join([e.message for e in validator.errors]))
