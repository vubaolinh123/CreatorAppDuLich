import os
from PIL import Image, ImageDraw

def create_icons():
    icon_dir = "../dulich-desktop/src-tauri/icons"
    os.makedirs(icon_dir, exist_ok=True)
    
    # Create a simple icon: purple background with a palm tree emoji shape or text
    def generate_img(size):
        img = Image.new("RGBA", (size, size), (124, 58, 237, 255)) # purple color
        draw = ImageDraw.Draw(img)
        # Draw a simple palm tree representation
        draw.ellipse([size // 4, size // 4, size * 3 // 4, size * 3 // 4], fill=(255, 255, 255, 40))
        # Add basic design lines
        draw.line([size // 2, size // 4, size // 2, size * 3 // 4], fill=(255, 255, 255, 180), width=max(1, size // 20))
        draw.line([size // 4, size // 2, size * 3 // 4, size // 2], fill=(255, 255, 255, 180), width=max(1, size // 20))
        return img

    # Generate images
    img_32 = generate_img(32)
    img_128 = generate_img(128)
    img_256 = generate_img(256)
    
    img_32.save(os.path.join(icon_dir, "32x32.png"))
    img_128.save(os.path.join(icon_dir, "128x128.png"))
    img_256.save(os.path.join(icon_dir, "128x128@2x.png"))
    
    # Generate .ico
    img_256.save(os.path.join(icon_dir, "icon.ico"), format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    
    # Generate mock .icns (just copy the 256 png for compile fallback, or write placeholder)
    # On Windows cargo might not strictly validate icns structure unless building macOS target,
    # so we write a dummy file or copy the ico.
    with open(os.path.join(icon_dir, "icon.icns"), "wb") as f:
        f.write(b"MOCK ICNS CONTENT")
        
    print(f"✓ All icons created successfully at {icon_dir}")

if __name__ == "__main__":
    create_icons()
