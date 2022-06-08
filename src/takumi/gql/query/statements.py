from flask_login import current_user

from takumi.gql import arguments, fields
from takumi.gql.exceptions import QueryException
from takumi.gql.utils import get_influencer_or_404
from takumi.roles import permissions
from takumi.statements import get_statements


class StatementQuery:
    statements_for_influencer = fields.List(
        "Statement", username=arguments.String(description="Developer only: request for username")
    )

    @permissions.influencer.require()
    def resolve_statements_for_influencer(root, info, username=None):
        if username is not None and permissions.developer.can():
            influencer = get_influencer_or_404(username)
        else:
            influencer = current_user.influencer

        if influencer is None:
            raise QueryException("Influencer not found")

        return get_statements(influencer)
