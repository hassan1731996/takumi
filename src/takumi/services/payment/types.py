from typing import TypedDict


# Alternative definition of TypedDict because of key using builtin "type"
class DestinationDict(TypedDict):
    type: str
    value: str


class PaymentDataDict(TypedDict):
    destination: DestinationDict
