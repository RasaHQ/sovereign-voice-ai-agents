# Makefile for Sovereign Voice Banking Assistant
# Full local stack: Faster-Whisper + Rasa + Ministral + NeuTTS

.PHONY: help install train run-actions run run-local-asr demo generate-audio check-system check-ollama check-asr check-rasa test clean

# ==============================================================================
# 🎨 Terminal Colors & UI
# ==============================================================================
GREEN   := $(shell tput -Txterm setaf 2)
YELLOW  := $(shell tput -Txterm setaf 3)
BLUE    := $(shell tput -Txterm setaf 4)
MAGENTA := $(shell tput -Txterm setaf 5)
RED     := $(shell tput -Txterm setaf 1)
RESET   := $(shell tput -Txterm sgr0)

# ==============================================================================
# 🛠️ Path & Environment Configuration
# ==============================================================================
VENV_NAME := .venv
PYTHON    := ./$(VENV_NAME)/bin/python
RASA      := $(PYTHON) -m rasa
UV        := $(shell which uv)

# Ensure .env is loaded for make commands if needed
ifneq (,$(wildcard .env))
    include .env
    export
endif

.DEFAULT_GOAL := help

# ==============================================================================
# 📖 Help & Instructions
# ==============================================================================
help: ## Show this help message
	@echo ''
	@echo '${MAGENTA}🎁 Unwrap the Future: Sovereign Voice Orchestration${RESET}'
	@echo ''
	@echo '${YELLOW}Setup Commands:${RESET}'
	@echo '  ${GREEN}make install${RESET}            - Install all dependencies via uv'
	@echo '  ${GREEN}make install-neutts${RESET}     - Install NeuTTS (requires espeak)'
	@echo '  ${GREEN}make install-local-asr${RESET}  - Install Faster-Whisper for ASR'
	@echo '  ${GREEN}make setup-env${RESET}          - Create .env file from template'
	@echo '  ${GREEN}make train${RESET}              - Train Rasa model'
	@echo ''
	@echo '${YELLOW}System Checks:${RESET}'
	@echo '  ${GREEN}make check-system${RESET}       - Run all health checks'
	@echo '  ${GREEN}make check-ollama${RESET}       - Verify Ollama + Ministral'
	@echo '  ${GREEN}make check-asr${RESET}          - Verify Local ASR server'
	@echo '  ${GREEN}make check-rasa${RESET}         - Verify Rasa server'
	@echo ''
	@echo '${YELLOW}Run Commands (need 3 terminals):${RESET}'
	@echo '  ${GREEN}make run-local-asr${RESET}      - Terminal 1: Start ASR server'
	@echo '  ${GREEN}make run-actions${RESET}        - Terminal 2: Start action server'
	@echo '  ${GREEN}make run${RESET}                - Terminal 3: Start Rasa server'
	@echo ''
	@echo '${YELLOW}Demo Commands:${RESET}'
	@echo '  ${GREEN}make generate-audio${RESET}     - Generate user audio files (GTTS)'
	@echo '  ${GREEN}make demo${RESET}               - Run live demo (all services must be running)'
	@echo ''
	@echo '${YELLOW}Utility Commands:${RESET}'
	@echo '  ${GREEN}make config-local${RESET}       - Switch to Ollama/Ministral config'
	@echo '  ${GREEN}make test${RESET}               - Run tests'
	@echo '  ${GREEN}make clean${RESET}              - Clean generated files'
	@echo ''

# ==============================================================================
# 🚀 Setup & Installation
# ==============================================================================
.PHONY: check-uv
check-uv:
	@if [ -z "$(UV)" ]; then echo "${RED}✗ uv not found. Please install uv: https://github.com/astral-sh/uv${RESET}"; exit 1; fi

.PHONY: install
install: check-uv ## Install all dependencies via uv
	@echo "${BLUE}Creating virtual environment and installing dependencies...${RESET}"
	$(UV) venv $(VENV_NAME)
	$(UV) pip install --upgrade pip setuptools
	$(UV) pip install -e .
	@echo "${GREEN}✓ Base dependencies installed${RESET}"
	@echo "${YELLOW}Next steps:${RESET}"
	@echo "  1. make install-neutts"
	@echo "  2. make install-local-asr"
	@echo "  3. make setup-env"

