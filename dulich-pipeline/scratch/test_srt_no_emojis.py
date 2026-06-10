import sys
from pathlib import Path

# Configure UTF-8 encoding for Windows CMD/PowerShell
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.subtitle_agent import generate_srt

# Sample script with emojis and icons
script = {
    "hook": "Đà Nẵng có gì vui? 😱 Khám phá ngay nhé! 👇",
    "body": "Đến đây bạn nhất định phải ăn bánh tráng cuốn thịt heo 🍜 và check-in Cầu Vàng 🌟. Đẹp cực kì luôn! 📍",
    "cta": "Nhấn follow mình để nhận thêm nhiều review nhé! 🎥🎙️"
}

print("Generating SRT...")
srt_path = generate_srt(script, output_name="test_clean_subtitles", voice_duration_sec=30.0)
print(f"SRT generated at: {srt_path}")

# Read and print generated SRT content
content = Path(srt_path).read_text(encoding="utf-8")
print("\nGenerated SRT Content:")
print(content)

# Assertions to verify no emojis or icons are present
emojis_to_check = ["😱", "👇", "🍜", "🌟", "📍", "🎥", "🎙️"]
has_emoji = False
for emoji in emojis_to_check:
    if emoji in content:
        print(f"FAIL: Found emoji '{emoji}' in generated subtitles!")
        has_emoji = True

if not has_emoji:
    print("SUCCESS: All emojis/icons were successfully stripped from subtitles!")
else:
    sys.exit(1)
