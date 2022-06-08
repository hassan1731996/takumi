from takumi.gql import arguments, fields
from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.base import Mutation
from takumi.gql.utils import get_gig_or_404
from takumi.roles import permissions
from takumi.services import GigService


class TriggerTranscodeSubmission(Mutation):
    """Trigger a transcode submission tiger task"""

    class Arguments:
        gig_id = arguments.UUID(required=True, description="The gig id")

    gig = fields.Field("Gig")

    @permissions.manage_influencers.require()
    def mutate(root, info, gig_id):
        gig = get_gig_or_404(gig_id)

        if not gig.submission:
            raise MutationException("Gig doesn't have a submission")

        if gig.submission.transcoded:
            raise MutationException(
                "Transcode already started. Contact support if it still doesn't work"
            )

        with GigService(gig) as service:
            service.trigger_transcode_submission()

        return TriggerTranscodeSubmission(ok=True, gig=gig)


class TranscodeMutation:
    trigger_transcode_submission = TriggerTranscodeSubmission.Field()
