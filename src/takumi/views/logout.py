from flask import redirect, url_for
from flask_login import login_required, logout_user

from .blueprint import api


@api.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("api.home"))
