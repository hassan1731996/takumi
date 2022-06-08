from typing import List

from sqlalchemy import or_

from takumi.extensions import db
from takumi.gql import arguments, fields
from takumi.gql.mutation.base import Mutation
from takumi.models import EmailLogin
from takumi.roles import permissions


class DisableUser(Mutation):
    """Disable user access on the admin"""

    class Arguments:
        username = arguments.String(
            required=True,
            description="The username part of the email. foo@takumi.com requires 'foo'",
        )
        dry = arguments.Boolean(
            description="Whether a dry run, use first to check what will be disabled!",
            default_value=True,
        )

    disabled_emails = fields.List(fields.String)
    dry_run = fields.Boolean()

    @permissions.developer.require()
    def mutate(root, info, username: str, dry: bool = True) -> "DisableUser":
        disabled_emails: List[str] = []

        q = EmailLogin.query.filter(
            or_(
                EmailLogin.email == f"{username}@takumi.com",
                EmailLogin.email.ilike(f"{username}+%@takumi.com"),
            ),
        )

        em: EmailLogin
        for em in q:
            disabled_emails.append(em.email)
            if not dry:
                em.user.active = False
        if not dry:
            db.session.commit()

        return DisableUser(ok=True, disabled_emails=disabled_emails, dry_run=dry)
