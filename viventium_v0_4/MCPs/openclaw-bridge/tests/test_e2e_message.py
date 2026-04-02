# VIVENTIUM START
# E2E test for openclaw_message — requires a running openclaw-bridge server + channel configured.
# Run with: pytest tests/test_e2e_message.py -v -m integration
# VIVENTIUM END

import pytest

pytestmark = pytest.mark.integration


class TestE2EMessage:
    """Placeholder for message E2E tests.

    Requires running bridge + OpenClaw gateway with channels configured.
    """

    def test_placeholder(self):
        """Message E2E tests require running openclaw-bridge + configured channels."""
        pytest.skip("Message E2E requires running openclaw-bridge + channels")
