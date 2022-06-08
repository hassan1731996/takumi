# encoding=utf-8
import pytest
from itsdangerous import BadData, BadTimeSignature

from takumi.signers import url_signer
from takumi.views.legacy import get_preview_token


def test_get_preview_token(client):
    token = url_signer.dumps("foo", salt="preview_campaign")
    with client.application.test_request_context("/?token={}".format(token)):
        assert get_preview_token() == "foo"


def test_get_preview_token_bad_salt(client):
    token = url_signer.dumps("foo", salt="bar")
    with client.application.test_request_context("/?token={}".format(token)):
        with pytest.raises(BadTimeSignature):
            get_preview_token()


def test_get_preview_token_no_token(client):
    with client.application.test_request_context("/"):
        assert get_preview_token() is None


def test_get_preview_token_bad_token(client):
    with client.application.test_request_context("/?token=bar"):
        with pytest.raises(BadData):
            get_preview_token()
