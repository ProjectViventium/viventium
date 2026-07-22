from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LIBRECHAT_ROOT = REPO_ROOT / "viventium_v0_4" / "LibreChat"


def read(relative: str) -> str:
    return (LIBRECHAT_ROOT / relative).read_text(encoding="utf-8")


def test_express_account_setup_survives_registration_and_login_boundaries() -> None:
    native_proxy = (REPO_ROOT / "scripts/viventium/native_runtime_proxy.js").read_text(
        encoding="utf-8"
    )
    registration = read("client/src/components/Auth/Registration.tsx")
    auth_context = read("client/src/hooks/AuthContext.tsx")
    redirect_utils = read("client/src/utils/redirect.ts")
    account_settings = read("client/src/components/Nav/AccountSettings.tsx")
    connected_accounts = read("client/src/common/connectedAccounts.ts")

    assert "location.href='/login?redirect_to=%2Fc%2Fnew%3Fsetup%3Daccounts'" in native_proxy
    assert "/login?setup=accounts" not in native_proxy
    assert "'/c/new?setup=accounts'" in registration
    assert "getPostLoginRedirect(searchParams)" in auth_context
    assert "persistRedirectToSession" in redirect_utils
    assert "shouldResumeConnectedAccountsSetup" in account_settings
    assert "shouldOpenConnectedAccountsSetup" in connected_accounts


def test_connected_account_retries_are_attempt_scoped_and_close_successful_popups() -> None:
    connected_accounts = read(
        "client/src/components/Nav/SettingsTabs/Account/ConnectedAccounts.tsx"
    )

    assert "flowAttemptsRef" in connected_accounts
    assert "isCurrentFlowAttempt(provider.slug, attempt)" in connected_accounts
    assert "invalidateFlowAttempt(provider.slug)" in connected_accounts
    assert "clearPopupWindow(provider.slug)" in connected_accounts
    assert "pollForConnectedKey(provider, attempt)" in connected_accounts


def test_connected_account_oauth_origin_never_falls_back_to_request_host() -> None:
    route = read("api/server/routes/connectedAccounts.js")
    route_tests = read("api/server/routes/__tests__/connectedAccounts.spec.js")

    assert "req.get('host')" not in route
    assert "Missing ${CONNECTED_ACCOUNTS_RETURN_ORIGIN_ENV} or DOMAIN_SERVER" in route
    assert "untrusted.example" in route_tests
