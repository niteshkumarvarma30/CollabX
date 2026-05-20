import json
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

import httpx
from dotenv import load_dotenv
from fastapi import Cookie, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "instagram_dashboard.sqlite3" # Deprecated
load_dotenv(BASE_DIR / ".env", override=True)

APP_ID = os.getenv("META_APP_ID", "")
APP_SECRET = os.getenv("META_APP_SECRET", "")
REDIRECT_URI = os.getenv("META_REDIRECT_URI", "http://localhost:8000/callback")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v25.0")
CONFIGURED_PAGE_ID = os.getenv("META_PAGE_ID", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
FACEBOOK_OAUTH_URL = f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth"
GRAPH_BASE_URL = f"https://graph.facebook.com/{GRAPH_VERSION}"

DEFAULT_SCOPES = [
    "pages_show_list",
    "pages_read_engagement",
    "instagram_basic",
    "instagram_manage_insights",
]
SCOPES = [
    scope.strip()
    for scope in os.getenv("META_SCOPES", ",".join(DEFAULT_SCOPES)).split(",")
    if scope.strip()
]

app = FastAPI(title="Instagram Insights Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

USERS: dict[str, dict[str, Any]] = {}
OAUTH_STATES: dict[str, str] = {}


class GraphAPIError(Exception):
    def __init__(self, message: str, status_code: int = 400, details: Any | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details


def db_connection() -> psycopg2.extensions.connection:
    if not DATABASE_URL:
        raise Exception("DATABASE_URL environment variable is missing. Please add your Supabase connection string to .env")
    connection = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    connection.autocommit = True
    return connection


def init_db() -> None:
    if not DATABASE_URL:
        return
    with db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_sessions (
                    user_id TEXT PRIMARY KEY,
                    access_token TEXT NOT NULL,
                    ig_id TEXT,
                    data_json TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )


def save_user_session(user_id: str, access_token: str, dashboard_data: dict[str, Any] | None = None) -> None:
    ig_id = None
    data_json = None
    if dashboard_data:
        ig_id = dashboard_data.get("user", {}).get("ig_id")
        data_json = json.dumps(dashboard_data)

    with db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO user_sessions (user_id, access_token, ig_id, data_json, updated_at)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    access_token = EXCLUDED.access_token,
                    ig_id = COALESCE(EXCLUDED.ig_id, user_sessions.ig_id),
                    data_json = COALESCE(EXCLUDED.data_json, user_sessions.data_json),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, access_token, ig_id, data_json),
            )


def load_user_session(user_id: str) -> dict[str, Any] | None:
    if user_id in USERS and USERS[user_id].get("access_token"):
        return USERS[user_id]

    with db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT access_token, ig_id, data_json FROM user_sessions WHERE user_id = %s",
                (user_id,),
            )
            row = cursor.fetchone()

    if not row:
        return None

    data = json.loads(row["data_json"]) if row["data_json"] else None
    session = {
        "access_token": row["access_token"],
        "ig_id": row["ig_id"],
        "data": data,
        "posts": (data or {}).get("posts", []),
    }
    USERS[user_id] = session
    return session


@app.on_event("startup")
def startup() -> None:
    init_db()


def require_meta_config() -> None:
    if not APP_ID or not APP_SECRET:
        raise HTTPException(
            status_code=500,
            detail="META_APP_ID and META_APP_SECRET must be set in backend/.env.",
        )


def make_error_redirect(message: str) -> RedirectResponse:
    return RedirectResponse(f"{FRONTEND_URL}/?error={quote(message)}")