.PHONY: install-neutts
install-neutts: check-uv ## Install NeuTTS dependencies via uv
	@echo "${BLUE}Installing NeuTTS dependencies...${RESET}"
	@echo "${YELLOW}Checking system dependencies...${RESET}"
	@command -v espeak >/dev/null 2>&1 || command -v espeak-ng >/dev/null 2>&1 || { \
		echo "${RED}✗ espeak/espeak-ng not found. Install: brew install espeak-ng${RESET}"; \
		exit 1; \
	}
	@echo "${GREEN}✓ espeak found${RESET}"
	@echo "${YELLOW}Installing core Python packages...${RESET}"
	$(UV) pip install \
		"librosa==0.11.0" \
		"soundfile>=0.13.1" \
		"gtts>=2.3.0"
	@echo "${YELLOW}Cloning NeuTTS repository...${RESET}"
	@rm -rf /tmp/neutts-install
	@git clone https://github.com/neuphonic/neutts.git /tmp/neutts-install
	@echo "${YELLOW}Installing NeuTTS requirements...${RESET}"
	@$(UV) pip install -r /tmp/neutts-install/requirements.txt
	@echo "${YELLOW}Fixing numpy and pyarrow versions for binary compatibility...${RESET}"
	@$(UV) pip install "numpy<2" "pyarrow<15.0.0"
	@echo "${YELLOW}Installing llama-cpp-python for GGUF support...${RESET}"
	@$(UV) pip install llama-cpp-python
	@echo "${YELLOW}Installing onnxruntime for codec decoder...${RESET}"
	@$(UV) pip install onnxruntime
	@echo "${YELLOW}Copying NeuTTS module to site-packages...${RESET}"
	@bash -c 'SITE_PACKAGES=$$($(PYTHON) -c "import site; print(site.getsitepackages()[0])"); \
		echo "Site packages: $$SITE_PACKAGES"; \
		rm -rf "$$SITE_PACKAGES/neutts"; \
		cp -r /tmp/neutts-install/neutts "$$SITE_PACKAGES/"; \
		echo "${GREEN}✓ NeuTTS module copied${RESET}"'
	@echo "${GREEN}✓ NeuTTS installation complete${RESET}"
	@echo "${YELLOW}Verifying installation...${RESET}"
	@$(PYTHON) -c "from neutts import NeuTTS; print('${GREEN}✓ NeuTTS can be imported successfully${RESET}')" 2>&1 | grep -v "Skipping import" | grep -v "NOTE: Redirects" || true
	@$(PYTHON) -c "from neutts import NeuTTS" 2>/dev/null && echo "${GREEN}✓ Import successful${RESET}" || { \
		echo "${RED}✗ Installation verification failed${RESET}"; \
		exit 1; \
	}
	@echo "${YELLOW}Cleaning up...${RESET}"
	@rm -rf /tmp/neutts-install
	@echo "${GREEN}✓ All done!${RESET}"

.PHONY: install-local-asr
install-local-asr: check-uv ## Install Faster-Whisper dependencies via uv
	@echo "${BLUE}Installing Local ASR dependencies...${RESET}"
	$(UV) pip install -e ".[local-asr]" 2>/dev/null || \
		$(UV) pip install faster-whisper websockets numpy scipy
	@echo "${GREEN}✓ Faster-Whisper installed${RESET}"

.PHONY: setup-env
setup-env: ## Create .env file from template
	@if [ ! -f .env ]; then \
		echo "${YELLOW}Creating .env file...${RESET}"; \
		echo "# Sovereign Voice Assistant Environment" > .env; \
		echo "RASA_LICENSE=your-rasa-pro-license-key-here" >> .env; \
		echo "" >> .env; \
		echo "# Optional for testing/reference" >> .env; \
		echo "# DEEPGRAM_API_KEY=your-key" >> .env; \
		echo "# RIME_API_KEY=your-key" >> .env; \
		echo "${GREEN}✓ .env created${RESET}"; \
		echo "${YELLOW}Edit .env and add your RASA_LICENSE${RESET}"; \
	else \
		echo "${GREEN}.env already exists${RESET}"; \
	fi

# ==============================================================================
# 🔍 System Health Checks
# ==============================================================================
.PHONY: check-system
check-system: check-ollama check-asr check-rasa ## Run all health checks
	@echo ""
	@echo "${GREEN}════════════════════════════════════════════════${RESET}"
	@echo "${GREEN}✓ All systems operational!${RESET}"
	@echo "${GREEN}════════════════════════════════════════════════${RESET}"

.PHONY: check-ollama
check-ollama: ## Verify Ollama + Ministral
	@echo "${YELLOW}Checking Ollama + Ministral...${RESET}"
	@curl -s http://localhost:11434/api/tags >/dev/null 2>&1 || { \
		echo "${RED}✗ Ollama not running${RESET}"; \
		echo "${YELLOW}  Start: ollama serve${RESET}"; \
		exit 1; \
	}
	@echo "${GREEN}✓ Ollama is running${RESET}"
	@curl -s http://localhost:11434/api/tags | grep -q "ministral" || { \
		echo "${RED}✗ Ministral model not found${RESET}"; \
		echo "${YELLOW}  Pull model: ollama pull ministral-3:14b${RESET}"; \
		exit 1; \
	}
	@echo "${GREEN}✓ Ministral model available${RESET}"

.PHONY: check-asr
check-asr: ## Verify Local ASR server
	@echo "${YELLOW}Checking Local ASR server...${RESET}"
	@$(PYTHON) scripts/check_asr.py 2>/dev/null || { \
		echo "${RED}✗ Local ASR server not running${RESET}"; \
		echo "${YELLOW}  Start: make run-local-asr${RESET}"; \
		exit 1; \
	}
	@echo "${GREEN}✓ Local ASR server running${RESET}"

