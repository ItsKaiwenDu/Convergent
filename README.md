![Banner](Banner.png)

# Convergent: Local File Converter Utility

> **Convergent** is a professional, high-performance CLI utility designed for batch file conversion. 
> It leverages power of FFmpeg and ImageMagick to provide seamless transformations between images, videos, and documents with a premium command-line experience.

## Getting Started

### Prerequisites

-   **Python 3.10+**
-   **Homebrew** (recommended for macOS system dependencies)

### Installation

1.  **Clone Repository**: Clone or download full repository. Ensure `Convergent.py`, `Makefile`, `modules/`, and `customs/` are all present in same directory.
2.  **Run Setup**:
    ```bash
    make setup
    ```
    *Installs Python dependencies from `requirements.txt` (incl. `rich`) and system tools (`ffmpeg`, `imagemagick`, `ghostscript`, `pandoc`) via your package manager (`brew`, `apt`, `dnf`, `pacman`).*
3.  **Check Dependencies & Auto-Update**:
    ```bash
    make check
    ```
    *Verifies dependencies and automatically pulls remote updates from GitHub origin if behind.*

## Usage

### Help
View all available Makefile targets:
```bash
make help
```

### Interactive Mode
Simply run following command and follow on-screen prompts:
```bash
make start
```

### Desktop Shortcut
Create a clickable terminal script to launch Convergent from anywhere (e.g., your Desktop) without manual navigation:
```bash
make shortcut
```
*This generates a `.command` file that you can double-click to open Terminal and run utility instantly.*

### Finder Quick Action (macOS)
Bind a saved Convergent shortcut to Finder's right-click menu so selected files or folders are sent straight into that workflow:
```bash
make quick-action
```
*First create a shortcut in Convergent (`make start` → `+`). The installer lists your saved shortcuts, writes an Automator Quick Action to `~/Library/Services/`, and opens Terminal to run the conversion. Use `--shortcut KEY --path` for direct CLI runs:*
```bash
make start ARGS="--shortcut S --path ~/Desktop/photo.heic"
```

### Clean Workspace
Remove all compiled Python cache (`__pycache__`) directories across project:
```bash
make clean
```

### CLI Mode (Arguments)
For automated workflows, you can pass arguments directly using `ARGS` variable.

| Flag | Description | Example |
|---|---|---|
| `--from` | Source file extension (e.g., `HEIC`, `MOV`) | `--from HEIC` |
| `--to` | Target output extension (e.g., `JPG`, `MP3`) | `--to JPG` |
| `--path` | Absolute path to file or directory | `--path ~/Desktop/Photos` |
| `--jobs`, `-j` | Number of parallel processing jobs (default: CPU count) | `--jobs 4` |
| `--fps` | Target frames per second (for GIF output) | `--fps 30` |
| `--bitrate` | Audio bitrate for MP3 conversion (e.g., `128k`, `192k`, `320k`) | `--bitrate 320k` |
| `--md-pdf-mode` | Rendering mode for Markdown to PDF (`formatted` or `raw`) | `--md-pdf-mode raw` |
| `--strip-metadata` | Remove EXIF/IPTC metadata from images for privacy | `--strip-metadata` |
| `--shortcut` | Run a saved shortcut by key (requires `--path` unless shortcut has a fixed path) | `--shortcut S` |
| `--overwrite` | Overwrite existing output files without prompting | `--overwrite` |
| `--skip` | Skip existing output files without prompting | `--skip` |

**Example Commands:**
```bash
# Convert HEIC images to JPG using 4 parallel jobs and strip EXIF metadata
make start ARGS="--from HEIC --to JPG --path ~/Desktop/Photos --jobs 4 --strip-metadata"

# Convert Video to GIF with 30 FPS
make start ARGS="--from MP4 --to GIF --fps 30 --path ./video.mp4"

# Force overwrite of existing files or skip them silently
make start ARGS="--from JPG --to PNG --path ./images --overwrite"

# Convert Markdown to raw PDF instead of human-friendly typeset PDF
make start ARGS="--from MD --to PDF --path ./document.md --md-pdf-mode raw"
```

## Features

-   **Interactive & CLI**: Numeric menu for manual runs, or direct command-line arguments for automated pipelines.
-   **High Performance**: Multi-core parallel batch processing for high-speed conversions.
-   **Smart Input**: Handles escaped spaces, messy paths, and EXIF auto-rotation for drag-and-dropped files.
-   **Image Privacy**: Strips EXIF/IPTC metadata via CLI flag, interactive prompts, or saved shortcuts.
-   **Multi-Format Support**:
    -   **PDF**: Merge (with interactive page-order preview and reordering), split, or export pages to JPG/PNG/TIFF.
    -   **Images**: Convert HEIC, HEIF, AVIF, JPG, PNG, WEBP, TIFF, BMP, SVG, and RAW formats (Sony ARW, Adobe DNG).
    -   **Video/Audio**: Convert MOV, MP4, WEBM, GIF, AVI, MKV, FLAC, MP3, WAV, M4A; split MP4 by chapter/segment, or merge MP4 (with interactive preview and reordering).
    -   **Documents**: Convert Office formats (DOCX, PPTX, RTF) to PDF, and Markdown (MD) to PDF (with options for typeset human-friendly or raw text), HTML, or TXT.
    -   **Notability (Beta)**: Convert `.ntb` note packages to standard PDF. Supports natural-order extraction and merging of multi-page imported PDF backgrounds, or compiles all available page preview thumbnails for native drawing notes.
    -   **Archives**: Compress/decompress ZIP, RAR, 7z, and TAR (.gz, .bz2, .xz) with optional password protection.
