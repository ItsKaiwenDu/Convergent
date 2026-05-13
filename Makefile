# Convergent: Local File Converter Utility
# Owner: Kaiwen Du
# License: Free to use

# Configuration
PYTHON = python3
SCRIPT = Convergent.py

.PHONY: help setup start check shortcut

help: ## Show this help message
	@echo "\033[1mUsage:\033[0m make [target]"
	@echo ""
	@echo "\033[1mTargets:\033[0m"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "\033[1mExample:\033[0m"
	@echo "  make start ARGS=\"--from JPG --to PNG\""

setup: ## Install dependencies
	@echo "Checking Python dependencies..."
	$(PYTHON) -m pip install -r requirements.txt
	@echo "Checking System dependencies..."
	@if command -v brew >/dev/null; then \
		brew install ffmpeg imagemagick pandoc ghostscript; \
	elif command -v apt >/dev/null; then \
		sudo apt update && sudo apt install -y ffmpeg imagemagick pandoc ghostscript; \
	elif command -v dnf >/dev/null; then \
		sudo dnf install -y ffmpeg ImageMagick pandoc ghostscript; \
	elif command -v pacman >/dev/null; then \
		sudo pacman -S --noconfirm ffmpeg imagemagick pandoc ghostscript; \
	else \
		echo "Warning: Supported package manager (brew, apt, dnf, pacman) not found. Please install FFmpeg, ImageMagick, Pandoc, and Ghostscript manually."; \
	fi
	@echo "Setup complete!"

start: ## Run converter
	$(PYTHON) $(SCRIPT) $(ARGS)

check: ## Verify dependencies
	@$(PYTHON) customs/check_deps.py

shortcut: ## Create desktop shortcut
	@printf "Path (default: ~/Desktop): "; \
	read DEST_DIR; \
	DEST_DIR=$${DEST_DIR:-$(HOME)/Desktop}; \
	printf "Name (default: Convergent): "; \
	read SHORTCUT_NAME; \
	SHORTCUT_NAME=$${SHORTCUT_NAME:-Convergent}; \
	DEST_PATH="$$DEST_DIR/$$SHORTCUT_NAME.command"; \
	echo "#!/bin/bash\ncd \"$(CURDIR)\"\nmake start" > "$$DEST_PATH"; \
	chmod +x "$$DEST_PATH"; \
	echo "Done! Created $$DEST_PATH"
