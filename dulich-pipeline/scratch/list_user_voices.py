import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def main():
    user_key = "sk_8788e0366c9418cd18bbdd13d77c2e5933ea7a8e8abfdeb3"
    from elevenlabs.client import ElevenLabs
    client = ElevenLabs(api_key=user_key)
    
    try:
        voices = client.voices.get_all()
        print(f"Total voices available: {len(voices.voices)}")
        print("\nList of voices:")
        for idx, voice in enumerate(voices.voices):
            print(f"{idx+1}. Name: {voice.name} | ID: {voice.voice_id} | Category: {voice.category}")
    except Exception as e:
        print(f"Error fetching voices: {e}")

if __name__ == "__main__":
    main()
