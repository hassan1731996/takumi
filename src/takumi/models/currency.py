from babel import Locale
from money import Money

CURRENCY_SETTINGS = {
    "EUR": {"locale": "de_DE", "pattern": "#,##0\xa0¤"},
    "GBP": {"locale": "en_GB", "pattern": "¤#,###"},
    "USD": {"locale": "en_US", "pattern": "¤#,###"},
    "ZAR": {"locale": "en_za", "pattern": "¤\xa0#,###"},
}


class Currency:
    __slots__ = "_amount", "_currency", "_currency_digits", "_settings"

    def __init__(self, amount: int = 0, currency: str = "GBP", currency_digits: bool = False):
        """Currency field formatter

        Expects object.currency_field to contain fractional money value (100 = £1)

        currency_digits parameter controls whether fractional units are displayed,
        if True: 123 = £1.23
        if False: 123 = £1
        (defaults to False)
        """
        self._amount = float(amount) / 100.0 if currency_digits else int(amount) / 100
        self._currency = currency
        self._currency_digits = currency_digits
        self._settings = CURRENCY_SETTINGS[currency]

    @property
    def value(self) -> float:
        return self._amount

    @property
    def formatted_value(self) -> str:
        value = Money(self._amount, self._currency)
        return value.format(
            self._settings["locale"],
            pattern=self._settings["pattern"],
            currency_digits=self._currency_digits,
        )

    @property
    def symbol(self) -> str:
        return Locale(self._settings["locale"]).currency_symbols[self._currency]

    @property
    def currency(self) -> str:
        return self._currency

    def __repr__(self) -> str:
        return f"<Currency: {self.formatted_value}>"
