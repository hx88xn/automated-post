"""
OAuth 2.0 flow handlers for LinkedIn, Facebook, and Instagram.
Handles authorization redirects, callbacks, token storage, and status.
"""

import os
import httpx
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse

router = APIRouter(prefix="/auth", tags=["auth"])

# ---------------------------------------------------------------------------
# Configuration (from environment)
# ---------------------------------------------------------------------------
APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:7001")

LINKEDIN_CLIENT_ID = os.environ.get("LINKEDIN_CLIENT_ID", "")
LINKEDIN_CLIENT_SECRET = os.environ.get("LINKEDIN_CLIENT_SECRET", "")

FACEBOOK_APP_ID = os.environ.get("FACEBOOK_APP_ID", "")
FACEBOOK_APP_SECRET = os.environ.get("FACEBOOK_APP_SECRET", "")

# ---------------------------------------------------------------------------
# In-memory token store  {platform: {access_token, ...}}
# ---------------------------------------------------------------------------
_tokens: dict[str, dict] = {}


def get_token(platform: str) -> dict | None:
    return _tokens.get(platform)


def is_connected(platform: str) -> bool:
    return platform in _tokens and bool(_tokens[platform].get("access_token"))


# ---------------------------------------------------------------------------
# Status & disconnect
# ---------------------------------------------------------------------------

@router.get("/status")
async def auth_status():
    """Return connection status for each platform."""
    return JSONResponse({
        "linkedin": is_connected("linkedin"),
        "facebook": is_connected("facebook"),
        "instagram": is_connected("instagram"),
    })


@router.post("/{platform}/disconnect")
async def disconnect(platform: str):
    """Remove stored token for a platform."""
    _tokens.pop(platform, None)
    # Instagram shares Facebook's token — disconnect both if needed
    if platform == "facebook":
        _tokens.pop("instagram", None)
    return JSONResponse({"status": "disconnected", "platform": platform})


# =========================================================================== #
#  LinkedIn OAuth 2.0                                                         #
# =========================================================================== #

LINKEDIN_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_SCOPES = "openid profile w_member_social"


@router.get("/linkedin/login")
async def linkedin_login():
    """Redirect user to LinkedIn's authorization page."""
    redirect_uri = f"{APP_BASE_URL}/auth/linkedin/callback"
    url = (
        f"{LINKEDIN_AUTH_URL}"
        f"?response_type=code"
        f"&client_id={LINKEDIN_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&scope={LINKEDIN_SCOPES}"
        f"&state=linkedin"
    )
    return RedirectResponse(url)


@router.get("/linkedin/callback")
async def linkedin_callback(code: str = "", error: str = ""):
    """Handle LinkedIn OAuth callback."""
    if error or not code:
        return RedirectResponse(f"/?auth_error=linkedin&detail={error}")

    redirect_uri = f"{APP_BASE_URL}/auth/linkedin/callback"

    async with httpx.AsyncClient() as client:
        # Exchange code for access token
        resp = await client.post(
            LINKEDIN_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": LINKEDIN_CLIENT_ID,
                "client_secret": LINKEDIN_CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        token_data = resp.json()

        if "access_token" not in token_data:
            return RedirectResponse(f"/?auth_error=linkedin&detail=token_exchange_failed")

        # Get user info (sub = member URN)
        userinfo = await client.get(
            "https://api.linkedin.com/v2/userinfo",
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )
        user_data = userinfo.json()

        _tokens["linkedin"] = {
            "access_token": token_data["access_token"],
            "sub": user_data.get("sub", ""),
            "name": user_data.get("name", "LinkedIn User"),
        }

    return RedirectResponse("/?auth_success=linkedin")


# =========================================================================== #
#  Facebook / Instagram OAuth 2.0  (Meta Graph API)                           #
# =========================================================================== #

FB_AUTH_URL = "https://www.facebook.com/v21.0/dialog/oauth"
FB_TOKEN_URL = "https://graph.facebook.com/v21.0/oauth/access_token"
FB_SCOPES = (
    "pages_manage_posts,pages_read_engagement,"
    "instagram_basic,instagram_content_publish"
)


@router.get("/facebook/login")
async def facebook_login():
    """Redirect user to Facebook's authorization page (covers Instagram too)."""
    redirect_uri = f"{APP_BASE_URL}/auth/facebook/callback"
    url = (
        f"{FB_AUTH_URL}"
        f"?client_id={FACEBOOK_APP_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&scope={FB_SCOPES}"
        f"&response_type=code"
        f"&state=facebook"
    )
    return RedirectResponse(url)


@router.get("/facebook/callback")
async def facebook_callback(code: str = "", error: str = ""):
    """Handle Facebook OAuth callback — also sets up Instagram."""
    if error or not code:
        return RedirectResponse(f"/?auth_error=facebook&detail={error}")

    redirect_uri = f"{APP_BASE_URL}/auth/facebook/callback"

    async with httpx.AsyncClient() as client:
        # Exchange code for short-lived token
        resp = await client.get(
            FB_TOKEN_URL,
            params={
                "client_id": FACEBOOK_APP_ID,
                "client_secret": FACEBOOK_APP_SECRET,
                "redirect_uri": redirect_uri,
                "code": code,
            },
        )
        token_data = resp.json()

        if "access_token" not in token_data:
            return RedirectResponse(f"/?auth_error=facebook&detail=token_exchange_failed")

        user_token = token_data["access_token"]

        # Exchange for long-lived token (60 days)
        ll_resp = await client.get(
            FB_TOKEN_URL,
            params={
                "grant_type": "fb_exchange_token",
                "client_id": FACEBOOK_APP_ID,
                "client_secret": FACEBOOK_APP_SECRET,
                "fb_exchange_token": user_token,
            },
        )
        ll_data = ll_resp.json()
        long_lived_token = ll_data.get("access_token", user_token)

        # Get user's Pages
        pages_resp = await client.get(
            "https://graph.facebook.com/v21.0/me/accounts",
            params={"access_token": long_lived_token},
        )
        pages_data = pages_resp.json()
        pages = pages_data.get("data", [])

        page_info = None
        page_token = long_lived_token
        if pages:
            page_info = pages[0]  # Use first page
            page_token = page_info.get("access_token", long_lived_token)

        _tokens["facebook"] = {
            "access_token": page_token,
            "user_token": long_lived_token,
            "page_id": page_info["id"] if page_info else None,
            "page_name": page_info["name"] if page_info else "No Page",
        }

        # Try to find linked Instagram Business account
        if page_info:
            ig_resp = await client.get(
                f"https://graph.facebook.com/v21.0/{page_info['id']}",
                params={
                    "fields": "instagram_business_account",
                    "access_token": page_token,
                },
            )
            ig_data = ig_resp.json()
            ig_account = ig_data.get("instagram_business_account")

            if ig_account:
                _tokens["instagram"] = {
                    "access_token": page_token,
                    "ig_user_id": ig_account["id"],
                    "page_name": page_info["name"],
                }

    return RedirectResponse("/?auth_success=facebook")


# Instagram login redirects to Facebook (same OAuth flow)
@router.get("/instagram/login")
async def instagram_login():
    """Instagram uses the same Facebook OAuth flow."""
    return await facebook_login()
