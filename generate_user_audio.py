#!/usr/bin/env python3
"""
Generate User Audio for Sovereign Voice Demo
Uses GTTS to create distinct user voice (different from NeuTTS agent)
"""

import asyncio
from pathlib import Path
from gtts import gTTS
from pydub import AudioSegment
import sys

# Configuration
OUTPUT_DIR = Path("tests/audio")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 5-step Money Transfer Conversation
TRANSCRIPTS = {
    "user_input_1.wav": "I want to transfer money.",
    "user_input_2.wav": "Checking.",
    "user_input_3.wav": "Savings.",
    "user_input_4.wav": "Five hundred dollars.",
    "user_input_5.wav": "Yes, please."
}

def generate_audio(filename: str, text: str):
    """Generate audio using GTTS with consistent voice settings."""
    try:
        output_path = OUTPUT_DIR / filename
        temp_mp3 = OUTPUT_DIR / f"temp_{filename}.mp3"
        
        print(f"Generating: {filename}")
        print(f"  Text: \"{text}\"")
        
        # Generate MP3 with GTTS
        # Using en-us for American accent, slow=False for natural speed
        tts = gTTS(text=text, lang='en', slow=False, tld='us')
        tts.save(str(temp_mp3))
        
        # Convert to WAV (16kHz, mono for compatibility)
        audio = AudioSegment.from_mp3(str(temp_mp3))
        audio = audio.set_channels(1)  # Mono
        audio = audio.set_frame_rate(16000)  # 16kHz (standard for ASR)
        audio.export(str(output_path), format="wav")
        
        # Cleanup temp file
        temp_mp3.unlink()
        
        print(f"  ✓ Saved: {output_path}")
        print()
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        sys.exit(1)

def main():
    print("=" * 70)
    print("Generating User Audio Files (GTTS)")
    print("=" * 70)
    print()
    
    # Check dependencies
    try:
        import gtts
        from pydub import AudioSegment
    except ImportError as e:
        print(f"✗ Missing dependencies: {e}")
        print("\nInstall with:")
        print("  pip install gtts pydub")
        print("\nAlso requires ffmpeg:")
        print("  macOS: brew install ffmpeg")
        print("  Linux: apt-get install ffmpeg")
        sys.exit(1)
    
    print(f"Output directory: {OUTPUT_DIR.absolute()}")
    print(f"Files to generate: {len(TRANSCRIPTS)}")
    print()
    
    # Generate all audio files
    for filename, text in TRANSCRIPTS.items():
        generate_audio(filename, text)
    
    print("=" * 70)
    print("✓ All audio files generated successfully!")
    print("=" * 70)
    print()
    print("Next steps:")
    print("  1. Ensure Local ASR is running: make run-local-asr")
    print("  2. Ensure Rasa is running: make run")
    print("  3. Run demo: make demo")
    print()

if __name__ == "__main__":
    main()