-   **Shortcuts**: Save, edit, and trigger persistent workflows with single-key shortcuts.
-   **Safety First**: Safe overwrite guard with macOS Trash integration (uses `trash` CLI/AppleScript), interactive collision preview tables, and bulk shift-modified actions.
-   **Premium UI**: Rich terminal interface with progress bars, status indicators, and real-time benchmarking timers.

## Quick Shortcuts

Save frequent workflows as persistent shortcuts for instant access.

- **Manage Shortcuts**: Manage your workflows directly from main menu:
  - `[+]` Create
  - `[=]` Edit
  - `[-]` Delete
- **Skip Prompts**: Save a fixed file or folder path in any shortcut to completely skip input path prompt.
- **Persistence**: Saved automatically to `~/.convergent_shortcuts.json` and loaded into main menu on startup.

## Collision Handling & Overwrite Guard

If output files already exist, a **Collision Preview** table lists conflicts and prompts you immediately:

- `[o]`: Overwrite once | `[Shift] + [o]`: Overwrite all
- `[s]`: Skip once | `[Shift] + [s]`: Skip all
- `[k]`: Keep both (auto-rename) once | `[Shift] + [k]`: Keep all
- `[c]`: Cancel entire operation

## Post-Conversion Actions

After conversion, you can choose:
- `[m]`: Move converted files/folders to a new directory.
- `[u]`: Undo conversion (move output files to Trash).
- `[Any other key]`: Return to main menu.

## Troubleshooting

- **Ghostscript not found**: Ensure `gs` is in your system PATH. Run `brew install ghostscript` to install or fix link.
- **ImageMagick policy error**: If PDF or HEIC processing fails, edit `/usr/local/etc/ImageMagick-7/policy.xml` to allow these formats (change `rights="none"` to `rights="read|write"` for relevant patterns).
- **Pandoc PDF fonts / Markdown to PDF**: If converting documents to PDF fails, ensure you have a LaTeX distribution or Typst installed (e.g., `brew install pandoc typst`).
- **Office styling off**: Install LibreOffice (`brew install --cask libreoffice`) for high-fidelity DOCX/PPTX/RTF to PDF layout conversion.
- **RAW Image Support**: On macOS, Sony `ARW` and Adobe `DNG` are supported natively via `sips`. On Linux, ensure `darktable` or `rawtherapee` is installed to provide necessary delegates for ImageMagick.

## Tech Stack & Requirements

| Layer | Technology | Tested On |
|---|---|---|
| **OS** | macOS | 14+ (Sonoma) |
| **Language** | [Python 3](https://www.python.org/) | 3.10+ |
| **Processing Engine** | [FFmpeg](https://ffmpeg.org/) | 6+ |
| **Image Engine** | [ImageMagick](https://imagemagick.org/) | 7+ |
| **PDF Engine** | [Ghostscript](https://ghostscript.com/) | 10+ |
| **Document Engine** | [Pandoc](https://pandoc.org/) + [Typst](https://typst.app/) + [LibreOffice](https://www.libreoffice.org/) | 3+ / 0.14+ / 24+ |
| **Archive Engine** | [7-Zip](https://www.7-zip.org/) + `unrar`/`rar` | 23+ |
| **CLI Framework** | `argparse` + `tty` | - |
| **UI/Styling** | [Rich](https://github.com/Textualize/rich) | - |

> [!NOTE]
> **Compatibility**: This utility is **macOS-first**. Linux is supported and dependencies can be automatically installed via `apt`, `dnf`, or `pacman`. Windows is **not supported** due to `tty` terminal dependency.

## Project Structure

```
Convergent/
├── Convergent.py        # Main CLI entry point and menu orchestrator
├── Makefile             # Task automation (setup, run, check, clean)
├── requirements.txt     # Python dependencies
├── modules/             # Format-specific conversion engines
│   ├── audio.py         # Audio format conversion
│   ├── compress.py      # Archive compression (ZIP, TAR, 7Z, RAR)
│   ├── decompress.py    # Archive decompression
│   ├── doc.py           # Document conversion (Office & Markdown)
│   ├── image.py         # Image conversion (HEIC, JPG, PNG, RAW, etc.)
│   ├── ntb.py           # Notability .ntb to vector PDF conversion
│   ├── pdf_manip.py     # PDF tools (merge, split, page export)
│   └── video.py         # Video conversion, segment splitting, and merging
└── customs/             # Shared helpers and utility frameworks
    ├── check_deps.py    # CLI dependency validator
    ├── console.py       # Terminal UI and rich-text helper
    ├── file_process.py  # Queue manager and collision handler
    ├── run_command.py   # Subprocess shell command runner
    ├── shortcut.py      # Custom workflow CRUD manager
    └── quick_action.py  # macOS Finder Quick Action installer
```

## Owner
**Kaiwen Du** - [GitHub](https://github.com/ItsKaiwenDu)

## License
Licensed under Apache License, Version 2.0. See [LICENSE](LICENSE) for details.
