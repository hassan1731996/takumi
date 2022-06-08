from takumi.gql import arguments
from takumi.models.offer import STATES as OFFER_STATES

OfferState = type(
    "OfferState", (arguments.Enum,), {param: param for param in OFFER_STATES.values()}
)

RevokeOfferState = type(
    "RevokeOfferState",
    (arguments.Enum,),
    {
        param: param
        for param in [
            OFFER_STATES.INVITED,
            OFFER_STATES.ACCEPTED,
            OFFER_STATES.REQUESTED,
            OFFER_STATES.APPROVED_BY_BRAND,
        ]
    },
)
