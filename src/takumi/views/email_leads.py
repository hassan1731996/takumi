import requests
from flask import jsonify, request
from flask_cors import cross_origin
from marshmallow import Schema, fields

from takumi import slack
from takumi.extensions import db
from takumi.models import EmailLead
from takumi.utils import uuid4_str
from takumi.utils.json import get_valid_json

from .blueprint import api

EMAIL_DOMAINS = [
    # Default domains included
    "aol.com",
    "att.net",
    "comcast.net",
    "facebook.com",
    "gmail.com",
    "gmx.com",
    "googlemail.com",
    "google.com",
    "hotmail.com",
    "hotmail.co.uk",
    "mac.com",
    "me.com",
    "mail.com",
    "msn.com",
    "live.com",
    "sbcglobal.net",
    "verizon.net",
    "yahoo.com",
    "yahoo.co.uk",
    # Other global domains
    "email.com",
    "games.com",
    "gmx.net",
    "hush.com",
    "hushmail.com",
    "icloud.com",
    "inbox.com",
    "lavabit.com",
    "love.com",
    "outlook.com",
    "pobox.com",
    "rocketmail.com",
    "safe-mail.net",
    "wow.com",
    "ygm.com",
    "ymail.com",
    "zoho.com",
    "fastmail.fm",
    "yandex.com",
    # United States ISP domains
    "bellsouth.net",
    "charter.net",
    "comcast.net",
    "cox.net",
    "earthlink.net",
    "juno.com",
    # British ISP domains
    "btinternet.com",
    "virginmedia.com",
    "blueyonder.co.uk",
    "freeserve.co.uk",
    "live.co.uk",
    "ntlworld.com",
    "o2.co.uk",
    "orange.net",
    "sky.com",
    "talktalk.co.uk",
    "tiscali.co.uk",
    "virgin.net",
    "wanadoo.co.uk",
    "bt.com",
    # Domains used in Asia
    "sina.com",
    "qq.com",
    "naver.com",
    "hanmail.net",
    "daum.net",
    "nate.com",
    "yahoo.co.jp",
    "yahoo.co.kr",
    "yahoo.co.id",
    "yahoo.co.in",
    "yahoo.com.sg",
    "yahoo.com.ph",
    # French ISP domains
    "hotmail.fr",
    "live.fr",
    "laposte.net",
    "yahoo.fr",
    "wanadoo.fr",
    "orange.fr",
    "gmx.fr",
    "sfr.fr",
    "neuf.fr",
    "free.fr",
    # German ISP domains
    "gmx.de",
    "hotmail.de",
    "live.de",
    "online.de",
    "t-online.de",
    "web.de",
    "yahoo.de",
    # Russian ISP domains
    "mail.ru",
    "rambler.ru",
    "yandex.ru",
    "ya.ru",
    "list.ru",
    # Belgian ISP domains
    "hotmail.be",
    "live.be",
    "skynet.be",
    "voo.be",
    "tvcablenet.be",
    "telenet.be",
    # Argentinian ISP domains
    "hotmail.com.ar",
    "live.com.ar",
    "yahoo.com.ar",
    "fibertel.com.ar",
    "speedy.com.ar",
    "arnet.com.ar",
    # Domains used in Mexico
    "hotmail.com",
    "gmail.com",
    "yahoo.com.mx",
    "live.com.mx",
    "yahoo.com",
    "hotmail.es",
    "live.com",
    "hotmail.com.mx",
    "prodigy.net.mx",
    "msn.com",
]


@api.route("/inbound/<uuid:id>")
def inbound(id):
    email_lead = EmailLead.query.get_or_404(id)
    return jsonify(
        id=email_lead.id,
        email=email_lead.email,
        company=email_lead.company,
        name=email_lead.name,
        job_title=email_lead.job_title,
        phone_number=email_lead.phone_number,
        campaign_ref=email_lead.campaign_ref,
    )


class EmailLeadSourceSchema(Schema):
    first_name = fields.String(required=True)
    last_name = fields.String(required=True)
    job_title = fields.String(required=True)
    company = fields.String(required=True)
    email = fields.Email(required=True)
    phone_number = fields.String(required=True)
    country = fields.String(required=True)
    campaign_ref = fields.String(default="")
    lead_source = fields.String(default="Website")
    hear_about_takumi = fields.String()


@api.route("/email", methods=["POST"])
@cross_origin()
def submit_email_lead():
    form = get_valid_json(EmailLeadSourceSchema(), request)
    company = form["company"]
    country = form["country"]
    email = form["email"]
    job_title = form["job_title"]
    first_name = form["first_name"]
    last_name = form["last_name"]
    phone_number = form["phone_number"]
    campaign_ref = form.get("campaign_ref")
    lead_source = form.get("lead_source")
    hear_about_takumi = form.get("hear_about_takumi")

    name = f"{first_name} {last_name}"
    valued_lead = True

    if EmailLead.query.filter_by(email=email).first():
        valued_lead = False

    lead = EmailLead(
        id=uuid4_str(),
        campaign_ref=campaign_ref,
        company=company,
        email=email,
        job_title=job_title,
        name=name,
        phone_number=phone_number,
    )

    db.session.add(lead)
    db.session.commit()

    valued_lead = True  # Force all leads to go through

    if valued_lead or campaign_ref:
        data = dict(
            company=company,
            country=country,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone_number,
            title=job_title,
            lead_source=lead_source,
            hear_about_takumi=hear_about_takumi,
        )

        slack.email_lead(campaign_ref=campaign_ref, **data)

        response = requests.post(
            "https://webto.salesforce.com/servlet/servlet.WebToLead?encoding=UTF-8",
            data={**data, "00N1i00000240uK": hear_about_takumi, "oid": "00D0Y000001KV4a"},
        )
        response.raise_for_status()

    return jsonify(
        message=f"Thank you {name}. You will be contacted by our sales team.", valued=valued_lead
    )
