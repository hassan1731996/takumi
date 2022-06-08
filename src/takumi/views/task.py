import datetime as dt
import json
from typing import Any, Dict, Optional, Tuple

import requests
import sentry_sdk
from dateutil.parser import parse as dateutil_parse
from flask import current_app, g, jsonify, request
from sentry_sdk import capture_exception, capture_message

from core.common.exceptions import APIError
from core.payments.dwolla.objects import WebhookEvent
from core.payments.revolut.exceptions import RevolutException
from core.taxid.exceptions import InvalidToken

from takumi import slack
from takumi._boto import connections
from takumi.auth import task
from takumi.events.payment import DwollaPaymentLog, RevolutPaymentLog
from takumi.extensions import db, dwolla, revolut, taxid
from takumi.i18n import format_currency
from takumi.i18n import gettext as _
from takumi.i18n import locale_context
from takumi.models import ApiTask, Config, Payment
from takumi.notifications import NotificationClient
from takumi.services import TaxFormService
from takumi.utils import uuid4_str

from .blueprint import tasks


def _pause_dwolla_payments():
    config = Config.get("PROCESS_DWOLLA_PAYMENTS")
    if config:
        config.value = False
        db.session.commit()
        slack.payments_paused("Dwolla")


def send_failed_payout_push_notification(offer):
    locale_amount = format_currency(offer.reward, offer.campaign.market.currency)
    if offer.influencer.has_device:
        with locale_context(offer.influencer.user.request_locale):
            client = NotificationClient.from_influencer(offer.influencer)
            client.send_payout_failed(
                _(
                    "Payout of %(amount)s failed, please check your bank account details.",
                    amount=locale_amount,
                ),
                offer.campaign,
            )


def _track_balance(provider: str, currency: str, balance: float):
    statsd = current_app.config["statsd"]
    statsd.gauge(f"takumi.finance.{provider}.{currency}.balance", balance)


def _track_revolut_balances() -> None:
    try:
        gbp = revolut.get_account(revolut.account_ids["gbp"])
        _track_balance(provider="revolut", currency="gbp", balance=float(gbp.balance))

        eur = revolut.get_account(revolut.account_ids["eur"])
        _track_balance(provider="revolut", currency="eur", balance=float(eur.balance))
    except Exception:
        capture_exception()


def _track_dwolla_balances() -> None:
    try:
        href = dwolla.account.balance.links["balance"].href
        response = dwolla.api.get(href).body
        balance = response["balance"]

        _track_balance(
            provider="dwolla", currency=balance["currency"].lower(), balance=float(balance["value"])
        )
    except Exception:
        capture_exception()


@tasks.url_defaults
def add_api_task(endpoint, values):
    values.setdefault("task_id", g.api_task.id if getattr(g, "task_id", None) else None)


@tasks.url_value_preprocessor
def pull_api_task(endpoint, values):
    task_id = values.pop("task_id")
    if not hasattr(g, "task"):
        g.task = (
            ApiTask.query.filter(ApiTask.id == task_id).filter(ApiTask.active == True)
        ).first()


def is_success_event(event):
    return event.topic in ("transfer_completed",)


def is_failure_event(event):
    return event.topic in ("transfer_cancelled", "transfer_failed")


def is_event_supported(event):
    return is_success_event(event) or is_failure_event(event)


# TODO: Remove
def _payment_from_gig_id(gig_id):
    from takumi.models import Gig

    gig = Gig.query.get_or_404(gig_id)
    return gig.offer.payment  # XXX: perhaps some more complex querying is required here..


def _remove_facebook_page_flag_override_if_no_active_offers(payment):
    influencer = payment.offer.influencer
    if influencer.active_campaigns.count() == 0:
        if "SHOW_FACEBOOK_LINK_PAGE" in influencer.info:
            del influencer.info["SHOW_FACEBOOK_LINK_PAGE"]
            db.session.commit()


@tasks.route("/dwolla/payout/callback", methods=["POST"])
@task
def dwolla_payout_callback():
    event = WebhookEvent(request.json)
    if not is_event_supported(event):
        slack.dwolla_hook(request.json, title="Unknown webhook topic")
        return jsonify({})

    transfer = dwolla.get_transfer(event.links["resource"])
    if "payment_id" not in transfer.metadata and "gig" not in transfer.metadata:
        slack.dwolla_hook(request.json, title="payment_id or gig_id missing from metadata")
        return jsonify({})

    payment_id = transfer.metadata.get("payment_id")

    # TODO: Remove
    gig_id = transfer.metadata.get("gig")
    if payment_id is None:
        payment = _payment_from_gig_id(gig_id)  # TODO: Remove
    else:
        payment = Payment.query.get(payment_id)

    if transfer.id != payment.reference:
        slack.dwolla_hook(request.json, title="Payout callback reference ID mismatch")
        capture_message(
            "Payout callback from Dwolla ID reference mismatch!",
            event_id=event.id,
            payment=payment,
            transfer=transfer,
            reference=payment.reference,
        )
        return jsonify({})

    log = DwollaPaymentLog(payment)
    if is_success_event(event):
        log.add_event("succeed", request.json)
    elif is_failure_event(event):
        log.add_event("fail", request.json)
        failure = dwolla.get_transfer_failure(transfer)
        slack.payout_failure_dwolla(payment, failure)
        send_failed_payout_push_notification(payment.offer)

        try:
            reason = failure.get("raw_notification", {}).get("reason")
            if reason == "Not enough balance":
                _pause_dwolla_payments()
        except:  # NOQA
            pass

    db.session.add(payment)
    db.session.commit()

    _remove_facebook_page_flag_override_if_no_active_offers(payment)
    _track_dwolla_balances()

    return jsonify({})


