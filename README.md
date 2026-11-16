![Banner](Banner.png)

# Convergent: Local File Converter Utility

> **Convergent** is a professional, high-performance CLI utility designed for batch file conversion. 
> It leverages power of FFmpeg and ImageMagick to provide seamless transformations between images, videos, and documents with a premium command-line experience.

[![CI](https://github.com/ItsKaiwenDu/Convergent/actions/workflows/ci.yml/badge.svg)](https://github.com/ItsKaiwenDu/Convergent/actions/workflows/ci.yml)

## Key Features

-   **Daily Conversion Formats**: Convert, merge, split, resize, and compress everyday images, videos, audio, documents, and archives—plus extract text from scans (`OCR`) and transcribe speech to text.
-   **Local MCP for AI Agent**: Built-in Model Context Protocol (`stdio`) server that lets AI coding assistants (Codex, Claude Code, Google Antigravity, OpenCode, etc.) run file conversions directly on your machine.
-   **Optimized for Efficiency**: Multi-core parallel batch processing, hardware-accelerated transcoding (`VideoToolbox`, `NVENC`, `QSV`, Apple Metal for Whisper), and `blake2b` checksum caching to skip unchanged files.
-   **Shortcuts**: Save and trigger your frequent conversion workflows with single-key shortcuts in the interactive menu, or run them straight from macOS Finder's right-click Quick Action menu.
-   **Private & Offline Use**: Runs 100% offline with zero cloud uploads, strips hidden `EXIF/IPTC` metadata, previews filename collisions before overwriting, and moves replaced files to macOS Trash for safe recovery.

## Getting Started

### Prerequisites

-   **Python 3.10+**
-   **Homebrew** (recommended for macOS system dependencies)

### Installation

1.  **Clone Repository**: Clone repository and navigate into project directory:
    ```bash
    git clone https://github.com/ItsKaiwenDu/Convergent.git
    cd Convergent
    ```
    *Ensure `Convergent.py`, `Makefile`, `modules/`, and `customs/` are all present in same directory.*
2.  **Run Setup**:
    ```bash
    make setup
    ```
    *Installs `rich`; interactive mode offers missing conversion tools on first use and reuses installed ones.*
3.  **Check Dependencies**:
    ```bash
    make check
    ```
    *Lists optional tools; missing tools do not block startup.*
4.  **Update Repository**:
    ```bash
    make update
    ```
    *Pulls latest updates from GitHub origin and syncs Python dependencies.*
5.  **Run Tests**:
    ```bash
    make test
    ```
    *Runs automated tests. MCP and real-conversion tests require their optional dependencies.*

## Usage

### User Commands

See [EXAMPLE_USAGE.md](EXAMPLE_USAGE.md#user-makefile-examples) for examples.

| Command | Description |
|---|---|
| `make start` | Launch interactive terminal UI with single-key navigation, drag-and-drop input, and saved shortcuts |
| `make setup` | Install minimal CLI dependencies; conversion tools install on demand |
| `make setup-mcp` | Install optional MCP support |
| `make shortcut` | Generate a clickable `.command` desktop shortcut for instant one-click access |
| `make quick-action` | Bind a saved shortcut to macOS Finder's right-click context menu (create shortcut via `make start` → `+` first) |
| `make update` | Pull latest updates from GitHub and sync Python dependencies |
| `make help` | View all available Makefile targets |

### Automation & Maintenance

| Command | Description |
|---|---|
| `make mcp` | Start local MCP server over `stdio` for AI coding assistants |
| `make mcp-config` | Print copy-paste JSON config for Claude Desktop, OpenCode, Cursor, etc. |
| `make check` | Verify installed conversion dependencies |
| `make test` | Run automated unit test suite |
| `make cache` | Display cached fingerprint records, TTL, and SQLite database storage size (`~/.convergent_cache.sqlite`) |
| `make cache-clear` | Delete all cached conversion checksums to force full re-conversion. This is automatically handled by Convergent. |
| `make clean` | Remove all compiled Python `__pycache__` directories across workspace |

### CLI Mode (Arguments)
For automated workflows, pass arguments using `ARGS`. CLI batches never prompt; missing tools return an error unless `--install-deps` is supplied. See [EXAMPLE_USAGE.md](EXAMPLE_USAGE.md#cli-mode-examples) for examples.

| Flag | Description |
|---|---|
| `--install-deps` | Install required tools/models without prompting |
| `--from` | Source file extension (e.g., `HEIC`, `MOV`) |
| `--to` | Target output extension (e.g., `JPG`, `MP3`) |
| `--path` | Path to input file/dir (or `-` for stdin pipe) |
| `--stdin` | Read binary input from standard input (`stdin`) |
| `--stdout` | Write binary converted output to standard output (`stdout`) |
| `--jobs`, `-j` | Number of parallel processing jobs (default: CPU count) |
| `--fps` | Target frames per second (for GIF output) |
| `--bitrate` | Audio bitrate for MP3 conversion (e.g., `128k`, `192k`, `320k`) |
| `--stt` | Perform Speech-to-Text transcription on audio/video input |
| `--model` | Whisper model size for STT (`base` ~142MB, `tiny` ~75MB, `small` ~466MB, `turbo` / `large-v3-turbo` ~1.5GB; default: `base`) |
| `--language` | Language code for STT transcription (e.g., `en`, `es`, `zh`, `auto`) |
| `--hwaccel` | Hardware acceleration mode (`auto`, `videotoolbox`, `nvenc`, `qsv`, `none`; default: `auto`) |
| `--md-pdf-mode` | Rendering mode for Markdown to PDF (`formatted` or `raw`) |
| `--strip-metadata` | Remove EXIF/IPTC metadata from images for privacy |
| `--dpi` | Resolution for PDF-to-image conversion (default: `300`) |
| `--cache` | Enable checksum-validated caching (default: enabled) |
| `--no-cache`, `--force` | Disable cache and force re-conversion of all files |
| `--cache-ttl` | Cache expiration Time-To-Live in days (default: `30`, `0` to disable) |
| `--shortcut` | Run a saved shortcut by key (requires `--path` unless shortcut has a fixed path) |
| `--overwrite` | Overwrite existing output files without prompting |
| `--skip` | Skip existing output files without prompting |
| `--resume` | Resume / retry last failed batch conversion |

## Supported Formats

| Category | Formats & Ops | Technology |
| :--- | :--- | :--- |
| **Images** | `JPG`, `PNG`, `HEIC`, `HEIF`, `AVIF`, `WEBP`, `TIF`, `BMP`, `SVG`, `ARW`, `DNG` | Native macOS `sips` acceleration, ImageMagick fallback, metadata stripping |
| **Video** | `MOV`, `MP4`, `WEBM`, `GIF`, `AVI`, `MKV` | Hardware encoding (`VideoToolbox`, `NVENC`, `QSV`), custom FPS, split & merge |
| **Audio** | `MP3`, `WAV`, `M4A`, `FLAC`, `AAC`, `OGG` | FFmpeg audio encoding, custom bitrates (`128k`, `192k`, `320k`), split & merge |
| **Documents** | `PDF`, `DOCX`, `PPTX`, `RTF`, `HTML`, `MD`, `TXT` | Pandoc, Typst, LibreOffice, and Ghostscript layout fidelity |
| **Archives** | `ZIP`, `TAR`, `TAR.GZ`, `TAR.BZ2`, `TAR.XZ`, `7Z`, `RAR` | 7-Zip, tar, and rar compression/extraction with optional password protection |
| **Resize** | `JPG`, `PNG`, `HEIC`, `MP4`, `MOV`, `PDF` | Percentage scaling, target height, exact dimensions, aspect-ratio crop (16:9, 4:3, 1:1, 9:16), bicubic PDF downsampling |
| **OCR** | `JPG`, `PNG`, `HEIC`, `WEBP`, `PDF` → `TXT`, `MD`, `DOCX` | Local text extraction via native Apple Vision Framework (macOS) or Tesseract |
| **Speech-to-Text** | `MP3`, `WAV`, `M4A`, `FLAC`, `AAC`, `OGG`, `MP4`, `MOV`, `MKV`, `WEBM`, `AVI` → `TXT`, `SRT`, `VTT`, `MD` | Local `whisper.cpp` Metal-accelerated transcription models (`base`, `tiny`, `small`, `turbo`) |
| **Combine & Split** | `PDF`, `DOCX`, `PPTX`, `MP4`, `MP3`, `GIF`, `TXT` | Multi-file concatenation, interactive page reordering, chapter/interval splitting |

## MCP

Convergent runs as a **100% local Model Context Protocol (MCP) server** over `stdio`, letting AI coding assistants (Codex, Claude Code, Google Antigravity, OpenCode, Cursor, etc.) run file conversions directly on your machine.

### Option 1: Prompt for AI Agent

1. **Setup**: "Install Convergent's MCP dependencies (`make setup-mcp`) and register its local `stdio` MCP server using `make mcp-config`."
2. **`/convergent` Skill Setup** "Create a minimal `/convergent` `SKILL.md` that points to Convergent's local MCP tools so you can invoke it on demand without consuming extra tokens."

### Option 2: Manual Setup

1. Install optional MCP support & generate your client config:
   ```bash
   make setup-mcp
   make mcp-config
   ```
2. Add printed JSON to your AI client's MCP config (e.g., `claude_desktop_config.json`):
   ```json
   {
     "mcpServers": {
       "convergent": {
         "command": "python3",
         "args": [
           "/path/to/Convergent/Convergent.py",
           "--mcp"
         ]
       }
     }
   }
   ```
3. To start server, run `make mcp` (or `python3 Convergent.py --mcp --install-deps` to allow auto tool/model downloads).

### Available MCP Tools

| Tool | Description |
| :--- | :--- |
| `convert` | General-purpose file & directory converter |
| `pdf_to_images` | Convert multi-page PDFs to image sequences for visual model analysis |
| `extract_audio` | Extract audio tracks from video files for transcription |
| `ocr` | Extract plain text or Markdown from images or scanned PDFs using local OCR |
| `stt` | Perform local Speech-to-Text transcription on audio/video to generate text or subtitles |
| `combine` | Merge multiple PDFs, videos, audio clips, or documents into a single file |
| `split` | Split PDFs, videos, audio files, or documents into segments |
| `compress` | Compress files or directories into archives with optional password protection |
| `decompress` | Decompress archive packages safely to target directories |
| `resize` | Resize, rescale, crop aspect ratio, or strip metadata from images, video, or PDF documents |
| `list_supported_formats` | Query all supported format conversions and category mappings |

## Quick Shortcuts

Save frequent workflows as persistent shortcuts for instant access.

- **Manage Shortcuts**: Manage workflows directly from main menu:
  - `[+]` Create
  - `[=]` Edit
  - `[-]` Delete
- **Instant Run**: Trigger any shortcut directly from initial prompt or via `--shortcut KEY`.
- **Skip Prompts**: Save a fixed file or folder path in any shortcut to completely skip input path prompt.
- **Persistence**: Saved automatically to `~/.convergent_shortcuts.json` and loaded into main menu on startup.

## Collision Handling & Overwrite Guard

Interactive mode prompts with a **Collision Preview** table before overwriting existing files. For automation, CLI skips existing outputs unless `--overwrite` is set, and MCP (`overwrite=False`) rejects single-file/custom target conflicts while skipping existing batch outputs and reporting `skipped_files`.

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues and step-by-step fixes.

## Tech Stack & Requirements

| Layer | Technology | Tested On |
|---|---|---|
| **OS** | macOS | 14+ (Sonoma) |
| **Language** | [Python 3](https://www.python.org/) | 3.10+ |
| **Processing Engine** | [FFmpeg](https://ffmpeg.org/) | 6+ |
| **Image Engine** | [ImageMagick](https://imagemagick.org/) 7+ + macOS `sips` | 7+ / Native |
| **PDF Engine** | [Ghostscript](https://ghostscript.com/) | 10+ |
| **Document Engine** | [Pandoc](https://pandoc.org/) + [Typst](https://typst.app/) + [LibreOffice](https://www.libreoffice.org/) | 3+ / 0.14+ / 24+ |
| **OCR Engine** | Apple Vision (macOS native) + [Tesseract](https://github.com/tesseract-ocr/tesseract) | - / 5+ |
| **STT Engine** | [whisper.cpp](https://github.com/ggerganov/whisper.cpp) (`whisper-cli`) | 1.5+ |
| **Archive Engine** | [7-Zip](https://www.7-zip.org/) + `unrar`/`rar` | 23+ |
| **CLI Framework** | `argparse` + `tty` | - |
| **UI/Styling** | [Rich](https://github.com/Textualize/rich) | - |

> [!NOTE]
> **Compatibility**: This utility is **macOS-first**. Linux is supported and dependencies can be automatically installed via `apt`, `dnf`, or `pacman`. Windows is **not supported** due to `tty` terminal dependency.

## Project Structure

```
Convergent/
├── Convergent.py             # Main CLI & interactive TUI entry point
├── Makefile                  # Task automation commands
├── requirements.txt          # Core Python dependencies
├── requirements-mcp.txt      # Optional MCP dependencies
├── mcp_server/               # Local MCP server package
├── modules/                  # Format conversion, OCR, STT, resize, and merge/split engines
├── customs/                  # Shared utilities (caching, hardware detection, shortcuts, UI)
└── tests/                    # Unit and integration tests
```

## Owner

**Kaiwen Du**: A Junior student majoring in Computer Science at Santa Clara University.
- **GitHub**: [ItsKaiwenDu](https://github.com/ItsKaiwenDu)
- **LinkedIn**: [kaiwen-du](https://www.linkedin.com/in/kaiwen-du/)

## License
Licensed under Apache License, Version 2.0. See [LICENSE](LICENSE) for details.
