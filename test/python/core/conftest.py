import pytest
from httmock import HTTMock, all_requests


@pytest.yield_fixture(autouse=True)
def mock_all_requests():
    """A catch-all request mock, to prevent tests from accidentally making requests

    Important: This mock must be below all other HTTMocks, since it's a catch-all
    """

    class TestDoingRequestException(Exception):
        pass

    @all_requests
    def response_content(url, request):
        raise TestDoingRequestException()

    with HTTMock(response_content):
        yield
