import os

USER_ID = os.getenv("USER", "default_user")
DEFAULT_APP_ID = "openmemory"

OIDC_ISSUER_URL = os.getenv("OIDC_ISSUER_URL", "")
OIDC_AUDIENCE = os.getenv("OIDC_AUDIENCE", "")