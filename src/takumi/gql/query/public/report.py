from takumi.gql import arguments, fields
from takumi.models import Campaign
from takumi.roles import permissions


class ReportQuery:
    report = fields.Field("Report", token=arguments.UUID(required=True))

    @permissions.public.require()
    def resolve_report(root, info, token):
        info.context["token"] = token
        return dict(campaign=Campaign.query.filter(Campaign.report_token == token).one_or_none())
