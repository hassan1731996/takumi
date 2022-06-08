import money
from marshmallow import Schema, fields, pre_dump

from core.math.math import round_fractional


def format_currency(amount_field, currency_field, currency_digits=False):
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

    def inner(obj):

        # Support both dict and sqla model dumps
        try:
            amount = getattr(obj, amount_field)
        except AttributeError:
            amount = obj.get(amount_field)

        if not currency_digits:
            amount = int(amount) / 100
        else:
            amount = float(amount) / 100.0

        try:
            currency = getattr(obj, currency_field)
        except AttributeError:
            currency = obj.get(currency_field)

        if currency not in CURRENCY_SETTINGS:
            currency = "GBP"
            amount = 0

        # convert value from 'fractional unit' (ie. pence) to whole currency unit
        value = money.Money(amount, currency)

        settings = CURRENCY_SETTINGS[currency]
        return value.format(
            settings["locale"], pattern=settings["pattern"], currency_digits=currency_digits
        )

    return inner


class CurrencyField(fields.Nested):
    def _serialize(self, value, attr, obj):
        if isinstance(obj, dict):
            currency = obj["currency"]
        else:
            currency = obj.currency
        if currency is None or currency == "":
            currency = "GBP"
            value = 0
        if value is None:
            return None
        return super()._serialize(dict(amount=value, currency=currency), attr, obj)


class MoneySchema(Schema):
    amount = fields.Integer()
    currency = fields.String()
    formatted_amount = fields.Function(format_currency("amount", "currency"))

    @classmethod
    def dump_formatted_amount(cls, amount, currency):
        return cls().dump({"amount": amount, "currency": currency}).data["formatted_amount"]


class FractionalMoneySchema(MoneySchema):
    formatted_amount = fields.Function(format_currency("amount", "currency", currency_digits=True))


class RoundedMoneySchema(MoneySchema):
    """This schema rounds any monetary amount down to the nearest 100"""

    @pre_dump
    def round_off_fractionals(self, item):
        if item.get("amount"):
            rounded, _ = round_fractional(item.get("amount"))
            item["amount"] = int(rounded)
        return item


class AccountSchema(Schema):
    id = fields.UUID()
    balance = CurrencyField(MoneySchema())
    limit = fields.Integer()
    currency = fields.String()
