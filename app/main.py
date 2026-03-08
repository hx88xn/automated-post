"""
FastAPI application — Automated Social Media Post Generator.
"""

import base64
import os
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from typing import Optional

from app.post_generator import (
    PostOptions,
    TextStyle,
    BackgroundStyle,
    generate_text_post,
    generate_image_post,
)
from app.social_auth import router as auth_router
from app.social_publisher import (
    publish_to_linkedin,
    publish_to_facebook,
    publish_to_instagram,
)

app = FastAPI(title="Automated Post Generator", version="1.0.0")

# Register OAuth router
app.include_router(auth_router)

# Mount static files
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# --------------------------------------------------------------------------- #
#  Routes                                                                      #
# --------------------------------------------------------------------------- #

@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main UI."""
    index_path = STATIC_DIR / "index.html"
    return HTMLResponse(content=index_path.read_text(), status_code=200)


@app.post("/api/generate")
async def generate_text(
    prompt: str = Form(...),
    platform: str = Form("general"),
    count: int = Form(1),
):
    """Generate one or more text-only social media posts via GPT-5.2."""
    result = generate_text_post(prompt, platform, count)
    return JSONResponse(content=result)


@app.post("/api/generate-image")
async def generate_image_endpoint(
    prompt: str = Form(...),
    platform: str = Form("general"),
    count: int = Form(1),
    font_size: int = Form(48),
    text_color: str = Form("#FFFFFF"),
    alignment: str = Form("center"),
    bg_color: str = Form("#1a1a2e"),
    gradient: bool = Form(False),
    gradient_start: str = Form("#0f0c29"),
    gradient_end: str = Form("#302b63"),
    width: int = Form(1080),
    height: int = Form(1080),
    bg_image: Optional[UploadFile] = File(None),
):
    """Generate one or more image posts (GPT-5.2 text + Pillow rendering)."""
    options = PostOptions(
        text_style=TextStyle(
            font_size=font_size,
            text_color=text_color,
            alignment=alignment,
        ),
        bg_style=BackgroundStyle(
            width=width,
            height=height,
            bg_color=bg_color,
            gradient=gradient,
            gradient_color_start=gradient_start,
            gradient_color_end=gradient_end,
        ),
    )

    bg_bytes = None
    if bg_image and bg_image.filename:
        bg_bytes = await bg_image.read()

    results = generate_image_post(prompt, options, platform, count, bg_bytes)

    # Return as JSON with base64-encoded images
    variations = []
    for png_bytes, text in results:
        variations.append({
            "image_b64": base64.b64encode(png_bytes).decode("ascii"),
            "text": text,
        })

    return JSONResponse(content={"variations": variations, "count": len(variations)})


# --------------------------------------------------------------------------- #
#  Publish to social media                                                     #
# --------------------------------------------------------------------------- #

@app.post("/api/publish")
async def publish_post(
    platform: str = Form(...),
    text: str = Form(""),
    image: Optional[UploadFile] = File(None),
):
    """Publish generated content to a connected social media platform."""
    image_bytes = None
    if image and image.filename:
        image_bytes = await image.read()

    if platform == "linkedin":
        result = await publish_to_linkedin(text, image_bytes)
    elif platform == "facebook":
        result = await publish_to_facebook(text, image_bytes)
    elif platform == "instagram":
        result = await publish_to_instagram(text, image_bytes=image_bytes)
    else:
        result = {"success": False, "error": f"Unknown platform: {platform}"}

    status_code = 200 if result.get("success") else 400
    return JSONResponse(content=result, status_code=status_code)
