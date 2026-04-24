# Convergent: Local File Converter Utility
# Owner: Kaiwen Du
# License: Free to use

# Configuration
PYTHON = python3
SCRIPT = Convergent.py

.PHONY: help setup start

help:
	@echo "Convergent Makefile Commands:"
	@echo "  make setup     - Install necessary Python and System dependencies"
	@echo "  make start     - Run the converter (Interactive or with flags)"
	@echo ""
	@echo "Usage with flags:"
	@echo "  make start ARGS=\"--from JPG --to PNG --path ./images\""

setup:
	@echo "Checking Python dependencies..."
	$(PYTHON) -m pip install rich
	@echo "Checking System dependencies (Homebrew required)..."
	@if command -v brew >/dev/null; then \
		brew install ffmpeg imagemagick pandoc; \
	else \
		echo "Warning: Homebrew not found. Please install FFmpeg, ImageMagick, and Pandoc manually."; \
	fi
	@echo "Setup complete!"

start:
	$(PYTHON) $(SCRIPT) $(ARGS)
