import pytest

from takumi.services.exceptions import PaymentAuthorizationSlugNotFoundException
from takumi.services.payment_authorization import PaymentAuthorizationService


def test_payment_authorization_service_create_fails_for_invalid_slugs(db_influencer):
    with pytest.raises(PaymentAuthorizationSlugNotFoundException):
        PaymentAuthorizationService.create(db_influencer.id, "invalid-slug")
