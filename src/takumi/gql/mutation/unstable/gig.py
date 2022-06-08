from takumi.extensions import db
from takumi.gql import arguments, fields
from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.base import Mutation
from takumi.gql.utils import get_gig_or_404
from takumi.roles import permissions


class SwapGigPosts(Mutation):
    """Swap posts on two gigs"""

    class Arguments:
        gig_1_id = arguments.UUID(required=True, description="The id of the first gig")
        gig_2_id = arguments.UUID(required=True, description="The id of the second gig")
        swap_story = arguments.Boolean(
            default_value=False, description="Whether to swap the Gig.instagram_story as well"
        )
        force = arguments.Boolean(default_value=False, description="Whether to skip any validation")

    gig1 = fields.Field("Gig")
    gig2 = fields.Field("Gig")

    @permissions.developer.require()
    def mutate(root, info, gig_1_id, gig_2_id, swap_story, force):
        gig1 = get_gig_or_404(gig_1_id)
        gig2 = get_gig_or_404(gig_2_id)

        if not force:
            if gig1.offer != gig2.offer:
                raise MutationException("The gigs don't belong to the same offer")

        gig1.post, gig2.post = gig2.post, gig1.post
        if swap_story:
            gig1.instagram_story, gig2.instagram_story = gig2.instagram_story, gig1.instagram_story

        db.session.commit()

        return SwapGigPosts(gig1=gig1, gig2=gig2, ok=True)
