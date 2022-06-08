import os
from contextlib import contextmanager
from typing import Iterator, Optional

import money
from flask import _request_ctx_stack  # type: ignore
from flask_babelex import Domain


def format_currency(amount, currency, currency_digits=False):
    """Currency field formatter

    Expects object.currency_field to contain fractional money value (100 = £1)

    currency_digits parameter controls whether fractional units are displayed,
    if True: 123 = £1.23
    if False: 123 = £1
    (defaults to False)

    """
    CURRENCY_SETTINGS = {
        "EUR": {"locale": "de_DE", "pattern": "#,##0\xa0¤"},
        "GBP": {"locale": "en_GB", "pattern": "¤#,###"},
        "USD": {"locale": "en_US", "pattern": "¤#,###"},
    }

    if currency not in CURRENCY_SETTINGS:
        currency = "GBP"
        amount = 0

    if not currency_digits:
        amount = int(amount) / 100
    else:
        amount = float(amount) / 100.0

    value = money.Money(amount, currency)
    settings = CURRENCY_SETTINGS.get(currency)
    return value.format(
        settings["locale"], pattern=settings["pattern"], currency_digits=currency_digits
    )


domain = Domain(dirname=os.path.join(os.path.dirname(__file__), "translations"))

gettext = domain.gettext
ngettext = domain.ngettext
lazy_gettext = domain.lazy_gettext


class RequestContext:
    babel_locale: Optional[str]


@contextmanager
def locale_context(locale: str) -> Iterator:
    # For a context block, override-then-reset the current locale. Useful if
    # a single request needs to deal with multiple locales, for example when
    # sending push notification to a German user with a request from a logged
    # in admin with English as their locale.
    ctx: Optional[RequestContext] = _request_ctx_stack.top

    if ctx and hasattr(ctx, "babel_locale"):
        current_locale = getattr(ctx, "babel_locale", None)
        ctx.babel_locale = locale
        yield
        ctx.babel_locale = current_locale
    else:
        yield
