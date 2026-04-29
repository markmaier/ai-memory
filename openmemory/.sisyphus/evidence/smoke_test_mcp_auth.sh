#!/usr/bin/env bash
# Integration smoke test for MCP multi-user OAuth.
# Run after deploying the new code. Requires:
#   - jq installed
#   - MCP_AUTH_JSON pointing to the OpenCode mcp-auth.json file
#   - API_BASE_URL set to the API base (default: https://ai-memory.nip-non-prod.cloud.netcetera.com)
#
# Usage: bash smoke_test_mcp_auth.sh

set -euo pipefail

API_BASE_URL="${API_BASE_URL:-https://ai-memory.nip-non-prod.cloud.netcetera.com}"
MCP_AUTH_JSON="${MCP_AUTH_JSON:-$HOME/.local/share/opencode/mcp-auth.json}"
KEYCLOAK_TOKEN_URL="https://dev-silver.fra.nip-non-prod.cloud.netcetera.com/realms/nca_users/protocol/openid-connect/token"
CLIENT_ID="ai-memory-cli"

PASS=0
FAIL=0

log_pass() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
log_fail() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }

# --- Get fresh token ---
echo "=== Obtaining fresh access token ==="
REFRESH_TOKEN=$(jq -r '."ai-memory".tokens.refresh_token // empty' "$MCP_AUTH_JSON")
if [ -z "$REFRESH_TOKEN" ]; then
    echo "ERROR: No refresh token found in $MCP_AUTH_JSON"
    exit 1
fi

TOKEN_RESPONSE=$(curl -s -X POST "$KEYCLOAK_TOKEN_URL" \
    -d "grant_type=refresh_token" \
    -d "client_id=$CLIENT_ID" \
    -d "refresh_token=$REFRESH_TOKEN")

ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.access_token // empty')
if [ -z "$ACCESS_TOKEN" ]; then
    echo "ERROR: Failed to get access token: $TOKEN_RESPONSE"
    exit 1
fi
echo "  Token obtained (${#ACCESS_TOKEN} chars)"

# --- Test 1: Authenticated SSE endpoint connects ---
echo ""
echo "=== Test 1: Authenticated SSE connects ==="
SSE_RESPONSE=$(curl -s -N --max-time 3 \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -w "\n%{http_code}" \
    "$API_BASE_URL/mcp/auth/openmemory/sse" 2>/dev/null || true)

HTTP_CODE=$(echo "$SSE_RESPONSE" | tail -1)
if [ "$HTTP_CODE" = "200" ]; then
    log_pass "Authenticated SSE returned 200"
else
    log_fail "Authenticated SSE returned $HTTP_CODE (expected 200)"
fi

# --- Test 2: No token returns 401 ---
echo ""
echo "=== Test 2: No token returns 401 ==="
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API_BASE_URL/mcp/auth/openmemory/sse" 2>/dev/null)
if [ "$HTTP_CODE" = "401" ]; then
    log_pass "No token returned 401"
else
    log_fail "No token returned $HTTP_CODE (expected 401)"
fi

# --- Test 3: Invalid token returns 401 ---
echo ""
echo "=== Test 3: Invalid token returns 401 ==="
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer invalid.token.here" \
    "$API_BASE_URL/mcp/auth/openmemory/sse" 2>/dev/null)
if [ "$HTTP_CODE" = "401" ]; then
    log_pass "Invalid token returned 401"
else
    log_fail "Invalid token returned $HTTP_CODE (expected 401)"
fi

# --- Test 4: Backward compat (old URL, no auth) ---
echo ""
echo "=== Test 4: Backward compat (old URL) ==="
OLD_RESPONSE=$(curl -s -N --max-time 3 \
    -w "\n%{http_code}" \
    "$API_BASE_URL/mcp/openmemory/sse/maier" 2>/dev/null || true)

HTTP_CODE=$(echo "$OLD_RESPONSE" | tail -1)
if [ "$HTTP_CODE" = "200" ]; then
    log_pass "Old URL returned 200 (backward compat works)"
else
    log_fail "Old URL returned $HTTP_CODE (expected 200)"
fi

# --- Summary ---
echo ""
echo "=== Results ==="
echo "  Passed: $PASS"
echo "  Failed: $FAIL"
echo ""

if [ "$FAIL" -gt 0 ]; then
    echo "VERDICT: FAIL"
    exit 1
else
    echo "VERDICT: PASS"
    exit 0
fi
