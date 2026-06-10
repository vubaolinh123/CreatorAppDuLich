"""
Voice Generator — Generates voiceover audio.
Providers:
  - Vbee.ai   (primary — Vietnamese TTS, mock mode nếu chưa có API key)
  - ElevenLabs (secondary — bilingual, instant voice clone)
  - Mock       (fallback — silent WAV, dùng khi không có API key nào)
"""

from __future__ import annotations

import os
import wave
from pathlib import Path
from typing import Optional

# ── ElevenLabs (optional) ─────────────────────────────────────────────────────
try:
    from elevenlabs import save
    from elevenlabs.client import ElevenLabs
    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False

# ── requests (for Vbee REST API) ──────────────────────────────────────────────
try:
    import requests as _requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

OUTPUT_DIR = Path("./output/audio")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ── Vbee.ai voice codes (built-in standard voices) ───────────────────────────
VBEE_STANDARD_VOICES = {
    "hn_female_lananh": "hn_female_lananh",     # Hà Nội nữ
    "hn_male_minhtuan": "hn_male_minhtuan",     # Hà Nội nam
    "hcm_male_ducanh": "hcm_male_ducanh",       # HCM nam
    "hn_female_ngocmai": "hn_female_ngocmai",   # Hà Nội nữ
    # ElevenLabs handled separately
    "default": "hn_female_lananh",
}

VBEE_API_BASE = "https://vbee.vn/api/v1/tts"


