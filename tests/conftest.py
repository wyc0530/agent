import pytest


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    from src.api.main import reset_rate_limits
    reset_rate_limits()