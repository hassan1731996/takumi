from marshmallow import Schema, fields


def format_percent(value_field):
    """Value field formatter

    Excepts object.value to contain percent value between 0.00 and 1.00
    """

    def inner(obj):

        # Support both dict and sqla model dumps
        try:
            value = getattr(obj, value_field)
        except AttributeError:
            value = obj.get(value_field)

        if value is None:
            return "N/A"

        value = float(value)
        # Convert from fraction (ie. 0.1234) to percentage (12.34%)
        return "{:.2f}%".format(value * 100)

    return inner


class PercentSchema(Schema):
    value = fields.Float()
    formatted_value = fields.Function(format_percent("value"))
