# encoding=utf-8

import mock
import pytest

from takumi.gql.mutation.post import ArchivePost
from takumi.services import PostService


def test_archive_post_archives_post(app, post, campaign, monkeypatch):
    # Arrange
    monkeypatch.setattr(
        "takumi.models.campaign.Campaign.post_count", mock.PropertyMock(return_value=2)
    )
    monkeypatch.setattr("takumi.gql.utils.PostService.get_by_id", mock.Mock(return_value=post))
    monkeypatch.setattr("sqlalchemy.orm.session.SessionTransaction.commit", lambda *args: None)

    # Act
    with mock.patch.object(PostService, "archive") as mock_archive:
        ArchivePost().mutate("info", post.id)

    # Assert
    mock_archive.assert_called_once_with()


#############################################
# Utility functions for tests defined below #
#############################################
@pytest.fixture(autouse=True, scope="module")
def _auto_stub_permission_decorator_required_for_mutations():
    with mock.patch("flask_principal.IdentityContext.can", return_value=True):
        yield
