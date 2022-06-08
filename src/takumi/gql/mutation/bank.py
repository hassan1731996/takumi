import re

from flask_login import current_user
from sentry_sdk import capture_exception

from core.payments.revolut.exceptions import RevolutException

from takumi.bank import register_iban, register_uk_account, register_us_account, register_za_account
from takumi.bank.exceptions import BankException, InvalidDetailsException
from takumi.gql import arguments, fields
from takumi.gql.exceptions import MutationException
from takumi.gql.mutation.base import Mutation
from takumi.roles import permissions

REQUIRES_ADDRESS = ["CH"]


class RegisterIban(Mutation):
    """Register a european IBAN account

    This is supported for EU countries that are marked as "usesIban" in the "supportedCountries" query

    An IBAN account is required to pay out any EUR campaigns.
    """

    class Arguments:
        full_name = arguments.String(
            required=True, description="Full name of the bank account holder"
        )
        country_code = arguments.String(
            required=True, description="Two letter country code of the bank account"
        )

        iban = arguments.String(required=True, description="The IBAN of the account")
        bic = arguments.String(required=True, description="The BIC of the account")

    destination_type = fields.String()
    destination_value = fields.String()

    @permissions.influencer.require()
    def mutate(
        root, info, full_name: str, country_code: str, iban: str, bic: str
    ) -> "RegisterIban":
        if permissions.use_takumi_payment.can():
            return RegisterIban(
                ok=True,
                destination_type="takumi",
                destination_value="developer-bank-account",
            )

        country_code = country_code.upper()
        full_name = re.sub(r"\s+", " ", full_name.strip().title())
        iban = iban.upper().replace(" ", "")
        bic = bic.upper().replace(" ", "")

        try:
            if country_code in REQUIRES_ADDRESS:
                address = current_user.influencer.address
                if address is None:
                    raise MutationException(
                        "Address is required for bank accounts in your country. "
                        "Please fill in your shipping address in settings."
                    )
                details = register_iban(
                    full_name=full_name,
                    country_code=country_code,
                    iban=iban,
                    bic=bic,
                    address=address,
                )
            else:
                details = register_iban(
                    full_name=full_name,
                    country_code=country_code,
                    iban=iban,
                    bic=bic,
                )
        except InvalidDetailsException as e:
            raise MutationException(str(e))
        except (BankException, RevolutException):
            capture_exception()  # Log them to sentry
            raise MutationException(
                "Unexpected error while adding payment details, please contact hello@takumi.com"
            )

        return RegisterIban(
            ok=True,
            destination_type=details["destination"]["type"],
            destination_value=details["destination"]["value"],
        )


class RegisterGbAccount(Mutation):
    """Register a Great Britain bank account

    A GB bank account has to have an account number and a sort code.

    A GB account is required to pay out any GBP campaigns.
    """

    class Arguments:
        full_name = arguments.String(
            required=True, description="Full name of the bank account holder"
        )

        account_number = arguments.String(required=True, description="The account number")
        sort_code = arguments.String(required=True, description="The sort code")

    destination_type = fields.String()
    destination_value = fields.String()

    @permissions.influencer.require()
    def mutate(
        root, info, full_name: str, account_number: str, sort_code: str
    ) -> "RegisterGbAccount":
        if permissions.use_takumi_payment.can():
            return RegisterIban(
                ok=True,
                destination_type="takumi",
                destination_value="developer-bank-account",
            )

        full_name = re.sub(r"\s+", " ", full_name.strip().title())

        try:
            details = register_uk_account(
                full_name=full_name,
                country_code="GB",
                account_number=account_number,
                sort_code=sort_code,
            )
        except InvalidDetailsException as e:
            raise MutationException(str(e))
        except (BankException, RevolutException):
            capture_exception()  # Log them to sentry
            raise MutationException(
                "Unexpected error while adding payment details, please contact hello@takumi.com"
            )

        return RegisterGbAccount(
            ok=True,
            destination_type=details["destination"]["type"],
            destination_value=details["destination"]["value"],
        )


class RegisterUsAccount(Mutation):
    """Register a United States bank account

    A US bank account has to have an account number, routing number and an account type.

    A US account is required to pay out any USD campaigns.
    """

    class Arguments:
        full_name = arguments.String(
            required=True, description="Full name of the bank account holder"
        )
        bank_name = arguments.String(
            required=True, description="Name of the bank where the account resides"
        )

        account_number = arguments.String(required=True, description="The account number")
        routing_number = arguments.String(required=True, description="The routing number")
        account_type = arguments.String(required=True, description="The account type")

    destination_type = fields.String()
    destination_value = fields.String()

    @permissions.influencer.require()
    def mutate(
        root,
        info,
        full_name: str,
        bank_name: str,
        account_number: str,
        routing_number: str,
        account_type: str,
    ) -> "RegisterUsAccount":
        if permissions.use_takumi_payment.can():
            return RegisterIban(
                ok=True,
                destination_type="takumi",
                destination_value="developer-bank-account",
            )

        full_name = re.sub(r"\s+", " ", full_name.strip().title())

        try:
            details = register_us_account(
                full_name=full_name,
                bank_name=bank_name,
                account_number=account_number,
                routing_number=routing_number,
                account_type=account_type,
            )
        except InvalidDetailsException as e:
            raise MutationException(str(e))
        except (BankException, RevolutException):
            capture_exception()  # Log them to sentry
            raise MutationException(
                "Unexpected error while adding payment details, please contact hello@takumi.com"
            )

        return RegisterUsAccount(
            ok=True,
            destination_type=details["destination"]["type"],
            destination_value=details["destination"]["value"],
        )


class RegisterZaAccount(Mutation):
    """Register a South African account

    A ZA bank account has to have an account number and a BIC

    A ZA account is required to pay out any ZAR campaigns.
    """

    class Arguments:
        full_name = arguments.String(
            required=True, description="Full name of the bank account holder"
        )

        account_number = arguments.String(required=True, description="The account number")
        bic = arguments.String(required=True, description="The BIC of the account")

    destination_type = fields.String()
    destination_value = fields.String()

    @permissions.influencer.require()
    def mutate(root, info, full_name: str, account_number: str, bic: str) -> "RegisterZaAccount":
        if permissions.use_takumi_payment.can():
            return RegisterIban(
                ok=True,
                destination_type="takumi",
                destination_value="developer-bank-account",
            )

        full_name = re.sub(r"\s+", " ", full_name.strip().title())
        address = current_user.influencer.address
        if address is None:
            raise MutationException(
                "Address is required for South African accounts."
                "Please fill in your shipping address in settings."
            )
        try:
            details = register_za_account(
                full_name=full_name,
                account_number=account_number,
                bic=bic,
                address=address,
            )
        except InvalidDetailsException as e:
            raise MutationException(str(e))
        except (BankException, RevolutException):
            capture_exception()  # Log them to sentry
            raise MutationException(
                "Unexpected error while adding payment details, please contact hello@takumi.com"
            )

        return RegisterZaAccount(
            ok=True,
            destination_type=details["destination"]["type"],
            destination_value=details["destination"]["value"],
        )


class BankMutation:
    register_iban = RegisterIban.Field()
    register_gb_account = RegisterGbAccount.Field()
    register_us_account = RegisterUsAccount.Field()
    register_za_account = RegisterZaAccount.Field()
