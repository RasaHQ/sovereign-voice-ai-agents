#!/usr/bin/env python3
"""
Sovereign Voice Assistant - Setup Verification
Checks all dependencies and services before running the demo.
"""

import sys
import os
import subprocess
import importlib.util
from pathlib import Path
from typing import Tuple, List

# ANSI colors
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

def print_header(text: str):
    print(f"\n{Colors.BLUE}{Colors.BOLD}{'='*70}{Colors.RESET}")
    print(f"{Colors.BLUE}{Colors.BOLD}{text:^70}{Colors.RESET}")
    print(f"{Colors.BLUE}{Colors.BOLD}{'='*70}{Colors.RESET}\n")

def print_success(text: str):
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")

def print_error(text: str):
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")

def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")

def print_info(text: str):
    print(f"{Colors.BLUE}ℹ {text}{Colors.RESET}")

def check_command(cmd: str) -> Tuple[bool, str]:
    """Check if a command is available."""
    try:
        result = subprocess.run(
            ['which', cmd], 
            capture_output=True, 
            text=True, 
            timeout=5
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, ""
    except:
        return False, ""

def check_python_module(module: str) -> bool:
    """Check if a Python module is installed."""
    return importlib.util.find_spec(module) is not None

def check_ollama() -> Tuple[bool, List[str]]:
    """Check if Ollama is running and list models."""
    try:
        import requests
        response = requests.get('http://localhost:11434/api/tags', timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = [m['name'] for m in data.get('models', [])]
            return True, models
        return False, []
    except:
        return False, []

def check_port(port: int) -> bool:
    """Check if a port is in use."""
    try:
        result = subprocess.run(
            ['lsof', '-i', f':{port}'],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except:
        return False

def main():
    print_header("Sovereign Voice Assistant - Setup Verification")
    
    all_checks_passed = True
    warnings = []
    
    # ========================================================================
    # System Dependencies
    # ========================================================================
    print_info("Checking system dependencies...")
    print()
    
    # Python version
    py_version = sys.version_info
    if py_version.major == 3 and py_version.minor in [10, 11]:
        print_success(f"Python {py_version.major}.{py_version.minor}.{py_version.micro}")
    else:
        print_error(f"Python {py_version.major}.{py_version.minor} (requires 3.10 or 3.11)")
        all_checks_passed = False
    
    # espeak (required for NeuTTS)
    has_espeak, espeak_path = check_command('espeak')
    if has_espeak:
        print_success(f"espeak: {espeak_path}")
    else:
        print_error("espeak not found (required for NeuTTS)")
        print(f"  {Colors.YELLOW}Install: brew install espeak (macOS) or apt-get install espeak (Linux){Colors.RESET}")
        all_checks_passed = False
    
    # ffmpeg (required for audio processing)
    has_ffmpeg, ffmpeg_path = check_command('ffmpeg')
    if has_ffmpeg:
        print_success(f"ffmpeg: {ffmpeg_path}")
    else:
        print_error("ffmpeg not found (required for audio)")
        print(f"  {Colors.YELLOW}Install: brew install ffmpeg (macOS) or apt-get install ffmpeg (Linux){Colors.RESET}")
        all_checks_passed = False
    
    # ollama
    has_ollama, ollama_path = check_command('ollama')
    if has_ollama:
        print_success(f"ollama: {ollama_path}")
    else:
        print_error("ollama not found (required for LLM)")
        print(f"  {Colors.YELLOW}Install: https://ollama.ai/download{Colors.RESET}")
        all_checks_passed = False
    
    # ========================================================================
    # Python Dependencies
    # ========================================================================
    print()
    print_info("Checking Python dependencies...")
    print()
    
    required_modules = [
        ('rasa', 'Rasa Pro'),
        ('rasa_sdk', 'Rasa SDK'),
        ('aiohttp', 'Async HTTP'),
        ('websockets', 'WebSocket support'),
        ('pydub', 'Audio processing'),
        ('rich', 'Terminal UI'),
        ('dotenv', 'Environment config'),
    ]
    
    for module, name in required_modules:
        if check_python_module(module):
            print_success(f"{name} ({module})")
        else:
            print_error(f"{name} ({module}) not found")
            print(f"  {Colors.YELLOW}Install: make install{Colors.RESET}")
            all_checks_passed = False
    
    # NeuTTS dependencies
    neutts_modules = [
        ('neuttsair', 'NeuTTS Air'),
        ('phonemizer', 'Phonemizer'),
        ('librosa', 'Librosa'),
        ('torch', 'PyTorch'),
    ]
    
    has_neutts = True
    for module, name in neutts_modules:
        if check_python_module(module):
            print_success(f"{name} ({module})")
        else:
            print_error(f"{name} ({module}) not found")
            has_neutts = False
    
    if not has_neutts:
        print(f"  {Colors.YELLOW}Install: make install-neutts{Colors.RESET}")
        all_checks_passed = False
    
    # Faster-Whisper
    if check_python_module('faster_whisper'):
        print_success("Faster-Whisper")
    else:
        print_error("Faster-Whisper not found")
        print(f"  {Colors.YELLOW}Install: make install-local-asr{Colors.RESET}")
        all_checks_passed = False
    
    # ========================================================================
    # Configuration Files
    # ========================================================================
    print()
    print_info("Checking configuration files...")
    print()
    
    config_files = [
        'config.yml',
        'credentials.yml',
        'domain.yml',
        'endpoints.yml',
        'data/flows.yml',
    ]
    
    for config_file in config_files:
        if Path(config_file).exists():
            print_success(config_file)
        else:
            print_error(f"{config_file} not found")
            all_checks_passed = False
    
    # .env file
    if Path('.env').exists():
        print_success(".env file exists")
        # Check for license
        with open('.env', 'r') as f:
            content = f.read()
            if 'RASA_LICENSE=' in content and 'your-rasa-pro-license' not in content:
                print_success("RASA_LICENSE configured")
            else:
                print_warning("RASA_LICENSE not configured in .env")
                warnings.append("Add your Rasa Pro license to .env")
    else:
        print_error(".env file not found")
        print(f"  {Colors.YELLOW}Create: make setup-env{Colors.RESET}")
        all_checks_passed = False
    
    # ========================================================================
    # Service Modules
    # ========================================================================
    print()
    print_info("Checking service modules...")
    print()
    
    service_files = [
        'services/neutts_service.py',
        'services/local_asr_server.py',
        'services/local_asr_client.py',
    ]
    
    for service_file in service_files:
        if Path(service_file).exists():
            print_success(service_file)
        else:
            print_error(f"{service_file} not found")
            all_checks_passed = False
    
    # ========================================================================
    # Running Services
    # ========================================================================
    print()
    print_info("Checking running services...")
    print()
    
    # Ollama service
    is_ollama_running, models = check_ollama()
    if is_ollama_running:
        print_success("Ollama is running")
        
        # Check for Ministral
        has_ministral = any('ministral' in m.lower() for m in models)
        if has_ministral:
            ministral_models = [m for m in models if 'ministral' in m.lower()]
            print_success(f"Ministral available: {', '.join(ministral_models)}")
        else:
            print_warning("Ministral model not found")
            print(f"  {Colors.YELLOW}Pull model: ollama pull ministral-3:14b{Colors.RESET}")
            warnings.append("Pull Ministral model before running demo")
        
        if models:
            print(f"  {Colors.BLUE}Available models:{Colors.RESET}")
            for model in models[:5]:  # Show first 5
                print(f"    - {model}")
            if len(models) > 5:
                print(f"    ... and {len(models) - 5} more")
    else:
        print_warning("Ollama not running")
        print(f"  {Colors.YELLOW}Start: ollama serve{Colors.RESET}")
        warnings.append("Start Ollama before running demo")
    
    # Local ASR
    if check_port(9001):
        print_success("Local ASR server is running (port 9001)")
    else:
        print_warning("Local ASR server not running")
        print(f"  {Colors.YELLOW}Start: make run-local-asr (in separate terminal){Colors.RESET}")
        warnings.append("Start Local ASR server before running demo")
    
    # Rasa
    if check_port(5005):
        print_success("Rasa server is running (port 5005)")
    else:
        print_warning("Rasa server not running")
        print(f"  {Colors.YELLOW}Start: make run (in separate terminal){Colors.RESET}")
        warnings.append("Start Rasa server before running demo")
    
    # Action server
    if check_port(5055):
        print_success("Action server is running (port 5055)")
    else:
        print_warning("Action server not running")
        print(f"  {Colors.YELLOW}Start: make run-actions (in separate terminal){Colors.RESET}")
        warnings.append("Start Action server before running demo")
    
    # ========================================================================
    # Test Audio
    # ========================================================================
    print()
    print_info("Checking test audio...")
    print()
    
    audio_dir = Path('tests/audio')
    if audio_dir.exists():
        audio_files = list(audio_dir.glob('*.wav'))
        if audio_files:
            print_success(f"Test audio directory: {len(audio_files)} files")
        else:
            print_warning("No audio files found")
            print(f"  {Colors.YELLOW}Generate: make generate-audio{Colors.RESET}")
            warnings.append("Generate audio files before running demo")
    else:
        print_warning("Test audio directory not found")
        print(f"  {Colors.YELLOW}Generate: make generate-audio{Colors.RESET}")
        warnings.append("Generate audio files before running demo")
    
    # ========================================================================
    # Summary
    # ========================================================================
    print_header("Verification Summary")
    
    if all_checks_passed and not warnings:
        print(f"{Colors.GREEN}{Colors.BOLD}✓ ALL CHECKS PASSED!{Colors.RESET}")
        print()
        print("Your system is fully configured and ready.")
        print()
        print("To run the demo:")
        print(f"  {Colors.GREEN}1. Terminal 1: make run-local-asr{Colors.RESET}")
        print(f"  {Colors.GREEN}2. Terminal 2: make run-actions{Colors.RESET}")
        print(f"  {Colors.GREEN}3. Terminal 3: make run{Colors.RESET}")
        print(f"  {Colors.GREEN}4. Terminal 4: make demo{Colors.RESET}")
        print()
        return 0
    
    elif warnings and all_checks_passed:
        print(f"{Colors.YELLOW}{Colors.BOLD}⚠ SETUP COMPLETE WITH WARNINGS{Colors.RESET}")
        print()
        print("Base installation is complete, but some services need to be started:")
        print()
        for i, warning in enumerate(warnings, 1):
            print(f"  {i}. {warning}")
        print()
        print("Quick start:")
        print(f"  {Colors.YELLOW}make check-system{Colors.RESET}  - Check all services")
        print()
        return 0
    
    else:
        print(f"{Colors.RED}{Colors.BOLD}✗ SETUP INCOMPLETE{Colors.RESET}")
        print()
        print("Please fix the errors above before running the demo.")
        print()
        print("Common fixes:")
        print(f"  {Colors.YELLOW}make install{Colors.RESET}           - Install base dependencies")
        print(f"  {Colors.YELLOW}make install-neutts{Colors.RESET}    - Install NeuTTS")
        print(f"  {Colors.YELLOW}make install-local-asr{Colors.RESET} - Install Faster-Whisper")
        print(f"  {Colors.YELLOW}make setup-env{Colors.RESET}         - Create .env file")
        print()
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Interrupted by user{Colors.RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
