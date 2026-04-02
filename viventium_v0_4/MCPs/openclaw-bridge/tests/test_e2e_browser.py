# VIVENTIUM START
# E2E test for openclaw_browser — requires a running openclaw-bridge server + OpenClaw instance.
# Run with: pytest tests/test_e2e_browser.py -v -m integration
# VIVENTIUM END

import pytest

pytestmark = pytest.mark.integration


class TestE2EBrowser:
    """Placeholder for browser E2E tests.

    Requires running bridge + OpenClaw gateway instance with Playwright available.
    """

    def test_placeholder(self):
        """Browser E2E tests require a live OpenClaw instance."""
        pytest.skip("Browser E2E requires running openclaw-bridge + gateway")
