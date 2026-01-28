#!/usr/bin/env python3
"""
Sovereign Voice Orchestration Demo - Live Pipeline
Uses: Local ASR (Faster-Whisper) -> Rasa (Ministral) -> Local TTS (NeuTTS)

This demo simulates a complete voice banking conversation using:
- Pre-generated user audio (GTTS for distinct voice)
- Local Faster-Whisper ASR (WebSocket server)
- Rasa with Ministral LLM (Ollama)
- Local NeuTTS TTS (neural voice synthesis)
"""

import asyncio
import os
import io
import time
import sys
import traceback
import json
import websockets
import audioop
import wave
from pathlib import Path
from dotenv import load_dotenv
import aiohttp
from pydub import AudioSegment
from pydub.playback import play

# Rich UI Imports
from rich.console import Console, Group
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.align import Align
from rich import box

# Load env variables
load_dotenv()
console = Console()

# Configuration
RASA_URL = "http://localhost:5005/webhooks/rest/webhook"
LOCAL_ASR_URL = "ws://localhost:9001"
OLLAMA_URL = "http://localhost:11434"
AUDIO_DIR = Path("tests/audio")

# Import local TTS service
sys.path.insert(0, str(Path(__file__).parent))
try:
    from services.neutts_service import NeuTTSService, NeuTTSConfig
except ImportError:
    console.print("[red]❌ Could not import NeuTTSService. Run 'make install-neutts'[/red]")
    sys.exit(1)

# The Story Script - 5-step Money Transfer Conversation
CONVERSATION_STEPS = [
    {"file": "user_input_1.wav", "label": "Transfer Request"},
    {"file": "user_input_2.wav", "label": "Account Selection"},
    {"file": "user_input_3.wav", "label": "Account Destination"},
    {"file": "user_input_4.wav", "label": "Amount"},
    {"file": "user_input_5.wav", "label": "Confirmation"},
]

def make_layout():
    """Define the 3-section layout: Header, Chat History, Status Footer."""
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="status", size=3),
    )
    return layout

async def check_ollama_connection() -> bool:
    """Verify Ollama is running and ministral model is available."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{OLLAMA_URL}/api/tags", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    models = [m['name'] for m in data.get('models', [])]
                    # Check for ministral variants
                    has_ministral = any('ministral' in m.lower() for m in models)
                    return has_ministral
    except Exception:
        return False
    return False

async def check_asr_connection() -> bool:
    """Verify Local ASR server is running."""
    try:
        async with websockets.connect(LOCAL_ASR_URL, open_timeout=2) as ws:
            await ws.close()
            return True
    except Exception:
        return False

async def check_rasa_connection() -> bool:
    """Verify Rasa server is running."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{RASA_URL.replace('/webhooks/rest/webhook', '')}/", 
                                   timeout=aiohttp.ClientTimeout(total=5)) as resp:
                return resp.status == 200
    except Exception:
        return False

async def play_audio_data(audio_bytes: bytes):
    """Play raw audio bytes."""
    try:
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format="wav")
        play(audio)
    except Exception as e:
        console.print(f"[red]Audio Error: {e}[/red]")

async def local_asr_transcribe(audio_path: Path) -> str:
    """
    Send audio to Local ASR server (Faster-Whisper).
    Converts to 8kHz mulaw format that server expects.
    """
    try:
        async with websockets.connect(LOCAL_ASR_URL, open_timeout=5) as ws:
            # Read WAV file
            with wave.open(str(audio_path), 'rb') as w:
                frames = w.readframes(w.getnframes())
                width = w.getsampwidth()
                rate = w.getframerate()
                n_channels = w.getnchannels()
                
                # Convert to mono
                if n_channels == 2:
                    frames = audioop.tomono(frames, width, 0.5, 0.5)
                
                # Resample to 8kHz
                if rate != 8000:
                    frames, _ = audioop.ratecv(frames, width, 1, rate, 8000, None)
                
                # Encode to u-law
                mulaw_bytes = audioop.lin2ulaw(frames, width)
            
            # Send audio bytes
            await ws.send(mulaw_bytes)
            
            # Trigger transcription
            await ws.send(json.dumps({"action": "transcribe"}))
            
            # Wait for response
            response = await ws.recv()
            data = json.loads(response)
            return data.get("text", "").strip()
            
    except Exception as e:
        console.print(f"[red]ASR Error: {e}[/red]")
        return ""

