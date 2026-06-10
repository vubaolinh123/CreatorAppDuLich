import os
import sys
from pathlib import Path

# Configure UTF-8 encoding for Windows CMD/PowerShell to avoid print crashes
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.voice_generator import VoiceGenerator

def main():
    # Set the user's key in the environment
    user_key = "sk_8788e0366c9418cd18bbdd13d77c2e5933ea7a8e8abfdeb3"
    os.environ["ELEVENLABS_API_KEY"] = user_key
    print(f"Testing ElevenLabs key: {user_key[:5]}...{user_key[-5:]}")
    
    try:
        # Check if elevenlabs library is available
        from elevenlabs.client import ElevenLabs
        client = ElevenLabs(api_key=user_key)
        print("ElevenLabs library imported successfully.")
        
        # Test listing voices or fetching subscription details
        print("Attempting to fetch user/voices info from ElevenLabs...")
        user_info = client.user.get()
        print(f"Success! User tier: {user_info.subscription.tier}")
        
        # Test creating a small voiceover with the new Adam ID
        new_adam_id = "pNInz6obpgDQGcFmaJgB"
        print(f"Generating a test voice audio file with voice_id: {new_adam_id}...")
        generator = VoiceGenerator(provider="elevenlabs")
        audio_path = generator.generate_voice(
            text="Xin chao day la thu nghiem giong noi ElevenLabs Adam.",
            voice_id=new_adam_id,
            output_name="test_el_diagnostic"
        )
        print(f"Success! Generated audio path: {audio_path}")
        
    except Exception as e:
        print("\nElevenLabs call failed with error:")
        print(e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