async def graph_get(
    path: str,
    access_token: str | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    query = dict(params or {})
    if access_token:
        query["access_token"] = access_token

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{GRAPH_BASE_URL}{path}", params=query)

    payload = response.json()
    if response.is_error or "error" in payload:
        error = payload.get("error", {})
        message = error.get("message", "Meta Graph API request failed.")
        raise GraphAPIError(message, response.status_code, error)

    return payload


async def exchange_code_for_token(code: str) -> str:
    payload = await graph_get(
        "/oauth/access_token",
        params={
            "client_id": APP_ID,
            "client_secret": APP_SECRET,
            "redirect_uri": REDIRECT_URI,
            "code": code,
        },
    )
    access_token = payload.get("access_token")
    if not access_token:
        raise GraphAPIError("Meta did not return an access token.")
    return access_token


async def get_first_page(user_access_token: str) -> dict[str, Any]:
    payload = await graph_get(
        "/me/accounts",
        user_access_token,
        {"fields": "id,name,access_token"},
    )
    pages = payload.get("data", [])
    if not pages:
        fallback = await graph_get(
            "/me",
            user_access_token,
            {"fields": "accounts.limit(25){id,name,access_token,instagram_business_account}"},
        )
        pages = (fallback.get("accounts") or {}).get("data", [])
    if not pages and CONFIGURED_PAGE_ID:
        try:
            configured_page = await graph_get(
                f"/{CONFIGURED_PAGE_ID}",
                user_access_token,
                {"fields": "id,name,access_token,instagram_business_account"},
            )
            return configured_page
        except GraphAPIError:
            pass
    if not pages:
        permissions = await get_permissions(user_access_token)
        requested_permissions = set(SCOPES)
        declined = [
            permission["permission"]
            for permission in permissions
            if permission.get("permission") in requested_permissions
            and permission.get("status") != "granted"
        ]
        granted = [
            permission["permission"]
            for permission in permissions
            if permission.get("permission") in requested_permissions
            and permission.get("status") == "granted"
        ]
        declined_text = ", ".join(declined) if declined else "none reported"
        granted_text = ", ".join(granted) if granted else "none reported"
        raise GraphAPIError(
            "Meta returned 0 Facebook Pages from /me/accounts. Use Fresh reconnect, choose Edit settings, "
            "select the Facebook Page, select its connected Instagram Business or Creator account, and grant "
            "all requested permissions. "
            f"Required permissions granted: {granted_text}. Required permissions missing or declined: {declined_text}."
        )
    return pages[0]


async def get_permissions(user_access_token: str) -> list[dict[str, Any]]:
    payload = await graph_get("/me/permissions", user_access_token)
    return payload.get("data", [])


async def get_instagram_account(page_id: str, page_access_token: str) -> str:
    payload = await graph_get(
        f"/{page_id}",
        page_access_token,
        {"fields": "instagram_business_account"},
    )
    ig_account = payload.get("instagram_business_account")
    if not ig_account or not ig_account.get("id"):
        raise GraphAPIError(
            "No Instagram Business or Creator account is connected to the selected Facebook Page."
        )
    return ig_account["id"]


async def get_ig_profile(ig_user_id: str, page_access_token: str) -> dict[str, Any]:
    return await graph_get(
        f"/{ig_user_id}",
        page_access_token,
        {"fields": "id,username,followers_count"},
    )


async def get_media(ig_user_id: str, page_access_token: str) -> list[dict[str, Any]]:
    payload = await graph_get(
        f"/{ig_user_id}/media",
        page_access_token,
        {"fields": "id,caption", "limit": 25},
    )
    return payload.get("data", [])


def extract_metric_value(insight: dict[str, Any]) -> int:
    values = insight.get("values") or []
    if not values:
        return 0
    value = values[-1].get("value", 0)
    return int(value or 0)


def is_permission_error(details: Any) -> bool:
    if not isinstance(details, dict):
        return False
    code = details.get("code")
    subcode = details.get("error_subcode")
    return code in {10, 190, 200} or subcode in {458, 459, 460, 463}


async def get_media_insights(media_id: str, page_access_token: str) -> tuple[dict[str, int], list[str]]:
    metric_names = ["reach", "likes", "comments", "saved", "shares"]
    try:
        payload = await graph_get(
            f"/{media_id}/insights",
            page_access_token,
            {"metric": ",".join(metric_names)},
        )
        metrics = {item.get("name"): extract_metric_value(item) for item in payload.get("data", [])}
        return {name: metrics.get(name, 0) for name in metric_names}, []
    except GraphAPIError as exc:
        if is_permission_error(exc.details):
            raise

    metrics: dict[str, int] = {}
    metric_errors: list[str] = []
    for metric in metric_names:
        try:
            payload = await graph_get(
                f"/{media_id}/insights",
                page_access_token,
                {"metric": metric},
            )
            metrics[metric] = extract_metric_value((payload.get("data") or [{}])[0])
        except GraphAPIError as exc:
            if is_permission_error(exc.details):
                raise
            metrics[metric] = 0
            metric_errors.append(f"{metric}: {exc.message}")

    return metrics, metric_errors


async def build_dashboard_data(user_access_token: str) -> dict[str, Any]:
    page = await get_first_page(user_access_token)
    page_access_token = page.get("access_token") or user_access_token
    ig_user_id = await get_instagram_account(page["id"], page_access_token)
    profile = await get_ig_profile(ig_user_id, page_access_token)
    media_items = await get_media(ig_user_id, page_access_token)

    posts = []
    warnings = []
    for media in media_items:
        metrics, metric_errors = await get_media_insights(media["id"], page_access_token)
        reach = metrics.get("reach", 0)
        interactions = (
            metrics.get("likes", 0)
            + metrics.get("comments", 0)
            + metrics.get("saved", 0)
            + metrics.get("shares", 0)
        )
        posts.append(
            {
                "id": media["id"],
                "caption": media.get("caption", ""),
                "reach": reach,
                "likes": metrics.get("likes", 0),
                "comments": metrics.get("comments", 0),
                "saved": metrics.get("saved", 0),
                "shares": metrics.get("shares", 0),
                "engagement_rate": round(interactions / reach, 4) if reach else 0,
            }
        )
        warnings.extend([f"Media {media['id']} {error}" for error in metric_errors])

    return {
        "user": {
            "ig_id": ig_user_id,
            "username": profile.get("username"),
            "followers": profile.get("followers_count", 0),
            "page_id": page["id"],
            "page_name": page.get("name"),
        },
        "posts": posts,
        "warnings": warnings,
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/login")
def login(response: Response, fresh: bool = Query(default=False)) -> RedirectResponse:
    require_meta_config()
    user_id = str(uuid.uuid4())
    state = str(uuid.uuid4())
    USERS.setdefault(user_id, {})
    OAUTH_STATES[state] = user_id

    params = {
        "client_id": APP_ID,
        "redirect_uri": REDIRECT_URI,
        "state": state,
        "scope": ",".join(SCOPES),
        "response_type": "code",
        # Ask Meta to show the permission/settings flow again when the user
        # previously continued with an incomplete Page/Instagram selection.
        "auth_type": "reauthorize" if fresh else "rerequest",
    }
    redirect = RedirectResponse(f"{FACEBOOK_OAUTH_URL}?{urlencode(params)}")
    redirect.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    redirect.headers["Pragma"] = "no-cache"
    redirect.headers["Expires"] = "0"
    redirect.set_cookie(
        "instagram_dashboard_user",
        user_id,
        httponly=True,
        samesite="none",
        secure=True,
        max_age=60 * 60 * 8,
    )
    return redirect


@app.get("/callback")
async def callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
) -> RedirectResponse:
    if error:
        return make_error_redirect(error_description or error)
    if not code or not state:
        return make_error_redirect("Meta callback did not include code and state.")

    user_id = OAUTH_STATES.pop(state, None)
    if not user_id:
        return make_error_redirect("Invalid or expired OAuth state. Please connect again.")

    try:
        access_token = await exchange_code_for_token(code)
        USERS[user_id] = {"access_token": access_token}
        save_user_session(user_id, access_token)
        dashboard_data = await build_dashboard_data(access_token)
        USERS[user_id] = {
            "access_token": access_token,
            "ig_id": dashboard_data["user"]["ig_id"],
            "posts": dashboard_data["posts"],
            "data": dashboard_data,
        }
        save_user_session(user_id, access_token, dashboard_data)
    except GraphAPIError as exc:
        return make_error_redirect(exc.message)

    redirect = RedirectResponse(f"{FRONTEND_URL}/?connected=1&session_token={user_id}")
    redirect.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    redirect.headers["Pragma"] = "no-cache"
    redirect.headers["Expires"] = "0"
    redirect.set_cookie(
        "instagram_dashboard_user",
        user_id,
        httponly=True,
        samesite="none",
        secure=True,
        max_age=60 * 60 * 8,
    )
    return redirect


from fastapi import Header

@app.get("/fetch-data")
async def fetch_data(
    instagram_dashboard_user: str | None = Cookie(default=None),
    authorization: str | None = Header(default=None)
) -> dict[str, Any]:
    token = instagram_dashboard_user
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ")[1]

    if not token:
        raise HTTPException(status_code=401, detail="Connect Instagram before fetching data.")

    user = load_user_session(token)
    if not user:
        raise HTTPException(status_code=401, detail="Connect Instagram before fetching data.")

    access_token = user.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="OAuth token missing. Please connect again.")

    try:
        dashboard_data = await build_dashboard_data(access_token)
    except GraphAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    user["ig_id"] = dashboard_data["user"]["ig_id"]
    user["posts"] = dashboard_data["posts"]
    user["data"] = dashboard_data
    save_user_session(token, access_token, dashboard_data)
    return dashboard_data


