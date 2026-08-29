# Convergent: Local File Converter Utility
# Owner: Kaiwen Du
# License: Apache License 2.0

# Configuration
PYTHON = python3
SCRIPT = Convergent.py

.PHONY: help setup update start check shortcut quick-action mcp mcp-config clean clean-cache cache-stats cache-prune

update: ## Pull latest updates from Git and refresh dependencies
	@echo "Pulling latest updates..."
	git pull
	@echo "Syncing Python dependencies..."
	$(PYTHON) -m pip install -r requirements.txt
	@echo "Update complete!"

mcp: check ## Start local MCP server over stdio
	$(PYTHON) mcp_server/server.py

mcp-config: ## Print copy-paste JSON config for Claude Desktop / OpenCode / Cursor
	$(PYTHON) mcp_server/config_generator.py

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
		brew install ffmpeg imagemagick pandoc ghostscript typst sevenzip tesseract whisper-cpp; \
		brew install --cask rar || true; \
		brew install --cask libreoffice || true; \
		xattr -d com.apple.quarantine $$(which rar unrar) 2>/dev/null || true; \
	elif command -v apt >/dev/null; then \
		sudo apt update && sudo apt install -y ffmpeg imagemagick pandoc ghostscript typst p7zip-full unrar rar trash-cli libreoffice tesseract-ocr || true; \
	elif command -v dnf >/dev/null; then \
		sudo dnf install -y ffmpeg ImageMagick pandoc ghostscript typst p7zip p7zip-plugins unrar rar trash-cli libreoffice tesseract || true; \
	elif command -v pacman >/dev/null; then \
		sudo pacman -S --noconfirm ffmpeg imagemagick pandoc ghostscript typst p7zip unrar rar trash-cli libreoffice-fresh tesseract || true; \
	else \
		echo "Warning: Supported package manager (brew, apt, dnf, pacman) not found. Please install FFmpeg, ImageMagick, Pandoc, Ghostscript, Typst, 7-Zip, unrar, rar, Tesseract, Whisper.cpp, and LibreOffice manually."; \
	fi
	@echo "Setup complete!"

start: check ## Run converter
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

quick-action: ## Install Finder Quick Action for a saved shortcut (macOS only)
	@if [ "$$(uname)" != "Darwin" ]; then \
		echo "Quick Actions are macOS only."; exit 1; \
	fi
	$(PYTHON) customs/quick_action.py --repo "$(CURDIR)"

clean: ## Clean up __pycache__ directories
	find . -type d -name __pycache__ -exec rm -rf {} +

clean-cache: ## Clear conversion cache (checksum DB)
	@$(PYTHON) -c "from customs.cache import clear_cache; removed=clear_cache(); print(f'Removed cache DBs: {removed}' if removed else 'No cache DB found.')"

cache-stats: ## Show cache entry count and storage stats
	@$(PYTHON) -c "from customs.cache import CacheManager; import json; cm=CacheManager(); print(json.dumps(cm.stats(), indent=2)); cm.close()"

cache-prune: ## Prune expired cache entries and enforce capacity limit
	@$(PYTHON) -c "from customs.cache import CacheManager; cm=CacheManager(); deleted=cm.prune(); print(f'Pruned {deleted} expired/excess cache entries.'); cm.close()"

