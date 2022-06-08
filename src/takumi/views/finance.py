from flask import Response, abort
from flask_login import login_required

from takumi.finance.report import get_campaign_month_report_csv
from takumi.roles import permissions
from takumi.views.blueprint import api


@api.route("/_/finance/campaign/report/<int:year>/<int:month>", methods=["GET"])
@login_required
def finance_campaign_report_csv(year: int, month: int) -> Response:
    if not permissions.accounting.can():
        return abort(403)

    with get_campaign_month_report_csv(f"{year}-{month:02}") as data:
        return Response(
            data,
            mimetype="text/csv",
            headers={
                "content-disposition": f"attachment; filename=campaign-report-{year}-{month:02}.csv",
                "content-type": "text/csv",
            },
        )
