from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_gemini_image_generation_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ENABLE_GEMINI_AI_IMAGE", raising=False)

    from tools.ai_image_gen import generate_infographic, recreate_all_from_tiktok

    result = generate_infographic({"template": "list8"})
    recreated = recreate_all_from_tiktok("https://www.tiktok.com/@test/photo/1")

    assert result["success"] is False
    assert recreated["success"] is False
    assert "tạm dừng" in result["error"]
    assert "tạm dừng" in recreated["error"]


def test_runtime_apify_code_only_reads_vietchinh_key():
    runtime_files = [
        ROOT / "server.py",
        ROOT / "tools" / "news_research.py",
        ROOT / "tools" / "news_youtube.py",
        ROOT / "tools" / "tiktok_photos.py",
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in runtime_files)

    assert "APIFY_KEY_VIETCHINH" in source
    assert 'os.getenv("APIFY_API_KEY")' not in source
    assert 'os.getenv("APIFY_TOKEN")' not in source