async def neutts_synthesize(text: str, tts_service: NeuTTSService) -> bytes:
    """
    Generate speech using NeuTTS.
    Returns PCM audio data (8kHz, 16-bit).
    """
    try:
        ulaw_data = bytearray()
        async for chunk in tts_service.synthesize(text):
            ulaw_data.extend(chunk)
        
        if not ulaw_data:
            return b""
        
        # Convert mulaw back to PCM for playback
        pcm_data = audioop.ulaw2lin(bytes(ulaw_data), 2)
        return pcm_data
        
    except Exception as e:
        console.print(f"[red]TTS Error: {e}[/red]")
        traceback.print_exc()
        return b""

async def run_demo():
    layout = make_layout()
    
    # Header Styling
    header_text = Text("🎁 Unwrap the Future: Sovereign Voice Orchestration", 
                       style="bold white on magenta", justify="center")
    layout["header"].update(Panel(header_text, style="magenta"))
    
    # Store full history
    full_history = []
    
    # Config: How many chat bubbles to show at once
    MAX_VISIBLE_BUBBLES = 6

    def update_chat_view():
        """Helper to render only the latest messages."""
        visible_history = full_history[-MAX_VISIBLE_BUBBLES:]
        layout["main"].update(
            Panel(
                Group(*visible_history), 
                title="Conversation Log", 
                border_style="white",
                padding=(1, 1)
            )
        )

    with Live(layout, refresh_per_second=10, screen=True) as live:
        
        # Pre-flight checks
        layout["status"].update(Panel(
            Text("🔍 Running pre-flight checks...", style="bold yellow"), 
            title="Status", border_style="yellow"
        ))
        
        # Check Ollama
        console.print("\n[yellow]Checking Ollama + Ministral...[/yellow]")
        if not await check_ollama_connection():
            layout["status"].update(Panel(
                Text("❌ Ollama/Ministral not available\nRun: ollama serve && ollama pull ministral-3:14b", 
                     style="bold red"), 
                title="Status", border_style="red"
            ))
            await asyncio.sleep(5)
            return
        console.print("[green]✓ Ollama + Ministral ready[/green]")
        
        # Check ASR
        console.print("[yellow]Checking Local ASR server...[/yellow]")
        if not await check_asr_connection():
            layout["status"].update(Panel(
                Text("❌ Local ASR server not running\nRun: make run-local-asr", 
                     style="bold red"), 
                title="Status", border_style="red"
            ))
            await asyncio.sleep(5)
            return
        console.print("[green]✓ Local ASR server ready[/green]")
        
        # Check Rasa
        console.print("[yellow]Checking Rasa server...[/yellow]")
        if not await check_rasa_connection():
            layout["status"].update(Panel(
                Text("❌ Rasa server not running\nRun: make run", 
                     style="bold red"), 
                title="Status", border_style="red"
            ))
            await asyncio.sleep(5)
            return
        console.print("[green]✓ Rasa server ready[/green]")
        
        # Initialize TTS
        console.print("[yellow]Initializing NeuTTS...[/yellow]")
        layout["status"].update(Panel(
            Text("⚙️ Loading NeuTTS model...", style="bold yellow"), 
            title="Status", border_style="yellow"
        ))
        
        try:
            tts_config = NeuTTSConfig(
                backbone_repo="neuphonic/neutts-air-q8-gguf",
                codec_repo="neuphonic/neucodec",
                device="cpu",
                auto_generate_reference=True
            )
            tts_service = NeuTTSService(tts_config)
            console.print("[green]✓ NeuTTS ready[/green]\n")
        except Exception as e:
            console.print(f"[red]❌ NeuTTS initialization failed: {e}[/red]")
            traceback.print_exc()
            layout["status"].update(Panel(
                Text(f"❌ TTS failed: {e}", style="bold red"), 
                title="Status", border_style="red"
            ))
            await asyncio.sleep(5)
            return
        
        # Check audio files
        if not AUDIO_DIR.exists():
            layout["status"].update(Panel(
                Text("❌ Test audio not found\nRun: make generate-audio", 
                     style="bold red"), 
                title="Status", border_style="red"
            ))
            await asyncio.sleep(5)
            return
        
        # Main conversation loop
        layout["status"].update(Panel(
            Text("✨ All systems ready - Starting conversation...", style="bold green"), 
            title="Status", border_style="green"
        ))
        await asyncio.sleep(1)
        
        for step in CONVERSATION_STEPS:
            audio_path = AUDIO_DIR / step['file']
            
            if not audio_path.exists():
                console.print(f"[red]Missing: {audio_path}[/red]")
                continue
            
            # --- STATE: USER SPEAKING ---
            status_text = f"🔊 User is speaking... [{step['label']}]"
            layout["status"].update(Panel(
                Text(status_text, style="bold cyan"), 
                title="Status", border_style="cyan"
            ))
            
            # Play user audio
            play(AudioSegment.from_wav(str(audio_path)))
            
            # --- STATE: TRANSCRIBING ---
            layout["status"].update(Panel(
                Text("⚡ Local ASR Transcribing (Faster-Whisper)...", style="bold yellow"), 
                title="Status", border_style="yellow"
            ))
            transcript = await local_asr_transcribe(audio_path)
            
            if not transcript:
                console.print(f"[red]No transcript for {audio_path}[/red]")
                continue
            
            # Add User Message
            user_panel = Align.left(
                Panel(
                    Text(transcript, style="bright_white"),
                    title="User",
                    style="cyan",
                    box=box.ROUNDED,
                    padding=(1, 2),
                    width=60
                )
            )
            full_history.append(user_panel)
            update_chat_view()
            
            # --- STATE: RASA THINKING ---
            layout["status"].update(Panel(
                Text("🧠 Rasa Thinking (Ministral via Ollama)...", style="bold green"), 
                title="Status", border_style="green"
            ))
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        RASA_URL, 
                        json={"sender": "demo-user", "message": transcript},
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as resp:
                        if resp.status != 200:
                            console.print(f"[red]Rasa error: {resp.status}[/red]")
                            continue
                        bot_responses = await resp.json()
            except Exception as e:
                console.print(f"[red]Rasa request failed: {e}[/red]")
                continue
            
            # --- STATE: AGENT SPEAKING ---
            for response in bot_responses:
                if 'text' in response:
                    agent_text = response['text']
                    
                    # Add Agent Message
                    agent_panel = Align.right(
                        Panel(
                            Text(agent_text, style="bright_white"),
                            title="Agent (NeuTTS)",
                            style="green",
                            box=box.ROUNDED,
                            padding=(1, 2),
                            width=60
                        )
                    )
                    full_history.append(agent_panel)
                    update_chat_view()
                    
                    layout["status"].update(Panel(
                        Text("🗣️ NeuTTS Generating & Speaking...", style="bold magenta"), 
                        title="Status", border_style="magenta"
                    ))
                    
                    # Generate and Play
                    pcm_audio = await neutts_synthesize(agent_text, tts_service)
                    if pcm_audio:
                        # Convert PCM to playable format
                        audio_segment = AudioSegment(
                            data=pcm_audio,
                            sample_width=2,
                            frame_rate=8000,
                            channels=1
                        )
                        play(audio_segment)

            time.sleep(0.5)

        layout["status"].update(Panel(
            Text("✨ Demo Complete - 100% Sovereign Stack!", style="bold white on green"), 
            title="Status", border_style="green"
        ))
        await asyncio.sleep(10)

if __name__ == "__main__":
    try:
        asyncio.run(run_demo())
    except KeyboardInterrupt:
        console.print("\n[yellow]Demo interrupted by user[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]Fatal error: {e}[/red]")
        traceback.print_exc()
        sys.exit(1)
