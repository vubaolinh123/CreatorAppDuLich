import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.db import seeding_col, new_doc, get_db

def seed():
    # Clean old ones first
    scol = seeding_col()
    try:
        scol.delete_many({"location": "Đà Nẵng"})
    except Exception:
        pass
        
    doc = new_doc(
        name="Mỳ Quảng Bà Mua",
        category="restaurant",
        location="Đà Nẵng",
        description="Mỳ Quảng vị đậm đà ngon nhất nhì Đà Nẵng, nổi tiếng với mỳ ếch và mỳ gà.",
        mention_guide="Hãy đề xuất làm địa điểm ăn sáng đậm chất bản địa Đà Nẵng.",
        status="active"
    )
    scol.insert_one(doc)
    print(f"✓ Seeded: {doc['name']} at {doc['location']}")

if __name__ == "__main__":
    seed()
