"""
image_composer.py — Pillow-based image composition tool.
Supports 10 design sizes, Canva template alpha overlay, and Unicode text rendering.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUTPUT_DIR = Path("./output/albums")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ASSETS_DIR = Path("./assets")
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# ── 10 Seeding Formats ────────────────────────────────────────────────────────
FORMATS = {
    "story": (1080, 1920, "Story Dọc (1080x1920)"),
    "feed_square": (1080, 1080, "Feed Vuông (1080x1080)"),
    "feed_portrait": (1080, 1350, "Feed Portrait (1080x1350)"),
    "reels_cover": (1080, 1920, "Reels Cover (1080x1920)"),
    "youtube_thumb": (1280, 720, "YouTube Thumbnail (1280x720)"),
    "facebook_cover": (820, 312, "Facebook Cover (820x312)"),
    "pinterest": (1000, 1500, "Pinterest Pin (1000x1500)"),
    "carousel_slide": (1080, 1080, "Carousel Slide (1080x1080)"),
    "blog_header": (1200, 630, "Blog Header (1200x630)"),
    "seeding_card": (800, 800, "Seeding Card (800x800)"),
}


def get_system_font(size: int = 40) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Find a system truetype font supporting Unicode (Vietnamese) on Windows/Unix."""
    paths_to_check = []
    
    if sys.platform.startswith("win"):
        # Windows Fonts directory
        paths_to_check.extend([
            "C:\\Windows\\Fonts\\Arial.ttf",
            "C:\\Windows\\Fonts\\tahoma.ttf",
            "C:\\Windows\\Fonts\\segoeui.ttf",
            "C:\\Windows\\Fonts\\Calibri.ttf"
        ])
    elif sys.platform.startswith("darwin"):
        # macOS Fonts
        paths_to_check.extend([
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc"
        ])
    else:
        # Linux Fonts
        paths_to_check.extend([
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
        ])
        
    for path in paths_to_check:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
                
    # Fallback to default PIL font (doesn't support custom size well, but avoids crash)
    return ImageFont.load_default()


