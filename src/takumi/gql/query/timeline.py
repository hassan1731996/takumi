from flask_login import current_user

from takumi.gql import arguments, fields
from takumi.gql.exceptions import QueryException
from takumi.gql.utils import get_influencer_or_404, get_post_or_404
from takumi.roles import permissions
from takumi.timeline import influencer_post_step, timeline_for_post


class TimelineQuery:
    timeline_for_post = fields.Field(
        "Timeline",
        post_id=arguments.UUID(description="ID of the post"),
        username=arguments.String(description="Developer only: get as user username"),
    )

    @permissions.influencer.require()
    def resolve_timeline_for_post(root, info, post_id, username=None):
        if username is not None and permissions.developer.can():
            influencer = get_influencer_or_404(username)
        else:
            influencer = current_user.influencer

        if influencer is None:
            raise QueryException("Influencer not found")

        post = get_post_or_404(post_id)

        return {
            "timeline_items": timeline_for_post(post, influencer),
            "post_step": influencer_post_step(post, influencer).name,
        }
