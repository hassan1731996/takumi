from takumi.audit import AuditClient, AuditDisabled, AuditTryLater
from takumi.gql import arguments, fields
from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.base import Mutation
from takumi.gql.utils import get_influencer_or_404
from takumi.roles import permissions


class GetFreshAudit(Mutation):
    """Get a fresh influencer audit, creating one if it doesnt exist"""

    class Arguments:
        username = arguments.String(required=True, description="The influencer username")

    audit = fields.Field("Audit")
    influencer = fields.Field("Influencer")

    @permissions.manage_influencers.require()
    def mutate(root, info, username):
        influencer = get_influencer_or_404(username)

        try:
            audit = AuditClient().get_fresh_influencer_audit(influencer)
        except AuditTryLater as e:
            if e.ttl <= 60:
                time = f"{e.ttl} seconds"
            else:
                time = "{} minutes".format(e.ttl / 60)

            raise MutationException(f"Audit not ready, try again in {time}")
        except AuditDisabled:
            raise MutationException("Hypeauditor audits are disabled right now")

        return GetFreshAudit(audit=audit, influencer=influencer, ok=True)


class AuditMutation:
    get_fresh_audit = GetFreshAudit.Field()
