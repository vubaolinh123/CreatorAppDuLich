"""
pexels_client.py — Stock photo retriever.
Dual-mode:
  - Online: Queries Pexels search API and downloads photos.
  - Offline (Mock): Generates beautiful abstract gradient placeholder images using Pillow.
"""

from __future__ import annotations

import os
import random
import urllib.request
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFilter

STOCK_DIR = Path("./output/stock")
STOCK_DIR.mkdir(parents=True, exist_ok=True)

# ── Color Palettes for G gradients ───────────────────────────────────────────
GRADIENT_PALETTES = [
    ((30, 27, 75), (124, 58, 237)),   # Indigo to Purple
    ((15, 23, 42), (56, 189, 248)),   # Slate to Sky Blue
    ((6, 78, 59), (16, 185, 129)),    # Emerald to Green
    ((67, 20, 7), (249, 115, 22)),     # Rust to Orange
    ((88, 28, 135), (236, 72, 153)),  # Purple to Pink
]


def search_photos(query: str, count: int = 3) -> list[str]:
    """
    Search and download photos.
    Returns list of local file paths.
    """
    api_key = os.getenv("PEXELS_API_KEY", "")
    
    if api_key and api_key != "your-pexels-api-key":
        try:
            return _download_from_pexels(query, count, api_key)
        except Exception as e:
            print(f"[Pexels] ⚠ Error fetching from API: {e}. Falling back to mock generator.")
            
    # Mock fallback
    return _generate_mock_photos(query, count)


def _download_from_pexels(query: str, count: int, api_key: str) -> list[str]:
    """Query Pexels API and download photos."""
    import json
    import urllib.parse
    
    encoded_query = urllib.parse.quote(query)
    url = f"https://api.pexels.com/v1/search?query={encoded_query}&per_page={count}"
    
    req = urllib.request.Request(url)
    req.add_header("Authorization", api_key)
    
    local_paths = []
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            photos = data.get("photos", [])
            
            for idx, photo in enumerate(photos):
                photo_url = photo.get("src", {}).get("large")
                if not photo_url:
                    continue
                    
                photo_id = photo.get("id", f"unknown_{idx}")
                clean_query = "".join(c for c in query if c.isalnum() or c in (" ", "_")).replace(" ", "_")
                filename = f"pexels_{clean_query}_{photo_id}.jpg"
                dest_path = STOCK_DIR / filename
                
                # Download image
                urllib.request.urlretrieve(photo_url, str(dest_path))
                print(f"[Pexels] ✓ Downloaded: {dest_path}")
                local_paths.append(str(dest_path))
                
    except Exception as e:
        raise RuntimeError(f"Pexels download failed: {e}")
        
    if not local_paths:
        raise RuntimeError("No photos found or downloaded from API.")
        
    return local_paths


def _generate_mock_photos(query: str, count: int) -> list[str]:
    """Generate high-quality abstract gradient images with Pillow."""
    local_paths = []
    
    for i in range(count):
        width, height = 1080, 1080
        # Create gradient base
        base = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(base)
        
        # Select random palette
        color1, color2 = random.choice(GRADIENT_PALETTES)
        
        # Draw linear gradient
        for y in range(height):
            ratio = y / height
            r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
            g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
            b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))
            
        # Draw some abstract geometric overlays (spheres, lines) for design depth
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw_ov = ImageDraw.Draw(overlay)
        
        for _ in range(5):
            radius = random.randint(100, 300)
            cx = random.randint(0, width)
            cy = random.randint(0, height)
            draw_ov.ellipse(
                [cx - radius, cy - radius, cx + radius, cy + radius],
                fill=(255, 255, 255, random.randint(10, 30))
            )
            
        # Apply slight blur to overlay for smooth integration
        overlay = overlay.filter(ImageFilter.GaussianBlur(10))
        base.paste(overlay, (0, 0), overlay)
        
        # Draw grid patterns
        draw_pattern = ImageDraw.Draw(base)
        grid_size = 60
        for x in range(0, width, grid_size):
            draw_pattern.line([(x, 0), (x, height)], fill=(255, 255, 255, 8))
        for y in range(0, height, grid_size):
            draw_pattern.line([(0, y), (width, y)], fill=(255, 255, 255, 8))
            
        # Write text description on image for travel theme
        draw_text = ImageDraw.Draw(base)
        # Simple crosshairs
        draw_text.line([(width // 2 - 20, height // 2), (width // 2 + 20, height // 2)], fill=(255, 255, 255, 100))
        draw_text.line([(width // 2, height // 2 - 20), (width // 2, height // 2 + 20)], fill=(255, 255, 255, 100))
        
        clean_query = "".join(c for c in query if c.isalnum() or c in (" ", "_")).replace(" ", "_")
        filename = f"mock_stock_{clean_query}_{i + 1}.jpg"
        dest_path = STOCK_DIR / filename
        
        base.save(str(dest_path), quality=95)
        print(f"[Pexels] ✓ Generated Mock Image: {dest_path}")
        local_paths.append(str(dest_path))
        
    return local_paths
