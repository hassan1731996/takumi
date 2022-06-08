from graphene import ObjectType

from takumi.gql import arguments, fields
from takumi.gql.db import paginate_query
from takumi.roles import permissions
from takumi.services import InsightService


class InsightUrl(ObjectType):
    year = fields.Int()
    week = fields.Int()

    count = fields.Int()

    url = fields.String()


class InsightQuery:
    insight = fields.Field(
        "InsightInterface",
        id=arguments.UUID(description="The id of the insight"),
        gig_id=arguments.UUID(description="The id of the gig"),
    )
    insights = fields.ConnectionField(
        "InsightConnection",
        processed=arguments.Boolean(description="Filter by processed or not"),
        campaign_id=arguments.UUID(description="Filter by campaign id"),
        post_id=arguments.UUID(description="Filter by post id"),
        mine=arguments.Boolean(description="Filter by insights in my campaigns"),
        region=arguments.UUID(description="Filter by insights by country"),
        offset=arguments.Int(description="Offset for pagination"),
        limit=arguments.Int(description="Limit for pagination"),
    )

    @permissions.team_member.require()
    def resolve_insight(root, info, **args):
        if "id" in args:
            return InsightService.get_by_id(args["id"])
        elif "gig_id" in args:
            return InsightService.get_by_gig_id(args["gig_id"])
        return None

    @permissions.team_member.require()
    def resolve_insights(root, info, **kwargs):
        """Insights resolver that get and filter insights.

        Args:
            root: The graphql self parameter.
            info: Graphql additional info.
            kwargs: Provided filters.

        Returns:
            Filtered and paginated insights.
        """
        query = InsightService.get_insights(kwargs)

        paginated_query = paginate_query(
            query, offset=kwargs.get("offset", 0), limit=kwargs.get("limit", 0)
        )

        return paginated_query
