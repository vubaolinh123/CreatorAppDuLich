"""Update image_path in venues.json to point to the actual thumb files."""
import json
from pathlib import Path

BASE = Path(__file__).parent
DB = BASE / "dulich-pipeline" / "data" / "venues.json"
THUMBS_A = BASE / "thumbs"
THUMBS_B = BASE.parent.parent / "he thong edit video du lich" / "CreatorAppDuLich" / "thumbs"
THUMBS = THUMBS_A if THUMBS_A.exists() else THUMBS_B

with open(DB, encoding="utf-8") as f:
    db = json.load(f)

updated = 0
for v in db["venues"]:
    thumb = THUMBS / (v["name"] + ".jpg")
    if thumb.exists():
        v["image_path"] = str(thumb.resolve())
        updated += 1

with open(DB, "w", encoding="utf-8") as f:
    json.dump(db, f, ensure_ascii=False, indent=2)

total = len(db["venues"])
no_img = [v["name"] for v in db["venues"] if not v.get("image_path") or not Path(v["image_path"]).exists()]
print(f"Updated: {updated}/{total} venues have image_path")
if no_img:
    print("Missing images:", no_img)
else:
    print("All venues have valid image_path")