class VoiceGenerator:
    """
    Unified voice generator.
    Chọn provider theo thứ tự: vbee → elevenlabs → mock
    """

    def __init__(self, provider: str = "vbee"):
        self.provider = provider
        self._el_client: Optional[ElevenLabs] = None
        self._vbee_key: str = os.getenv("VBEE_API_KEY", "")
        self._el_key: str = os.getenv("ELEVENLABS_API_KEY", "")

        if provider == "elevenlabs" and ELEVENLABS_AVAILABLE and self._el_key:
            self._el_client = ElevenLabs(api_key=self._el_key)

    # ── Public API ────────────────────────────────────────────────────────────

    def generate_voice(
        self,
        text: str,
        voice_id: str = "default",
        output_name: str = "voice_output",
        language: str = "vi",
        speed: float = 1.0,
    ) -> str:
        """
        Generate TTS audio and save to output/audio/.
        Returns absolute path to generated audio file.
        """
        # Try Vbee first
        if self.provider in ("vbee", "auto"):
            if self._vbee_key:
                path = self._vbee_generate(text, voice_id, output_name, speed)
                if path:
                    return path
            else:
                print("[Voice] VBEE_API_KEY không có — Tự động fallback sang Microsoft Edge TTS (free).")
                path = self._edge_generate(text, voice_id, output_name, speed)
                if path:
                    return path

        # Try Edge TTS explicitly
        if self.provider == "edge":
            path = self._edge_generate(text, voice_id, output_name, speed)
            if path:
                return path

        # Try ElevenLabs
        if self.provider in ("elevenlabs", "auto") and self._el_client:
            path = self._elevenlabs_generate(text, voice_id, output_name)
            if path:
                return path

        # Fallback: edge-tts (free) first, then mock WAV
        print("[Voice] Thử tạo giọng nói với Microsoft Edge TTS làm fallback...")
        path = self._edge_generate(text, voice_id, output_name, speed)
        if path:
            return path

        # Last resort: silent mock WAV
        return self._mock_generate(output_name, duration_sec=max(5, len(text) // 10))

    def clone_voice(self, audio_samples: list[str], name: str) -> str:
        """
        Clone a voice from sample files.
        Only supported with ElevenLabs.
        Returns voice_id string.
        """
        if self._el_client:
            voice = self._el_client.clone(name=name, files=audio_samples)
            return voice.voice_id

        print(f"[Voice] Voice cloning not available (ElevenLabs key missing). Returning mock ID.")
        return f"mock_clone_{name.lower().replace(' ', '_')}"

    # ── Vbee.ai ───────────────────────────────────────────────────────────────

    def _vbee_generate(
        self,
        text: str,
        voice_id: str,
        output_name: str,
        speed: float = 1.0,
    ) -> Optional[str]:
        if not self._vbee_key:
            print("[Voice] VBEE_API_KEY không có — skip Vbee, dùng mock.")
            return None

        if not REQUESTS_AVAILABLE:
            print("[Voice] requests không được cài — skip Vbee.")
            return None

        voice_code = VBEE_STANDARD_VOICES.get(voice_id, VBEE_STANDARD_VOICES["default"])
        output_path = OUTPUT_DIR / f"{output_name}.mp3"

        try:
            resp = _requests.post(
                VBEE_API_BASE,
                headers={
                    "Authorization": f"Bearer {self._vbee_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "voice_code": voice_code,
                    "speed_ratio": speed,
                    "output_format": "mp3",
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            # Vbee trả về URL audio → download
            audio_url = data.get("audio_url") or data.get("url")
            if audio_url:
                audio_resp = _requests.get(audio_url, timeout=30)
                audio_resp.raise_for_status()
                output_path.write_bytes(audio_resp.content)
                print(f"[Voice] ✓ Vbee TTS saved: {output_path}")
                return str(output_path)

            # Một số phiên bản Vbee trả về base64
            audio_b64 = data.get("audio_base64") or data.get("data")
            if audio_b64:
                import base64
                output_path.write_bytes(base64.b64decode(audio_b64))
                print(f"[Voice] ✓ Vbee TTS (base64) saved: {output_path}")
                return str(output_path)

        except Exception as e:
            print(f"[Voice] ⚠ Vbee API lỗi: {e}. Fallback sang mock.")

        return None

    # ── ElevenLabs ───────────────────────────────────────────────────────────

    def _elevenlabs_generate(
        self,
        text: str,
        voice_id: str,
        output_name: str,
    ) -> Optional[str]:
        if not self._el_client:
            return None

        output_path = OUTPUT_DIR / f"{output_name}.mp3"
        try:
            audio = self._el_client.text_to_speech.convert(
                voice_id=voice_id,
                text=text,
                model_id="eleven_multilingual_v2",
            )
            save(audio, str(output_path))
            print(f"[Voice] ✓ ElevenLabs TTS saved: {output_path}")
            return str(output_path)
        except Exception as e:
            print(f"[Voice] ⚠ ElevenLabs lỗi: {e}. Fallback sang mock.")
            return None

    # ── Microsoft Edge TTS (Free) ───────────────────────────────────────────

    def _edge_generate(
        self,
        text: str,
        voice_id: str,
        output_name: str,
        speed: float = 1.0,
    ) -> Optional[str]:
        output_path = OUTPUT_DIR / f"{output_name}.mp3"
        try:
            import edge_tts
        except ImportError:
            print("[Voice] edge-tts package not installed! Can't generate voice.")
            return None

        # Resolve voice mapping
        edge_voice = "vi-VN-HoaiMyNeural"
        v_id_lower = voice_id.lower()
        if any(k in v_id_lower for k in ["namminh", "minhtuan", "ducanh", "male"]):
            edge_voice = "vi-VN-NamMinhNeural"
        elif any(k in v_id_lower for k in ["hoaimy", "lananh", "ngocmai", "female"]):
            edge_voice = "vi-VN-HoaiMyNeural"
        else:
            edge_voice = "vi-VN-HoaiMyNeural"

        # Rate representation in edge-tts: e.g. "+10%", "-5%"
        rate_percent = int((speed - 1.0) * 100)
        rate_str = f"{rate_percent:+d}%"

        async def run_tts():
            import time
            last_err = None
            for attempt in range(3):
                try:
                    communicate = edge_tts.Communicate(text, edge_voice, rate=rate_str, boundary="WordBoundary")
                    words = []
                    
                    with open(output_path, "wb") as fp:
                        async for chunk in communicate.stream():
                            if chunk["type"] == "audio":
                                fp.write(chunk["data"])
                            elif chunk["type"] == "WordBoundary":
                                start_sec = chunk["offset"] / 10000000.0
                                dur_sec = chunk["duration"] / 10000000.0
                                words.append({
                                    "start": start_sec,
                                    "end": start_sec + dur_sec,
                                    "word": chunk["text"]
                                })
                    if len(words) > 0:
                        return words
                    raise Exception("No words timings generated.")
                except Exception as e:
                    last_err = e
                    print(f"[Voice] Edge TTS attempt {attempt + 1} failed: {e}")
                    if attempt < 2:
                        await asyncio.sleep(1.0)
            raise last_err

        # Execute async task synchronously
        import asyncio
        import concurrent.futures
        import json

        # Loop checking
        try:
            loop = asyncio.get_running_loop()
            is_running = True
        except RuntimeError:
            is_running = False

        try:
            if is_running:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, run_tts())
                    words = future.result()
            else:
                words = asyncio.run(run_tts())

            # Write word timings JSON file
            words_path = output_path.with_suffix(".words.json")
            words_path.write_text(json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[Voice] ✓ Edge TTS saved: {output_path} and timing details: {words_path}")
            return str(output_path.resolve())

        except Exception as e:
            print(f"[Voice] ⚠ Edge TTS error: {e}")
            if output_path.exists():
                try:
                    output_path.unlink()
                except Exception:
                    pass
            return None

    # ── Mock (silent WAV) ────────────────────────────────────────────────────

    def _mock_generate(self, output_name: str, duration_sec: int = 10) -> str:
        """Generate a silent WAV file as placeholder (no external API needed)."""
        output_path = OUTPUT_DIR / f"{output_name}.wav"
        sample_rate = 24000
        n_channels = 1
        sample_width = 2  # 16-bit

        n_frames = sample_rate * duration_sec
        try:
            with wave.open(str(output_path), "wb") as wf:
                wf.setnchannels(n_channels)
                wf.setsampwidth(sample_width)
                wf.setframerate(sample_rate)
                wf.writeframes(b"\x00" * n_frames * sample_width)
            print(f"[Voice] ✓ Mock silent audio ({duration_sec}s): {output_path}")
        except Exception as e:
            print(f"[Voice] ⚠ Không tạo được mock audio: {e}")
            # Fallback: empty file
            output_path.write_bytes(b"")

        return str(output_path)
