import pytest


@pytest.fixture
def api_url() -> str:
    return "http://mem0.test"


@pytest.fixture
def api_key() -> str:
    return "test-api-key"
