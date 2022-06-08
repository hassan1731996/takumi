import ast
import os

import boto3
from dotenv import load_dotenv


def set_secrets_as_env_vars():
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=region_name)
    get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    if "SecretString" in get_secret_value_response:
        secrets = ast.literal_eval(get_secret_value_response["SecretString"])
    else:
        raise KeyError("'SecretString' not found in AWS Secret Manager Response!")
    for secret in secrets:
        os.environ[secret] = secrets[secret]


takumi_server_env = os.environ["TAKUMI_SERVER_ENV"].lower()
if "local" in takumi_server_env.lower() or "test.env" == takumi_server_env.lower():
    print("Loading .env:", takumi_server_env)
    load_dotenv(takumi_server_env)
else:
    region_name = os.environ["AWS_REGION"]
    secret_name = f"takumi-{takumi_server_env}-secrets"
    set_secrets_as_env_vars()
