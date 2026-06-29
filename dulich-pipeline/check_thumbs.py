# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from tools.venues_db import get_venues, resolve_image

venues = get_venues()
with_img = [(v["name"], resolve_image(v)) for v in venues if resolve_image(v)]
without = [v["name"] for v in venues if not resolve_image(v)]

print(f"Total: {len(venues)}, With image: {len(with_img)}, Without: {len(without)}")
print("\nWith image:")
for name, path in with_img[:10]:
    print(f"  {name}: {Path(path).name}")
print("\nWithout image:")
for name in without[:10]:
    print(f"  {name}")