@app.get("/debug/meta")
async def debug_meta(instagram_dashboard_user: str | None = Cookie(default=None)) -> dict[str, Any]:
    if not instagram_dashboard_user:
        raise HTTPException(status_code=401, detail="Connect Instagram before debugging Meta data.")

    user = load_user_session(instagram_dashboard_user)
    if not user:
        raise HTTPException(status_code=401, detail="Connect Instagram before debugging Meta data.")

    access_token = user.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="OAuth token missing. Please connect again.")

    permissions = await get_permissions(access_token)
    accounts_response = await graph_get(
        "/me/accounts",
        access_token,
        {"fields": "id,name,instagram_business_account", "limit": 25},
    )
    fallback_response = await graph_get(
        "/me",
        access_token,
        {"fields": "id,name,accounts.limit(25){id,name,instagram_business_account}"},
    )
    required = set(SCOPES)
    return {
        "required_permissions": [
            permission
            for permission in permissions
            if permission.get("permission") in required
        ],
        "accounts_count": len(accounts_response.get("data", [])),
        "accounts": accounts_response.get("data", []),
        "fallback_accounts_count": len((fallback_response.get("accounts") or {}).get("data", [])),
        "fallback_accounts": (fallback_response.get("accounts") or {}).get("data", []),
    }


@app.get("/debug/page/{page_id}")
async def debug_page(
    page_id: str,
    instagram_dashboard_user: str | None = Cookie(default=None),
) -> dict[str, Any]:
    if not instagram_dashboard_user:
        raise HTTPException(status_code=401, detail="Connect Instagram before debugging a Page.")

    user = load_user_session(instagram_dashboard_user)
    if not user:
        raise HTTPException(status_code=401, detail="Connect Instagram before debugging a Page.")

    access_token = user.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="OAuth token missing. Please connect again.")

    try:
        page = await graph_get(
            f"/{page_id}",
            access_token,
            {"fields": "id,name,instagram_business_account,access_token"},
        )
    except GraphAPIError as exc:
        return {
            "page_id": page_id,
            "accessible": False,
            "message": exc.message,
            "meta_error": exc.details,
        }

    ig_account = page.get("instagram_business_account")
    return {
        "page_id": page_id,
        "accessible": True,
        "page_name": page.get("name"),
        "has_page_access_token": bool(page.get("access_token")),
        "instagram_business_account": ig_account,
        "can_continue_to_insights": bool(page.get("access_token") and ig_account and ig_account.get("id")),
    }
