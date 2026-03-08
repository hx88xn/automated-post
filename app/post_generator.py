"""
Post generation logic — GPT-5.2 powered text generation + Pillow image compositing.
"""

import io
import os
from dataclasses import dataclass, field
from typing import Optional

from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont


# ---------------------------------------------------------------------------
# OpenAI client (initialised lazily so import doesn't fail without key)
# ---------------------------------------------------------------------------

_client: Optional[OpenAI] = None

def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
    return _client

MODEL = "gpt-5.2-2025-12-11"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class TextStyle:
    font_size: int = 48
    text_color: str = "#FFFFFF"
    alignment: str = "center"          # left | center | right
    line_spacing: int = 12


@dataclass
class BackgroundStyle:
    width: int = 1080
    height: int = 1080
    bg_color: str = "#1a1a2e"
    gradient: bool = False
    gradient_color_start: str = "#0f0c29"
    gradient_color_end: str = "#302b63"


@dataclass
class PostOptions:
    text_style: TextStyle = field(default_factory=TextStyle)
    bg_style: BackgroundStyle = field(default_factory=BackgroundStyle)


# ---------------------------------------------------------------------------
# GPT-5.2 powered text generation
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_TEXT = """You are an expert social media copywriter. Given a user prompt, generate a compelling, 
engaging social media post. Follow these rules:
- Keep the post concise and impactful
- Use appropriate tone for the platform specified
- Include relevant emojis where appropriate
- Add relevant hashtags at the end (3-5 hashtags)
- Do NOT include any meta-commentary, just output the post text directly
- For Twitter/X: stay under 280 characters
- For Instagram: can be longer, more descriptive, up to 2200 characters
- For LinkedIn: professional tone, can be longer form
- For Facebook: conversational, medium length
- For General: balanced, medium length"""

SYSTEM_PROMPT_IMAGE = """You are an expert social media copywriter. Given a user prompt, generate a compelling, 
engaging social media post that will be rendered as text on an image. Follow these rules:
- Keep the post concise and impactful — shorter is better for image posts
- Use appropriate tone for the platform specified
- Do NOT use any emojis — the text will be rendered on an image where emojis cannot display properly
- Do NOT use hashtags — they clutter image posts
- Do NOT include any meta-commentary, just output the post text directly
- Keep it to 1-3 short sentences maximum
- For Twitter/X: very short, punchy
- For Instagram: inspirational quote style
- For LinkedIn: professional and insightful
- For Facebook: conversational
- For General: balanced, medium length"""


def generate_text_post(prompt: str, platform: str = "general", count: int = 1, for_image: bool = False) -> dict:
    """Use GPT-5.2 to generate one or more social media post variations."""
    client = _get_client()
    count = max(1, min(count, 10))  # clamp 1–10

    system_prompt = SYSTEM_PROMPT_IMAGE if for_image else SYSTEM_PROMPT_TEXT

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Platform: {platform}\n\nCreate a post about: {prompt}"},
        ],
        temperature=0.9,
        max_completion_tokens=1024,
        n=count,
    )

    variations = []
    for choice in response.choices:
        content = choice.message.content.strip()
        lines = [l for l in content.splitlines() if l.strip()]
        variations.append({
            "content": content,
            "character_count": len(content),
            "line_count": len(lines),
        })

    return {
        "variations": variations,
        "count": len(variations),
        "platform": platform,
        "model": MODEL,
    }


# ---------------------------------------------------------------------------
# Image post generation (Pillow)
# ---------------------------------------------------------------------------

def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def _create_gradient_fast(width: int, height: int, start_hex: str, end_hex: str) -> Image.Image:
    """Create a vertical linear gradient image (fast, row-based)."""
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)
    top = _hex_to_rgb(start_hex)
    bottom = _hex_to_rgb(end_hex)
    for y in range(height):
        ratio = y / height
        r = int(top[0] + (bottom[0] - top[0]) * ratio)
        g = int(top[1] + (bottom[1] - top[1]) * ratio)
        b = int(top[2] + (bottom[2] - top[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    return img


def _get_font(size: int) -> ImageFont.FreeTypeFont:
    """Return a TrueType font; fall back to the default bitmap font."""
    font_paths = [
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Word-wrap text to fit inside max_width pixels."""
    words = text.split()
    lines: list[str] = []
    current_line = ""
    for word in words:
        test = f"{current_line} {word}".strip()
        bbox = font.getbbox(test)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            current_line = test
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines or [""]


def _render_text_on_image(
    text: str,
    base_img: Image.Image,
    options: PostOptions,
) -> bytes:
    """Render text onto a copy of the base image and return PNG bytes."""
    ts = options.text_style
    bs = options.bg_style
    width, height = bs.width, bs.height

    img = base_img.copy()
    draw = ImageDraw.Draw(img)
    font = _get_font(ts.font_size)

    padding = 80
    max_text_width = width - padding * 2
    wrapped_lines = _wrap_text(text, font, max_text_width)

    line_heights: list[int] = []
    for line in wrapped_lines:
        bbox = font.getbbox(line)
        line_heights.append(bbox[3] - bbox[1])
    total_text_height = sum(line_heights) + ts.line_spacing * (len(wrapped_lines) - 1)

    y = (height - total_text_height) // 2
    text_color = _hex_to_rgb(ts.text_color)

    for i, line in enumerate(wrapped_lines):
        bbox = font.getbbox(line)
        lw = bbox[2] - bbox[0]
        if ts.alignment == "center":
            x = (width - lw) // 2
        elif ts.alignment == "right":
            x = width - padding - lw
        else:
            x = padding

        draw.text((x + 2, y + 2), line, fill=(0, 0, 0), font=font)
        draw.text((x, y), line, fill=text_color, font=font)
        y += line_heights[i] + ts.line_spacing

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_image_post(
    prompt: str,
    options: PostOptions,
    platform: str = "general",
    count: int = 1,
    bg_image_bytes: Optional[bytes] = None,
) -> list[tuple[bytes, str]]:
    """
    Generate multiple post text variations via GPT-5.2, render each onto a
    background image, and return a list of (png_bytes, generated_text) tuples.
    """
    # Step 1 — Generate text variations
    result = generate_text_post(prompt, platform, count, for_image=True)
    variations = result["variations"]

    # Step 2 — Create base background image
    bs = options.bg_style
    width, height = bs.width, bs.height

    if bg_image_bytes:
        base_img = Image.open(io.BytesIO(bg_image_bytes)).convert("RGB")
        base_img = base_img.resize((width, height), Image.LANCZOS)
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 140))
        base_img = Image.alpha_composite(base_img.convert("RGBA"), overlay).convert("RGB")
    elif bs.gradient:
        base_img = _create_gradient_fast(width, height, bs.gradient_color_start, bs.gradient_color_end)
    else:
        base_img = Image.new("RGB", (width, height), bs.bg_color)

    # Step 3 — Render each variation
    results = []
    for var in variations:
        png_bytes = _render_text_on_image(var["content"], base_img, options)
        results.append((png_bytes, var["content"]))

    return results
