import shutil
from pathlib import Path

# Paths
brain_dir = Path("C:/Users/duyph/.gemini/antigravity/brain/d8e4bf40-3650-460f-935c-0aa71cf0a101")
dest_dir = Path("D:/ProjectWeb/DuLichAppWeb/dulich-desktop/public")
dest_dir.mkdir(parents=True, exist_ok=True)

files_to_copy = [
    "hook_green.png",
    "hook_pink.png",
    "hook_purple.png",
    "hook_floating_check.png",
    "hook_frame_check.png"
]

print("Starting to copy files...")
for f in files_to_copy:
    src_file = brain_dir / f
    dest_file = dest_dir / f
    if src_file.exists():
        shutil.copy(src_file, dest_file)
        print(f"Copied {f} to {dest_file}")
    else:
        print(f"Source file {src_file} does not exist!")
print("Copy completed.")
