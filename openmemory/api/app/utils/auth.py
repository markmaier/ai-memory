"""JWT validation utilities for OpenMemory MCP server.

Validates Keycloak JWT access tokens using JWKS (JSON Web Key Set) for
multi-user MCP access. The ``preferred_username`` claim is used as the
OpenMemory ``user_id``.

Configuration:
    OIDC_ISSUER_URL  – Keycloak realm URL (e.g.
        ``https://keycloak.example.com/realms/my_realm``).  When empty,
        JWT authentication is disabled and the authenticated routes
        return 503.
"""

import logging
from typing import Optional

import jwt
from fastapi import HTTPException, Request
from jwt import PyJWKClient

from app.config import OIDC_ISSUER_URL

logger = logging.getLogger(__name__)

# Module-level JWKS client singleton – PyJWKClient caches keys internally
# (default lifespan 300 s).  Created lazily on first use so the server can
# start even when the OIDC issuer is unreachable.
_jwks_client: Optional[PyJWKClient] = None


def _get_jwks_client() -> PyJWKClient:
    """Return (and lazily create) the module-level JWKS client."""
    global _jwks_client
    if _jwks_client is None:
        if not OIDC_ISSUER_URL:
            raise RuntimeError("OIDC_ISSUER_URL is not configured")
        jwks_url = f"{OIDC_ISSUER_URL.rstrip('/')}/protocol/openid-connect/certs"
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True, lifespan=300)
        logger.info("JWKS client initialised for %s", jwks_url)
    return _jwks_client


def decode_jwt(token: str) -> dict:
    """Decode and validate a JWT access token.

    Validates:
    - Signature (via JWKS)
    - ``exp`` (expiration)
    - ``iss`` (issuer, when ``OIDC_ISSUER_URL`` is set)

    Does **not** validate ``aud`` (Keycloak omits it from access tokens).

    Raises:
        jwt.ExpiredSignatureError: token has expired.
        jwt.InvalidTokenError: any other validation failure.
        RuntimeError: OIDC is not configured.
    """
    client = _get_jwks_client()
    signing_key = client.get_signing_key_from_jwt(token)
    payload = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=OIDC_ISSUER_URL if OIDC_ISSUER_URL else None,
        options={
            "verify_aud": False,
            "verify_exp": True,
            "verify_iss": bool(OIDC_ISSUER_URL),
        },
    )
    return payload


def get_user_from_token(request: Request) -> Optional[dict]:
    """Extract and decode the JWT from the request's Authorization header.

    Returns the decoded payload, or ``None`` when no valid Bearer token
    is present.
    """
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header[7:]
    if not token:
        return None
    try:
        return decode_jwt(token)
    except jwt.ExpiredSignatureError:
        logger.debug("JWT expired")
        return None
    except jwt.InvalidTokenError as exc:
        logger.debug("Invalid JWT: %s", exc)
        return None
    except RuntimeError:
        return None


async def require_jwt_user(request: Request) -> dict:
    """FastAPI dependency that enforces a valid JWT with ``preferred_username``.

    Raises:
        HTTPException 401: missing/invalid token or missing username claim.
        HTTPException 503: OIDC is not configured.
    """
    if not OIDC_ISSUER_URL:
        raise HTTPException(status_code=503, detail="OAuth not configured")

    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    try:
        payload = decode_jwt(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")

    username = payload.get("preferred_username", "").strip()
    if not username:
        raise HTTPException(
            status_code=401,
            detail="Token missing preferred_username claim",
        )

    return payload
