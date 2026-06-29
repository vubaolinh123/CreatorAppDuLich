"""Merge thumbnail paths into real venues DB."""
import json
from pathlib import Path

REAL_DB   = Path(__file__).parent / "data" / "venues.json"
WRONG_DB  = Path(__file__).parent.parent.parent.parent / "he thong edit video du lich" / "CreatorAppDuLich" / "dulich-pipeline" / "data" / "venues.json"
THUMBS    = Path(__file__).parent.parent.parent.parent / "he thong edit video du lich" / "CreatorAppDuLich" / "thumbs"

with open(REAL_DB, encoding="utf-8") as f:
    db = json.load(f)

print(f"Real DB: {len(db['venues'])} venues")

# Map thumbnails to existing venues
updated = 0
for v in db["venues"]:
    thumb = THUMBS / f"{v['name']}.jpg"
    if thumb.exists():
        v["image_path"] = str(thumb)
        updated += 1
        print(f"  [OK] {v['name']}")
    else:
        print(f"  [--] {v['name']} — no thumb found")

# Add new venues from wrong-path DB
if WRONG_DB.exists():
    with open(WRONG_DB, encoding="utf-8") as f:
        wdb = json.load(f)
    existing = {v["name"] for v in db["venues"]}
    next_id = db.get("_next_id", len(db["venues"]) + 1)
    added = 0
    for wv in wdb["venues"]:
        if wv["name"] not in existing:
            thumb = THUMBS / f"{wv['name']}.jpg"
            wv["image_path"] = str(thumb) if thumb.exists() else ""
            wv["id"] = next_id
            db["venues"].append(wv)
            existing.add(wv["name"])
            next_id += 1
            added += 1
            print(f"  [+] Added: {wv['name']}")
    db["_next_id"] = next_id
    print(f"Added {added} new venues from merge")
else:
    print("Wrong-path DB not found, skipping merge")

with open(REAL_DB, "w", encoding="utf-8") as f:
    json.dump(db, f, ensure_ascii=False, indent=2)

print(f"\nDone: {updated} image_path updated, total {len(db['venues'])} venues in DB")
