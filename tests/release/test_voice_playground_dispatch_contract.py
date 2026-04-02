from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP_FILE = ROOT / "viventium_v0_4" / "agent-starter-react" / "components" / "app" / "app.tsx"
ROUTE_FILE = (
    ROOT / "viventium_v0_4" / "agent-starter-react" / "app" / "api" / "connection-details" / "route.ts"
)


def test_playground_client_merges_deeplink_token_options_into_connection_details_request() -> None:
    content = APP_FILE.read_text()

    assert "getConnectionDetailsTokenSource(\n  fallbackOptions?: AgentTokenOptions" in content
    assert "const mergedOptions = {" in content
    assert "...(fallbackOptions ?? {})," in content
    assert "...(options ?? {})," in content
    assert "body: JSON.stringify(mergedOptions)" in content
    assert ": getConnectionDetailsTokenSource(tokenOptions);" in content


def test_connection_details_route_recovers_agent_dispatch_inputs_from_deeplink_referer() -> None:
    content = ROUTE_FILE.read_text()

    assert "function extractDeepLinkFallbacks(req: Request)" in content
    assert "const referer = req.headers.get('referer') || req.headers.get('referrer') || '';" in content
    assert "const deepLinkFallbacks = extractDeepLinkFallbacks(req);" in content
    assert "if (!options.agentName && deepLinkFallbacks.agentName)" in content
    assert "if (!currentCallSessionId && deepLinkFallbacks.callSessionId)" in content
    assert "const metadata = JSON.stringify({ callSessionId: deepLinkFallbacks.callSessionId });" in content
