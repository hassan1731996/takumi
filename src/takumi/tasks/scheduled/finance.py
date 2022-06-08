from flask import current_app
from tasktiger.schedule import periodic

from takumi.extensions import dwolla, revolut, tiger


@tiger.scheduled(periodic(hours=1))
def update_finance() -> None:
    statsd = current_app.config["statsd"]

    # Revolut GBP
    gbp = revolut.get_account(revolut.account_ids["gbp"])
    statsd.gauge("takumi.finance.revolut.gbp.balance", gbp.balance)

    # Revolut EUR
    eur = revolut.get_account(revolut.account_ids["eur"])
    statsd.gauge("takumi.finance.revolut.eur.balance", eur.balance)

    # Dwolla USD
    href = dwolla.account.balance.links["balance"].href
    response = dwolla.api.get(href).body
    usd_balance = response["balance"]
    statsd.gauge("takumi.finance.dwolla.usd.balance", float(usd_balance["value"]))
