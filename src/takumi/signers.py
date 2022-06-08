import os

from itsdangerous import Signer, URLSafeTimedSerializer

url_signer = URLSafeTimedSerializer(os.environ["SECRET_KEY"])
task_signer = Signer(os.environ["SECRET_KEY"])
