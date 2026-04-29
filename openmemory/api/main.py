import datetime
import os
from uuid import uuid4

from app.config import DEFAULT_APP_ID, USER_ID
from app.database import Base, SessionLocal, engine
from app.mcp_server import setup_mcp_server
from app.models import App, User
from app.routers import apps_router, backup_router, config_router, health_router, memories_router, stats_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi_pagination import add_pagination

app = FastAPI(title="OpenMemory API")

_cors_origins_raw = os.getenv("CORS_ALLOWED_ORIGINS", "*")
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- RFC 9728  Protected Resource Metadata (MCP OAuth discovery) --------
_oauth_resource_url = os.getenv("OAUTH_RESOURCE_URL", "")
_oauth_authz_server = os.getenv("OAUTH_AUTHORIZATION_SERVER_URL", "")

if _oauth_resource_url and _oauth_authz_server:
    _prm_response = JSONResponse(
        content={
            "resource": _oauth_resource_url,
            "authorization_servers": [_oauth_authz_server],
        },
        headers={"Cache-Control": "public, max-age=3600"},
    )

    # RFC 9728 §3: metadata URL = /.well-known/oauth-protected-resource{+resource-path}
    @app.get("/.well-known/oauth-protected-resource/{path:path}")
    @app.get("/.well-known/oauth-protected-resource")
    async def oauth_protected_resource():
        return _prm_response


# Create all tables
Base.metadata.create_all(bind=engine)


# Check for USER_ID and create default user if needed
def create_default_user():
    db = SessionLocal()
    try:
        # Check if user exists
        user = db.query(User).filter(User.user_id == USER_ID).first()
        if not user:
            # Create default user
            user = User(
                id=uuid4(), user_id=USER_ID, name="Default User", created_at=datetime.datetime.now(datetime.UTC)
            )
            db.add(user)
            db.commit()
    finally:
        db.close()


def create_default_app():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == USER_ID).first()
        if not user:
            return

        # Check if app already exists
        existing_app = db.query(App).filter(App.name == DEFAULT_APP_ID, App.owner_id == user.id).first()

        if existing_app:
            return

        app = App(
            id=uuid4(),
            name=DEFAULT_APP_ID,
            owner_id=user.id,
            created_at=datetime.datetime.now(datetime.UTC),
            updated_at=datetime.datetime.now(datetime.UTC),
        )
        db.add(app)
        db.commit()
    finally:
        db.close()


# Create default user on startup
create_default_user()
create_default_app()

# Setup MCP server
setup_mcp_server(app)

# Include routers
app.include_router(memories_router)
app.include_router(apps_router)
app.include_router(stats_router)
app.include_router(config_router)
app.include_router(backup_router)
app.include_router(health_router)

# Add pagination support
add_pagination(app)
