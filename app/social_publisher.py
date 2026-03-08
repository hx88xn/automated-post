"""
Social media publishing — post text and images to LinkedIn, Facebook, and Instagram.
"""

import httpx
from app.social_auth import get_token


# =========================================================================== #
#  LinkedIn — Posts API                                                        #
# =========================================================================== #

async def publish_to_linkedin(text: str, image_bytes: bytes | None = None) -> dict:
    """Publish a text post (or text + image) to LinkedIn."""
    token_info = get_token("linkedin")
    if not token_info:
        return {"success": False, "error": "LinkedIn not connected"}

    access_token = token_info["access_token"]
    author_urn = f"urn:li:person:{token_info['sub']}"

    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "LinkedIn-Version": "202502",
            "X-Restli-Protocol-Version": "2.0.0",
        }

        # If image provided, upload it first
        image_urn = None
        if image_bytes:
            # Step 1: Initialize upload
            init_resp = await client.post(
                "https://api.linkedin.com/rest/images?action=initializeUpload",
                headers=headers,
                json={
                    "initializeUploadRequest": {
                        "owner": author_urn,
                    }
                },
            )
            init_data = init_resp.json()
            upload_url = init_data.get("value", {}).get("uploadUrl")
            image_urn = init_data.get("value", {}).get("image")

            if upload_url:
                # Step 2: Upload the image binary
                await client.put(
                    upload_url,
                    content=image_bytes,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "image/png",
                    },
                )

        # Build post payload
        post_body: dict = {
            "author": author_urn,
            "commentary": text,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
        }

        if image_urn:
            post_body["content"] = {
                "media": {
                    "id": image_urn,
                    "title": "Generated Post",
                }
            }

        resp = await client.post(
            "https://api.linkedin.com/rest/posts",
            headers=headers,
            json=post_body,
        )

        if resp.status_code in (200, 201):
            post_id = resp.headers.get("x-restli-id", "")
            return {"success": True, "platform": "linkedin", "post_id": post_id}
        else:
            return {
                "success": False,
                "error": resp.text,
                "status_code": resp.status_code,
            }


# =========================================================================== #
#  Facebook — Graph API                                                        #
# =========================================================================== #

async def publish_to_facebook(text: str, image_bytes: bytes | None = None) -> dict:
    """Publish a post to the connected Facebook Page."""
    token_info = get_token("facebook")
    if not token_info:
        return {"success": False, "error": "Facebook not connected"}

    access_token = token_info["access_token"]
    page_id = token_info.get("page_id")

    if not page_id:
        return {"success": False, "error": "No Facebook Page found"}

    async with httpx.AsyncClient() as client:
        if image_bytes:
            # Post with photo
            resp = await client.post(
                f"https://graph.facebook.com/v21.0/{page_id}/photos",
                data={
                    "caption": text,
                    "access_token": access_token,
                },
                files={"source": ("post.png", image_bytes, "image/png")},
            )
        else:
            # Text-only post
            resp = await client.post(
                f"https://graph.facebook.com/v21.0/{page_id}/feed",
                data={
                    "message": text,
                    "access_token": access_token,
                },
            )

        result = resp.json()
        if "id" in result:
            return {"success": True, "platform": "facebook", "post_id": result["id"]}
        else:
            return {
                "success": False,
                "error": result.get("error", {}).get("message", str(result)),
            }


# =========================================================================== #
#  Instagram — Graph API (requires image)                                      #
# =========================================================================== #

async def publish_to_instagram(
    text: str, image_url: str | None = None, image_bytes: bytes | None = None
) -> dict:
    """
    Publish to Instagram Business account via Graph API.
    Instagram API requires a publicly accessible image URL.
    If image_bytes is provided, we first upload to Facebook to get a URL.
    """
    token_info = get_token("instagram")
    if not token_info:
        return {"success": False, "error": "Instagram not connected"}

    access_token = token_info["access_token"]
    ig_user_id = token_info.get("ig_user_id")

    if not ig_user_id:
        return {"success": False, "error": "No Instagram Business account linked"}

    if not image_url and not image_bytes:
        return {"success": False, "error": "Instagram requires an image"}

    async with httpx.AsyncClient() as client:
        # If we have image bytes but no URL, upload to Facebook Page first to get URL
        if image_bytes and not image_url:
            fb_token = get_token("facebook")
            if fb_token and fb_token.get("page_id"):
                upload_resp = await client.post(
                    f"https://graph.facebook.com/v21.0/{fb_token['page_id']}/photos",
                    data={
                        "published": "false",
                        "access_token": fb_token["access_token"],
                    },
                    files={"source": ("post.png", image_bytes, "image/png")},
                )
                upload_data = upload_resp.json()
                photo_id = upload_data.get("id")
                if photo_id:
                    # Get the photo URL
                    photo_resp = await client.get(
                        f"https://graph.facebook.com/v21.0/{photo_id}",
                        params={
                            "fields": "images",
                            "access_token": fb_token["access_token"],
                        },
                    )
                    photo_data = photo_resp.json()
                    images = photo_data.get("images", [])
                    if images:
                        image_url = images[0].get("source")

        if not image_url:
            return {"success": False, "error": "Could not obtain a public image URL for Instagram"}

        # Step 1: Create media container
        container_resp = await client.post(
            f"https://graph.facebook.com/v21.0/{ig_user_id}/media",
            data={
                "image_url": image_url,
                "caption": text,
                "access_token": access_token,
            },
        )
        container_data = container_resp.json()
        container_id = container_data.get("id")

        if not container_id:
            return {
                "success": False,
                "error": container_data.get("error", {}).get("message", str(container_data)),
            }

        # Step 2: Publish the container
        publish_resp = await client.post(
            f"https://graph.facebook.com/v21.0/{ig_user_id}/media_publish",
            data={
                "creation_id": container_id,
                "access_token": access_token,
            },
        )
        publish_data = publish_resp.json()

        if "id" in publish_data:
            return {"success": True, "platform": "instagram", "post_id": publish_data["id"]}
        else:
            return {
                "success": False,
                "error": publish_data.get("error", {}).get("message", str(publish_data)),
            }
