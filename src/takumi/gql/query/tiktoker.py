from takumi.gql import arguments, fields
from takumi.models import TikTokAccount
from takumi.roles import permissions


class TiktokerOrderBy(arguments.Enum):
    digg = "digg"
    likes = "likes"
    videoCount = "video_count"
    medianPlays = "median_plays"
    meanPlays = "mean_plays"
    medianDiggs = "median_diggs"
    meanDiggs = "mean_diggs"
    medianShares = "median_shares"
    meanShares = "mean_shares"
    medianComments = "median_comments"
    meanComments = "mean_comments"


class TiktokerQuery:
    tiktokers = fields.ConnectionField(
        "TiktokerConnection",
        limit=arguments.Int(),
        order_by=TiktokerOrderBy(),
        descending=arguments.Boolean(default_value=True),
        min_followers=arguments.Int(),
        min_videos=arguments.Int(),
    )

    @permissions.access_all_influencers.require()
    def resolve_tiktokers(root, info, **params):
        q = TikTokAccount.query
        if "order_by" in params:
            column = getattr(TikTokAccount, params["order_by"])
            if params["descending"]:
                column = column.desc()
            q = q.order_by(column)

        if "min_followers" in params:
            q = q.filter(TikTokAccount.followers >= params["min_followers"])

        if "min_videos" in params:
            q = q.filter(TikTokAccount.video_count >= params["min_videos"])

        return q