@tasks.route("/revolut/auth", methods=["GET"])
@task
def revolut_auth():
    if "code" not in request.values:
        raise APIError("Code missing")

    code = request.values["code"]

    try:
        revolut.authenticate(code)
    except RevolutException as e:
        raise APIError(str(e), 400)

    return "Revolut access refreshed", 200


def _revolut_transaction_created(payment: Payment, payload: Dict) -> None:
    data = payload["data"]
    state = data["state"]

    log = RevolutPaymentLog(payment)

    if state == "pending":
        # Nothing to do, future callback will change state
        return None
    elif state == "failed":
        log.add_event("fail", payload)
        db.session.commit()
        slack.revolut_hook(payload, title=f"Payment failed for {payment.id}")
        send_failed_payout_push_notification(payment.offer)
    elif state == "completed":
        # Synchronous payment
        log.add_event("succeed", payload)
        db.session.commit()
    else:
        # Unexpected state
        slack.revolut_hook(
            payload,
            title=f"Unknown state for created transaction ({state})",
        )


def _revolut_transaction_state_changed(payment: Payment, payload: Dict) -> None:
    # Get the payment by transaction id reference
    data = payload["data"]

    new_state = data["new_state"]
    old_state = data.get("old_state")

    log = RevolutPaymentLog(payment)

    """
    Transactions start as 'pending' (if not synchronous) and transition into
    one of 'completed', 'failed', 'reverted' and 'declined'
    """
    if new_state == "completed":
        log.add_event("succeed", payload)
        db.session.commit()
    elif new_state == "failed":
        log.add_event("fail", payload)
        db.session.commit()
        slack.revolut_hook(payload, title=f"Payment failed for {payment.id}")
        send_failed_payout_push_notification(payment.offer)
    else:
        slack.revolut_hook(
            payload,
            title=f"Unknown transition change ({old_state} -> {new_state})",
        )
        return


@tasks.route("/revolut/payout/callback", methods=["POST"])
@task
def revolut_payout_callback() -> str:
    payload: Dict[str, Any] = request.json
    if "event" not in payload:
        return jsonify({})

    # For debugging, log all events to S3
    try:
        from takumi.slack.channels.revolut import _upload_json_to_s3

        today = dt.datetime.today()
        _upload_json_to_s3(
            bucket=current_app.config["S3_LOG_BUCKET"],
            key=f"payment-callbacks/revolut/{today.year}/{today.month}/{today.day}/{uuid4_str()}",
            data=payload,
        )
    except Exception:
        capture_exception()

    event: Dict = payload["event"]

    # Check if payment is related to Takumi
    data = payload.get("data")
    if not data or "id" not in data:
        return jsonify({})

    payment: Optional[Payment] = Payment.query.filter(Payment.reference == data["id"]).one_or_none()
    if payment is None:
        return jsonify({})

    # Handle state callback for Takumi payment
    if event == "TransactionCreated":
        _revolut_transaction_created(payment, payload)
    elif event == "TransactionStateChanged":
        _revolut_transaction_state_changed(payment, payload)
    else:
        slack.revolut_hook(payload, title="Unknown webhook event")

    _remove_facebook_page_flag_override_if_no_active_offers(payment)
    _track_revolut_balances()

    return jsonify({})


@tasks.route("twilio/callback", methods=["POST"])
@task
def twilio_callback() -> str:
    from_number = request.form.get("From")
    body = request.form.get("Body")

    slack.notify_debug(f"text from {from_number}: {body}")

    return "<Response></Response>"


@tasks.route("taxid", methods=["POST"])
@task
def taxid_callback() -> Tuple[str, int]:
    data = request.json
    form = data["form"]
    slack.notify_debug(f"taxid.pro callback: {data}")

    # Validate signature
    calculated_signature = taxid.calculate_signature(data)
    callback_signature = request.headers.get("Webhook-Signature", "")
    if len(callback_signature) != 64 or calculated_signature != callback_signature:
        return "", 403

    # Get user by reference
    tax_form_id = form.get("reference")

    if tax_form_id == "abc123":
        # A test callback from taxid.pro (used by test_taxid_callback_test_notifies_slack)
        return "", 200

    if not tax_form_id:
        return "", 403

    tax_form = TaxFormService.get_by_id(tax_form_id)
    if not tax_form:
        return "", 404

    # Set signature year as signed
    if "w9" in form:
        signature_date = dateutil_parse(form["w9"]["signatureDate"])
    elif "w8ben" in form:
        signature_date = dateutil_parse(form["w8ben"]["signatureDate"])
    else:
        return "", 422

    with TaxFormService(tax_form) as service:
        service.callback_update(form)

    influencer = tax_form.influencer

    if not influencer.has_w9_info(signature_date.year):
        influencer.w9_tax_years_submitted.append(signature_date.year)
        db.session.add(influencer)
        db.session.commit()
    _upload_to_s3(influencer=influencer, data=data)
    return "", 200


def _upload_to_s3(influencer, data):
    # Store the json payload
    s3 = connections.s3
    date = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H_%M_%S")
    json_path = f"forms/{influencer.id}/{date}.json"

    s3.put_object(
        Bucket=current_app.config["S3_TAXID_BUCKET"],
        Body=json.dumps(data).encode("utf-8"),
        Key=json_path,
        ContentType="application/json",
    )

    # Get PDF and stream it to S3
    try:
        pdf_response = taxid.get_pdf_link(data["form"]["token"])
    except InvalidToken:
        # Capture the exception and move on
        sentry_sdk.capture_exception()
        return

    pdf_path = f"forms/{influencer.id}/{date}.pdf"

    response = requests.get(pdf_response["pdf"], stream=True)
    s3.upload_fileobj(response.raw, current_app.config["S3_TAXID_BUCKET"], pdf_path)


__all__ = ["dwolla_payout_callback"]