def ensure_mock_canva_template(width: int, height: int) -> str:
    """Generate a mock Canva frame (transparent PNG with border overlay) if missing."""
    template_path = ASSETS_DIR / f"canva_mock_{width}x{height}.png"
    if template_path.exists():
        return str(template_path)
        
    # Create image with transparent alpha channel
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw artistic dark translucent border frames
    border = min(width, height) // 12
    # Translucent border (dark indigo-purple hue)
    draw.rectangle([0, 0, width, height], fill=None, outline=(67, 56, 202, 100), width=6)
    
    # Header block
    draw.rectangle([0, 0, width, border * 2], fill=(17, 12, 46, 230))
    # Footer block
    draw.rectangle([0, height - border * 2, width, height], fill=(17, 12, 46, 230))
    
    # Geometric card details
    draw.line([border, border * 2, width - border, border * 2], fill=(124, 58, 237, 255), width=4)
    
    # Draw logo icon on mock template
    draw.ellipse([border, border // 3, border * 2, border * 4 // 3], fill=(124, 58, 237, 255))
    draw.line([border * 1.5, border // 2, border * 1.5, border * 7 // 6], fill=(255, 255, 255, 255), width=3)
    
    img.save(str(template_path), "PNG")
    print(f"[Composer] Generated mock Canva template: {template_path}")
    return str(template_path)


def compose_image(
    bg_image_path: str,
    output_name: str,
    format_name: str = "feed_square",
    title: str = "Khám phá Việt Nam",
    subtitle: str = "Những hành trình tuyệt vời cùng Creator",
    canva_template_path: Optional[str] = None,
) -> str:
    """
    Compose final image from background + Canva template + texts.
    
    Args:
        bg_image_path: Travel stock image path.
        output_name: Base filename (no extension) to write to output/albums/.
        format_name: Preset sizing format.
        title: Large text overlay.
        subtitle: Small description text overlay.
        canva_template_path: Path to PNG border template (optional).
    """
    width, height, desc = FORMATS.get(format_name, FORMATS["feed_square"])
    output_path = OUTPUT_DIR / f"{output_name}_{format_name}.jpg"
    
    # 1. Load background image and resize/crop to fit dimensions
    if bg_image_path and os.path.exists(bg_image_path):
        bg_img = Image.open(bg_image_path)
    else:
        # Fallback: create random dark gradient background if missing
        bg_img = Image.new("RGB", (width, height), (30, 27, 75))
        draw = ImageDraw.Draw(bg_img)
        draw.rectangle([0, 0, width, height], fill=None, outline=(124, 58, 237), width=20)
        
    # Crop and scale background image to fit perfectly (cover ratio)
    bg_w, bg_h = bg_img.size
    target_ratio = width / height
    current_ratio = bg_w / bg_h
    
    if current_ratio > target_ratio:
        # Background is wider
        new_w = int(bg_h * target_ratio)
        offset = (bg_w - new_w) // 2
        bg_img = bg_img.crop((offset, 0, offset + new_w, bg_h))
    else:
        # Background is taller
        new_h = int(bg_w / target_ratio)
        offset = (bg_h - new_h) // 2
        bg_img = bg_img.crop((0, offset, bg_w, offset + new_h))
        
    bg_img = bg_img.resize((width, height), Image.Resampling.LANCZOS)
    
    # Apply soft blur/dark overlay to background to ensure text readability
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 90)) # 95 alpha black overlay
    bg_img.paste(overlay, (0, 0), overlay)
    
    # 2. Get Canva Template
    if not canva_template_path or not os.path.exists(canva_template_path):
        canva_template_path = ensure_mock_canva_template(width, height)
        
    template_img = Image.open(canva_template_path).convert("RGBA")
    # Resize template if dimensions do not match
    if template_img.size != (width, height):
        template_img = template_img.resize((width, height), Image.Resampling.LANCZOS)
        
    # Composite template ON TOP of background image
    final_img = Image.new("RGBA", (width, height))
    final_img.paste(bg_img, (0, 0))
    final_img.paste(template_img, (0, 0), template_img)
    
    # Convert back to RGB for drawing and saving as JPEG
    final_img = final_img.convert("RGB")
    draw = ImageDraw.Draw(final_img)
    
    # 3. Draw Typography/Text overlays
    border = min(width, height) // 12
    
    # Title Font Setup
    title_size = max(18, min(width, height) // 16)
    sub_size = max(12, min(width, height) // 28)
    
    title_font = get_system_font(title_size)
    sub_font = get_system_font(sub_size)
    
    # Center text coordinates inside top/bottom bars or overlay on center
    title_text = title.strip()
    sub_text = subtitle.strip()
    
    # Draw Title inside the top banner or center depending on size
    # We will wrap or truncate text if it is too wide
    def draw_centered_text(d_draw, text, y_pos, font, fill_color):
        try:
            # Pillow 10+ textlength/textbbox
            w = d_draw.textlength(text, font=font)
        except AttributeError:
            # Fallback for older PIL
            w, _ = d_draw.textsize(text, font=font)
            
        x_pos = (width - w) // 2
        d_draw.text((x_pos, y_pos), text, font=font, fill=fill_color)
        
    # Top banner position
    title_y = border // 2 if border // 2 > 10 else 20
    draw_centered_text(draw, title_text, title_y, title_font, (255, 255, 255))
    
    # Bottom banner position
    sub_y = height - border - sub_size // 2
    draw_centered_text(draw, sub_text, sub_y, sub_font, (209, 213, 219))
    
    # Draw seeding tags/decorations (e.g. #dulich, etc.) at the very bottom
    tag_font = get_system_font(max(10, sub_size - 4))
    draw_centered_text(draw, "#seeding #travelvlog #vietnam", height - border // 2, tag_font, (129, 140, 248))
    
    # Save Image
    final_img.save(str(output_path), "JPEG", quality=92)
    print(f"[Composer] ✓ Composed image ({desc}): {output_path}")
    return str(output_path)
