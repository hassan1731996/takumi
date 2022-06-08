from takumi.briefs import TEMPLATES
from takumi.gql import arguments, fields
from takumi.gql.db import filter_posts
from takumi.models import Post
from takumi.roles import permissions


class PostQuery:
    post = fields.Field("Post", id=arguments.UUID(required=True))
    post_history = fields.ConnectionField("PostHistoryConnection", id=arguments.UUID(required=True))
    post_brief_templates = fields.List("BriefTemplate")

    @permissions.public.require()
    def resolve_post(root, info, id):
        query = filter_posts()
        post = query.filter(Post.id == id).one_or_none()

        if post is None:
            from takumi.gql.utils import get_post_for_public_campaign

            post = get_post_for_public_campaign(id)

        return post

    @permissions.public.require()
    def resolve_post_history(root, info, id):
        query = filter_posts()
        post = query.filter(Post.id == id).one_or_none()
        if post is None:
            return None
        results = sorted(post.events + post.gig_events, key=lambda r: r["_created"], reverse=True)
        return results

    @permissions.team_member.require()
    def resolve_post_brief_templates(root, info):
        return TEMPLATES
