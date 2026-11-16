# Troubleshooting

Common issues and fixes, organized from daily usage to specific subsystems and sorted A–Z within each section.

## Daily & General

| Problem | Step-by-Step Fix |
| :--- | :--- |
| **Cache taking up too much disk space** | 1. Run `make cache` to inspect current cache usage in `~/.cache/convergent/`.<br>2. Run `make clean-cache` to clear cached models and temporary files. |
| **Dependency installation fails** | 1. Run `make check` to see which tools are missing.<br>2. Ensure you have internet access and a supported package manager (`brew`, `apt`, `dnf`, or `pacman`).<br>3. On Linux unattended installs, ensure `root` or passwordless `sudo` is available, or install the missing package manually. |
| **Output file already exists / unexpected `_1` suffix** | Convergent automatically appends `_1`, `_2`, etc. when an output file already exists to prevent accidental overwrites. Rename or remove the existing file if you want the original filename. |
| **Permission denied or `Operation not permitted` on macOS** | 1. Open **System Settings > Privacy & Security > Full Disk Access**.<br>2. Enable access for your terminal app (Terminal, iTerm2, Warp, etc.) and retry. |
| **Terminal UI looks broken or keys don't respond** | 1. Ensure you are running in an interactive TTY terminal (not a non-interactive pipe or Windows).<br>2. For scripted or headless runs, pass explicit CLI flags or use `Convergent.py --mcp`. |

## Documents, PDF & OCR

| Problem | Step-by-Step Fix |
| :--- | :--- |
| **Document / Office to PDF fails or styling is off** | 1. For Markdown/Pandoc to PDF, install Typst or LaTeX: `brew install pandoc typst`.<br>2. For high-fidelity `DOCX`/`PPTX`/`RTF` layouts, install LibreOffice: `brew install --cask libreoffice`. |
| **Ghostscript (`gs`) not found** | 1. Run `which gs` to check if Ghostscript is in your `PATH`.<br>2. Install or relink it with `brew install ghostscript` (or your Linux package manager). |
| **ImageMagick policy error (PDF / HEIC)** | 1. Open `/usr/local/etc/ImageMagick-7/policy.xml` (or `/etc/ImageMagick-7/policy.xml` on Linux).<br>2. Find the `<policy>` lines for `PDF` or `HEIC`.<br>3. Change `rights="none"` to `rights="read\|write"` and save. |
| **OCR returns empty or garbled text** | 1. Verify the source image or PDF page is clear and high enough resolution.<br>2. On Linux (or if Apple Vision is unavailable), install Tesseract: `brew install tesseract` / `sudo apt install tesseract-ocr`. |
| **PDF to images is slow or produces huge files** | Lower the target DPI or resize the output images using the `resize` action (or `resize` MCP tool) after conversion. |

## Audio, Video & Speech-to-Text

| Problem | Step-by-Step Fix |
| :--- | :--- |
| **FFmpeg hardware acceleration fails (VideoToolbox / NVENC / QSV)** | Convergent automatically falls back to software encoding (`libx264`) if hardware acceleration is unavailable. Update FFmpeg (`brew upgrade ffmpeg`) or your GPU drivers if you need hardware speed. |
| **No audio in converted video or audio extraction fails** | 1. Check whether the source video actually contains an audio stream.<br>2. Ensure `ffmpeg` is installed (`make check`). |
| **Resizing or FPS change produces distorted video** | 1. Keep aspect ratio locked unless you intentionally want a crop or stretch.<br>2. Use standard FPS values (e.g., `24`, `30`, `60`) supported by the target container. |
| **Video conversion is slow** | 1. Ensure hardware acceleration is working (`ffmpeg -hwaccels`).<br>2. On Apple Silicon Macs, VideoToolbox is used automatically when available. |
| **Whisper Speech-to-Text fails** | 1. Install `whisper.cpp` via `brew install whisper-cpp`.<br>2. Re-run with `--install-deps` (or approve the prompt in `make start`) to download models into `~/.cache/convergent/models/`. |

## Archives & MCP

| Problem | Step-by-Step Fix |
| :--- | :--- |
| **Archive extraction fails for `.rar` or `.7z`** | 1. Run `make check` to verify `7z` and `unrar`/`rar` are installed.<br>2. Install missing tools: `brew install p7zip rar` (macOS) or `sudo apt install p7zip-full unrar` (Linux). |
| **Decompression skips files or warns about path traversal** | Convergent blocks unsafe archive entries containing `..` or absolute paths to protect your filesystem. Inspect the archive contents before extracting manually. |
| **MCP client cannot connect to Convergent** | 1. Run `make setup-mcp` to install MCP dependencies.<br>2. Run `make mcp-config` and verify the exact `python3` path and `/path/to/Convergent/Convergent.py` in your client's config.<br>3. Restart your MCP client. |
| **MCP server hangs or prompts for input** | MCP mode (`--mcp`) never prompts interactively. If a tool needs missing dependencies or models, add `--install-deps` to the `args` list in your MCP config. |
| **MCP tools missing or outdated** | Restart your MCP client after pulling updates so it reloads the latest tool definitions from `mcp_server/server.py`. |
