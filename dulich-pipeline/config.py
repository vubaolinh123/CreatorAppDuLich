"""Pipeline Configuration — Central config for the LangGraph content pipeline."""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()


@dataclass
class PipelineConfig:
    # --- AI Models ---
    anthropic_api_key: str = ""
    elevenlabs_api_key: str = ""

    # --- Voice ---
    vbee_api_key: str = ""          # Vbee.ai API key (tiếng Việt TTS)
    voice_provider: str = "vbee"    # "vbee" | "edge" | "elevenlabs" | "mock"

    # --- Google ---
    google_sheet_id: str = ""
    google_credentials_path: str = "credentials.json"

    # --- MongoDB ---
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "dulichapp"

    # --- Output ---
    output_dir: str = "./output"
    dashboard_url: str = "http://localhost:3000"

    # --- Resource / Worker config ---
    max_workers: int = 2            # Số jobs chạy song song
    ram_gb: float = 4.0             # RAM giới hạn (GB)
    cpu_cores: int = 2              # Số CPU cores có thể dùng

    # --- Creator Voices ---
    creator_voices: dict = field(default=None)

    def __post_init__(self):
        if not self.anthropic_api_key:
            self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not self.elevenlabs_api_key:
            self.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", "")
        if not self.vbee_api_key:
            self.vbee_api_key = os.getenv("VBEE_API_KEY", "")
        
        # Override defaults with env only if they match their dataclass default values
        if self.voice_provider == "vbee":
            self.voice_provider = os.getenv("VOICE_PROVIDER", "vbee")
        if not self.google_sheet_id:
            self.google_sheet_id = os.getenv("GOOGLE_SHEET_ID", "")
        if self.mongo_uri == "mongodb://localhost:27017":
            self.mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        if self.mongo_db_name == "dulichapp":
            self.mongo_db_name = os.getenv("MONGO_DB_NAME", "dulichapp")
        if self.dashboard_url == "http://localhost:3000":
            self.dashboard_url = os.getenv("DASHBOARD_URL", "http://localhost:3000")
        if self.max_workers == 2:
            self.max_workers = int(os.getenv("MAX_WORKERS", "2"))
        if self.ram_gb == 4.0:
            self.ram_gb = float(os.getenv("RAM_GB", "4.0"))
        if self.cpu_cores == 2:
            self.cpu_cores = int(os.getenv("CPU_CORES", "2"))

        if self.creator_voices is None:
            self.creator_voices = {
                "creator1": os.getenv("CREATOR1_VOICE_ID", ""),
                "creator2": os.getenv("CREATOR2_VOICE_ID", ""),
                "creator3": os.getenv("CREATOR3_VOICE_ID", ""),
                "creator4": os.getenv("CREATOR4_VOICE_ID", ""),
                "creator5": os.getenv("CREATOR5_VOICE_ID", ""),
            }

    @property
    def output_video_dir(self) -> str:
        return f"{self.output_dir}/videos"

    @property
    def output_audio_dir(self) -> str:
        return f"{self.output_dir}/audio"

    @property
    def output_image_dir(self) -> str:
        return f"{self.output_dir}/images"

    @property
    def output_briefs_dir(self) -> str:
        return f"{self.output_dir}/briefs"


config = PipelineConfig()
