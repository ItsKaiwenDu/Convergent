![Banner](Banner.png)

# Convergent: Local File Converter Utility

> **Convergent** is a professional, high-performance CLI utility designed for batch file conversion. 
> It leverages power of FFmpeg and ImageMagick to provide seamless transformations between images, videos, and documents with a premium command-line experience.

[![CI](https://github.com/ItsKaiwenDu/Convergent/actions/workflows/ci.yml/badge.svg)](https://github.com/ItsKaiwenDu/Convergent/actions/workflows/ci.yml)

## Key Features

-   **Comprehensive Media & Document Suite**: Convert, merge, split, resize, compress, extract text (OCR), and transcribe speech across images, videos, audio, documents, and archives.
-   **Interactive TUI & Headless CLI**: Intuitive terminal menu with single-key navigation and drag-and-drop support, paired with scriptable CLI flags and Unix pipe streaming (`stdin`/`stdout`).
-   **100% Local MCP Server**: Standalone Model Context Protocol (`stdio`) server empowering AI coding assistants (Claude Desktop, Cursor, OpenCode, Zed) with local conversion tools.
-   **Hardware-Accelerated & Cached**: Multi-core parallel batch processing, hardware transcoding (`VideoToolbox`, `NVENC`, `QSV`, Apple Metal for Whisper), and `blake2b` checksum caching to skip unchanged files.
-   **Privacy & Safety First**: Fully offline execution, EXIF/IPTC metadata stripping, collision preview tables, and safe macOS Trash recovery.
-   **Persistent Workflow Shortcuts**: Save, edit, and trigger custom workflows with single-key shortcuts, plus native macOS Finder Quick Action context-menu integration.

## Supported Formats

| Category | Formats & Ops | Technology |
| :--- | :--- | :--- |
| **Images** | `JPG`, `PNG`, `HEIC`, `HEIF`, `AVIF`, `WEBP`, `TIF`, `BMP`, `SVG`, `ARW`, `DNG` | Native macOS `sips` acceleration, ImageMagick fallback, metadata stripping |
| **Video** | `MOV`, `MP4`, `WEBM`, `GIF`, `AVI`, `MKV` | Hardware encoding (`VideoToolbox`, `NVENC`, `QSV`), custom FPS, split & merge |
| **Audio** | `MP3`, `WAV`, `M4A`, `FLAC`, `AAC`, `OGG` | FFmpeg audio encoding, custom bitrates (`128k`, `192k`, `320k`), split & merge |
| **Documents** | `PDF`, `DOCX`, `PPTX`, `RTF`, `HTML`, `MD`, `TXT` | Pandoc, Typst, LibreOffice, and Ghostscript layout fidelity |
| **Archives** | `ZIP`, `TAR`, `TAR.GZ`, `TAR.BZ2`, `TAR.XZ`, `7Z`, `RAR` | 7-Zip, tar, and rar compression/extraction with optional password protection |
| **Resize** | `JPG`, `PNG`, `HEIC`, `MP4`, `PDF` | Percentage scaling, target height, exact dimensions, aspect-ratio crop (16:9, 4:3, 1:1, 9:16), bicubic PDF downsampling |
| **OCR** | `JPG`, `PNG`, `HEIC`, `WEBP`, `PDF` → `TXT`, `MD`, `DOCX` | Local text extraction via native Apple Vision Framework (macOS) or Tesseract |
| **Speech-to-Text** | `MP3`, `WAV`, `M4A`, `FLAC`, `AAC`, `OGG`, `MP4`, `MOV`, `MKV`, `WEBM`, `AVI` → `TXT`, `SRT`, `VTT`, `MD` | Local `whisper.cpp` Metal-accelerated transcription models (`base`, `tiny`, `small`, `turbo`) |
| **Combine & Split** | `PDF`, `DOCX`, `PPTX`, `MP4`, `MP3`, `GIF`, `TXT` | Multi-file concatenation, interactive page reordering, chapter/interval splitting |

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

| Command | Description |
|---|---|
| `make setup-mcp` | Install optional MCP support |
| `make start` | Launch interactive terminal UI with single-key navigation, drag-and-drop input, and saved shortcuts |
| `make shortcut` | Generate a clickable `.command` desktop shortcut for instant one-click access |
| `make quick-action` | Bind a saved shortcut to macOS Finder's right-click context menu (create shortcut via `make start` → `+` first) |
| `make cache-stats` | Display cached fingerprint records, TTL, and SQLite database storage size (`~/.convergent_cache.sqlite`) |
| `make cache-clear` | Delete all cached conversion checksums to force full re-conversion |
| `make clean` | Remove all compiled Python `__pycache__` directories across workspace |
| `make help` | View all available Makefile targets |

### CLI Mode (Arguments)
For automated workflows, pass arguments using `ARGS`. CLI batches never prompt; missing tools return an error unless `--install-deps` is supplied.

| Flag | Description | Example |
|---|---|---|
| `--install-deps` | Install required tools/models without prompting | `--install-deps` |
| `--from` | Source file extension (e.g., `HEIC`, `MOV`) | `--from HEIC` |
| `--to` | Target output extension (e.g., `JPG`, `MP3`) | `--to JPG` |
| `--path` | Path to input file/dir (or `-` for stdin pipe) | `--path ~/Desktop/Photos` |
| `--stdin` | Read binary input from standard input (`stdin`) | `--stdin` |
| `--stdout` | Write binary converted output to standard output (`stdout`) | `--stdout` |
| `--jobs`, `-j` | Number of parallel processing jobs (default: CPU count) | `--jobs 4` |
| `--fps` | Target frames per second (for GIF output) | `--fps 30` |
| `--bitrate` | Audio bitrate for MP3 conversion (e.g., `128k`, `192k`, `320k`) | `--bitrate 320k` |
| `--stt` | Perform Speech-to-Text transcription on audio/video input | `--stt` |
| `--model` | Whisper model size for STT (`base` ~142MB, `tiny` ~75MB, `small` ~466MB, `turbo` / `large-v3-turbo` ~1.5GB; default: `base`) | `--model turbo` |
| `--language` | Language code for STT transcription (e.g., `en`, `es`, `zh`, `auto`) | `--language en` |
| `--hwaccel` | Hardware acceleration mode (`auto`, `videotoolbox`, `nvenc`, `qsv`, `none`; default: `auto`) | `--hwaccel auto` |
| `--md-pdf-mode` | Rendering mode for Markdown to PDF (`formatted` or `raw`) | `--md-pdf-mode raw` |
| `--strip-metadata` | Remove EXIF/IPTC metadata from images for privacy | `--strip-metadata` |
| `--dpi` | Resolution for PDF-to-image conversion (default: `300`) | `--dpi 150` |
| `--cache` | Enable checksum-validated caching (default: enabled) | `--cache` |
| `--no-cache`, `--force` | Disable cache and force re-conversion of all files | `--no-cache` |
| `--cache-ttl` | Cache expiration Time-To-Live in days (default: `30`, `0` to disable) | `--cache-ttl 14` |
| `--shortcut` | Run a saved shortcut by key (requires `--path` unless shortcut has a fixed path) | `--shortcut S` |
| `--overwrite` | Overwrite existing output files without prompting | `--overwrite` |
| `--skip` | Skip existing output files without prompting | `--skip` |
| `--resume` | Resume / retry last failed batch conversion | `--resume` |

**Example Commands:**
```bash
# Install a specific tool before an automated run
python3 -m customs.check_deps --install ffmpeg

# Transcribe MP3 audio to plain text using local Whisper engine (base model)
make start ARGS="--from MP3 --to TXT --path ~/Desktop/recording.mp3"

# Generate timestamped SRT subtitles from an MP4 video using Whisper Turbo model
make start ARGS="--from MP4 --to SRT --path ./meeting.mp4 --model turbo"

# Convert HEIC images to JPG using 4 parallel jobs and strip EXIF metadata
make start ARGS="--from HEIC --to JPG --path ~/Desktop/Photos --jobs 4 --strip-metadata"

# Convert MOV video to MP4 using Apple Silicon hardware acceleration
make start ARGS="--from MOV --to MP4 --path ./video.mov --hwaccel auto"

# Force software encoding (libx264) for maximum compression
make start ARGS="--from MOV --to MP4 --path ./video.mov --hwaccel none"

# Convert Video to GIF with 30 FPS
make start ARGS="--from MP4 --to GIF --fps 30 --path ./video.mp4"

# Force overwrite of existing files or skip them silently
make start ARGS="--from JPG --to PNG --path ./images --overwrite"

# Convert Markdown to raw PDF instead of human-friendly typeset PDF
make start ARGS="--from MD --to PDF --path ./document.md --md-pdf-mode raw"

# Stream pipe: convert image from stdin and write binary JPG to stdout
cat input.heic | python3 Convergent.py --from HEIC --to JPG --stdout > output.jpg

# Convert image directly from macOS clipboard
pbpaste | python3 Convergent.py --from PNG --to WEBP --stdout > clipboard.webp

# Pipe FFmpeg audio stream into Convergent for 320k MP3 output
ffmpeg -i video.mp4 -vn -f wav pipe:1 | python3 Convergent.py --from WAV --to MP3 --bitrate 320k --stdout > audio.mp3
```

## Local MCP Server Integration

Convergent can run as a **100% local Model Context Protocol (MCP) server** over `stdio`. This allows local AI models, assistants, and IDE extensions (such as OpenCode, Claude Desktop, Cursor, Windsurf, Zed, etc.) to use Convergent's conversion capabilities directly.

### Running MCP Server
```bash
# Install optional MCP support and start server
make setup-mcp
make mcp

# Or directly via Python
python Convergent.py --mcp
```

*MCP never prompts. Add `--install-deps` to Python command to allow tool/model downloads.*

### Client Configuration Helper
To print ready-to-use JSON configuration snippets for your AI clients:
```bash
make mcp-config
```

#### Example `claude_desktop_config.json`:
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

### Available MCP Tools Exposed to AI Models
- `convergent_convert`: General-purpose file & directory converter (PDF, JPG, PNG, MP3, MP4, DOCX, MD, etc.).
- `pdf_to_images`: Convert multi-page PDFs to image sequences (JPG/PNG) for visual model analysis.
- `extract_audio`: Extract audio tracks (`MP3`, `WAV`, `AAC`, `FLAC`, `M4A`) from video files for transcription.
- `perform_ocr`: Extract plain text or Markdown from images or scanned PDFs using local OCR.
- `perform_stt`: Perform local Speech-to-Text transcription on audio/video to generate text or subtitles.
- `combine_files`: Merge multiple PDFs, videos, audio clips, or documents into a single file.
- `split_file`: Split PDFs, videos, audio files, or documents into segments.
- `compress_files`: Compress files or directories into archives (ZIP, TAR.GZ, 7Z, RAR) with optional password protection.
- `decompress_archive`: Decompress archive packages safely to target directories.
- `resize_media`: Resize, rescale, crop aspect ratio, or strip metadata from images, video, or PDF documents.
- `list_supported_formats`: Query all supported format conversions and category mappings.

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

In interactive mode, a **Collision Preview** table lists existing outputs and offers:

- `[o]`: Overwrite once | `[Shift] + [o]`: Overwrite all
- `[s]`: Skip once | `[Shift] + [s]`: Skip all
- `[k]`: Keep both (auto-rename) once | `[Shift] + [k]`: Keep all
- `[c]`: Cancel entire operation

**Automation:** CLI skips existing outputs unless `--overwrite` is set. For MCP, `overwrite=False` rejects destination conflicts on single-file/custom targets and safely skips existing outputs on batch/directory conversions while reporting `skipped_files`.

## Post-Conversion Actions

After conversion, you can choose from Post-Convert Options menu:
- `[d]`: Delete original (source) files (move to Trash).
- `[m]`: Move converted files/folders to a new directory.
- `[u]`: Undo conversion (move output files to Trash).
- `[q]`: Quit program.
- `[Any other key]`: Continue / Return to main menu.

## Troubleshooting

- **Dependency installation**: Uses `brew`, `apt`, `dnf`, or `pacman`; install manually if unavailable. Downloads need internet; conversion runs locally. Unattended Linux installs require root or passwordless sudo.
- **Ghostscript not found**: Ensure `gs` is in system PATH. Run `brew install ghostscript` to install or fix link.
- **ImageMagick policy error**: If PDF or HEIC processing fails, edit `/usr/local/etc/ImageMagick-7/policy.xml` to allow these formats (change `rights="none"` to `rights="read|write"` for relevant patterns).
- **Pandoc PDF fonts / Markdown to PDF**: If converting documents to PDF fails, ensure you have a LaTeX distribution or Typst installed (e.g., `brew install pandoc typst`).
- **Office styling off**: Install LibreOffice (`brew install --cask libreoffice`) for high-fidelity DOCX/PPTX/RTF to PDF layout conversion.
- **Whisper Speech-to-Text**: Install whisper.cpp via `brew install whisper-cpp`. Models download on approval or with `--install-deps`; cached in `~/.cache/convergent/models/`.
- **RAW Image Support**: On macOS, Sony `ARW` and Adobe `DNG` are supported natively via `sips`. On Linux, ensure `darktable` or `rawtherapee` is installed to provide necessary delegates for ImageMagick.

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
├── Convergent.py             # Main CLI entry point
├── Makefile                  # Task automation commands
├── requirements.txt          # Core Python dependencies
├── requirements-mcp.txt      # Optional MCP dependencies
├── tests/                    # Unit and integration tests
├── _config.yml               # GitHub Pages config
├── _includes/                # Documentation templates
│   └── head-custom.html      # Custom site headers & verification
├── mcp_server/               # Local MCP server package
│   ├── __init__.py           # Package initialization
│   ├── server.py             # FastMCP server and tool handlers
│   └── config_generator.py   # Client configuration generator
├── modules/                  # Format conversion engines
│   ├── audio.py              # Audio format conversion
│   ├── combine.py            # File merge & combine engine
│   ├── compress.py           # Archive compression
│   ├── decompress.py         # Archive extraction
│   ├── doc.py                # Office & Markdown conversion
│   ├── image.py              # Image format conversion
│   ├── resize.py             # Image, video & PDF resize engine
│   ├── ocr.py                # OCR text extraction
│   ├── pdf_manip.py          # PDF to image export
│   ├── split.py              # File splitting engine
│   ├── stt.py                # Speech-to-Text transcription
│   └── video.py              # Video format conversion
└── customs/                  # Shared helper utilities
    ├── cache.py              # Conversion caching (blake2b + SQLite)
    ├── check_deps.py         # Dependency check & installer
    ├── console.py            # Rich terminal UI helper
    ├── file_process.py       # File processing & collision guard
    ├── hwaccel.py            # Hardware acceleration detector
    ├── run_command.py        # Command execution runner
    ├── shortcut.py           # Custom shortcuts manager
    └── quick_action.py       # macOS Quick Action installer
```

## Owner

**Kaiwen Du**: A Junior student majoring in Computer Science at Santa Clara University.
- **GitHub**: [ItsKaiwenDu](https://github.com/ItsKaiwenDu)
- **LinkedIn**: [kaiwen-du](https://www.linkedin.com/in/kaiwen-du/)

## License
Licensed under Apache License, Version 2.0. See [LICENSE](LICENSE) for details.