.PHONY: check-rasa
check-rasa: ## Verify Rasa server
	@echo "${YELLOW}Checking Rasa server...${RESET}"
	@curl -s http://localhost:5005/ >/dev/null 2>&1 || { \
		echo "${RED}✗ Rasa server not running${RESET}"; \
		echo "${YELLOW}  Start: make run${RESET}"; \
		exit 1; \
	}
	@echo "${GREEN}✓ Rasa server running${RESET}"

# ==============================================================================
# ⚙️ Configuration
# ==============================================================================
.PHONY: config-local
config-local: ## Switch to Ollama/Ministral config
	@echo "${BLUE}Configuring for local Ollama/Ministral...${RESET}"
	@cp config.yml config.yml.bak 2>/dev/null || true
	@sed -i.tmp 's/model_group: .*/model_group: ollama_llm/' config.yml
	@rm -f config.yml.tmp
	@echo "${GREEN}✓ Switched to ollama_llm${RESET}"
	@echo "${YELLOW}Verify with: make check-ollama${RESET}"

# ==============================================================================
# 🎓 Training
# ==============================================================================
.PHONY: train
train: ## Train the Rasa model
	@echo "${BLUE}Training Rasa model...${RESET}"
	@$(RASA) train
	@echo "${GREEN}✓ Training complete${RESET}"

# ==============================================================================
# 🎤 Run Services (3 terminals needed)
# ==============================================================================
.PHONY: run-local-asr
run-local-asr: ## Terminal 1: Start Local ASR Server (Faster-Whisper)
	@echo "${MAGENTA}Starting Local ASR Server (Faster-Whisper)...${RESET}"
	@echo "${YELLOW}This will listen on ws://localhost:9001${RESET}"
	@echo "${YELLOW}Keep this terminal running${RESET}"
	@echo ""
	$(PYTHON) services/local_asr_server.py

.PHONY: run-actions
run-actions: ## Terminal 2: Start Action Server
	@echo "${MAGENTA}Starting Action Server...${RESET}"
	@echo "${YELLOW}This will listen on http://localhost:5055${RESET}"
	@echo "${YELLOW}Keep this terminal running${RESET}"
	@echo ""
	$(RASA) run actions

.PHONY: run
run: ## Terminal 3: Start Rasa Server
	@echo "${MAGENTA}Starting Rasa Server...${RESET}"
	@echo "${YELLOW}This will listen on http://localhost:5005${RESET}"
	@echo "${YELLOW}Keep this terminal running${RESET}"
	@echo ""
	$(RASA) run --enable-api --cors "*"

# ==============================================================================
# 🎬 Demo
# ==============================================================================
.PHONY: generate-audio
generate-audio: ## Generate user audio files (GTTS)
	@echo "${BLUE}Generating user audio files (GTTS)...${RESET}"
	$(PYTHON) generate_user_audio.py
	@echo "${GREEN}✓ Audio files ready${RESET}"

.PHONY: demo
demo: ## Run live demo (all services must be running)
	@echo "${MAGENTA}Starting Sovereign Voice Demo...${RESET}"
	@echo "${YELLOW}Make sure all services are running:${RESET}"
	@echo "  1. Terminal 1: make run-local-asr"
	@echo "  2. Terminal 2: make run-actions"
	@echo "  3. Terminal 3: make run"
	@echo ""
	@echo "${YELLOW}Checking services...${RESET}"
	@$(MAKE) check-system || { echo "${RED}Services not ready. Start them first.${RESET}"; exit 1; }
	@echo ""
	@echo "${GREEN}All systems ready! Starting demo...${RESET}"
	@echo ""
	$(PYTHON) demo_live.py

# ==============================================================================
# 🧪 Testing
# ==============================================================================
.PHONY: test
test: ## Run tests
	@echo "${BLUE}Running tests...${RESET}"
	$(PYTHON) -m pytest tests/ -v

# ==============================================================================
# 🧹 Cleanup
# ==============================================================================
.PHONY: clean
clean: ## Clean generated files
	@echo "${YELLOW}Cleaning generated files...${RESET}"
	rm -rf tests/audio/*.wav
	rm -rf tests/audio_responses_real/
	rm -rf models/
	rm -rf .rasa/
	rm -rf __pycache__/
	rm -rf actions/__pycache__/
	rm -rf services/__pycache__/
	@echo "${GREEN}✓ Cleanup complete${RESET}"

# ==============================================================================
# 🛠️ Development Helpers
# ==============================================================================
.PHONY: inspect
inspect: ## Start Rasa shell for interactive testing
	@echo "${BLUE}Starting Rasa shell for interactive testing...${RESET}"
	$(RASA) shell

.PHONY: inspect-debug
inspect-debug: ## Start Rasa shell with debug logging
	@echo "${BLUE}Starting Rasa shell with debug logging...${RESET}"
	$(RASA) shell --debug