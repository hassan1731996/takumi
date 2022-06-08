from .dev import Development, Local
from .env import overrides, secrets
from .prod import Production
from .test import Testing

development = Development() + secrets + overrides
integration = Development() + secrets + overrides
staging = Development() + secrets + overrides
local = Local() + secrets + overrides
production = Production() + secrets + overrides
testing = Testing() + secrets + overrides
