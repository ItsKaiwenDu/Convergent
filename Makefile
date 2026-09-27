# Convergent: Local File Converter Utility
# Owner: Kaiwen Du
# License: Apache License 2.0

# Configuration
PYTHON = python3
SCRIPT = Convergent.py

.PHONY: help setup setup-mcp update start check test shortcut quick-action mcp mcp-config clean cache-clear cache-stats

test: ## Run automated unit test suite
	$(PYTHON) -m unittest discover -s tests -v

update: ## Pull latest updates from Git and refresh dependencies
	@echo "Pulling latest updates..."
	git pull
	@echo "Syncing Python dependencies..."
	$(PYTHON) -m pip install -r requirements.txt
	@echo "Update complete!"

mcp: ## Start local MCP server over stdio
	@$(PYTHON) $(SCRIPT) --mcp

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

setup: ## Install minimal CLI dependencies; conversion tools install on demand
	$(PYTHON) -m pip install -r requirements.txt

setup-mcp: ## Install optional MCP support
	$(PYTHON) -m pip install -r requirements-mcp.txt

start: ## Run converter
	$(PYTHON) $(SCRIPT) $(ARGS)

check: ## Verify dependencies
	@$(PYTHON) -m customs.check_deps

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

cache-clear: ## Clear conversion cache (checksum DB)
	@$(PYTHON) -c "from customs.cache import clear_cache; removed=clear_cache(); print(f'Removed cache DBs: {removed}' if removed else 'No cache DB found.')"

cache-stats: ## Show cache entry count and storage stats
	@$(PYTHON) -c "from customs.cache import CacheManager; import json; cm=CacheManager(); print(json.dumps(cm.stats(), indent=2)); cm.close()"

