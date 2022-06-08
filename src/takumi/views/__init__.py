# flake8: noqa

from flask import redirect

from takumi.i18n import gettext as _

from .admin.campaigns import *
from .admin.gigs import *
from .advertisers.user_enrollment import *
from .bank import *
from .blueprint import api
from .countries import *
from .devices import *
from .email_leads import *
from .email_login import *
from .finance import *
from .gql import *
from .legacy import *
from .locations import *
from .logout import *
from .rewards_calculator import *
from .signup import *
from .statements import *
from .status import *
from .task import *
from .users import *
from .webhooks import *


@api.route("/")
def home():
    return "Home"
