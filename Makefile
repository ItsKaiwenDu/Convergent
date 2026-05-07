# Convergent: Local File Converter Utility
# Owner: Kaiwen Du
# License: Free to use

# Configuration
PYTHON = python3
SCRIPT = Convergent.py

.PHONY: help setup start check shortcut

help:
	@echo "Convergent Makefile Commands:"
	@echo "  make setup     - Install necessary Python and System dependencies"
	@echo "  make check     - Probe system dependencies to ensure everything is installed"
	@echo "  make start     - Run the converter (Interactive or with flags)"
	@echo "  make shortcut  - Create a clickable Desktop shortcut to run Convergent"
	@echo ""
	@echo "Usage with flags:"
	@echo "  make start ARGS=\"--from JPG --to PNG --path ./images\""

setup:
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

start:
	$(PYTHON) $(SCRIPT) $(ARGS)

check:
	@$(PYTHON) customs/check_deps.py

shortcut:
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
