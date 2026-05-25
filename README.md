![Banner](Banner.png)

# Convergent: Local File Converter Utility

> **Convergent** is a professional, high-performance CLI utility designed for batch file conversion. 
> It leverages power of FFmpeg and ImageMagick to provide seamless transformations between images, videos, and documents with a premium command-line experience.

## Getting Started

### Prerequisites

-   **Python 3.10+**
-   **Homebrew** (recommended for macOS system dependencies)

### Installation

1.  **Clone Repository**: Clone or download full repo — `Convergent.py`, `Makefile`, `modules/`, and `customs/` must all be present in same directory.
2.  **Run Setup**:
    ```bash
    make setup
    ```
    *This will install Python dependencies from `requirements.txt` (including `rich`) and attempt to install system dependencies like `ffmpeg`, `imagemagick`, `ghostscript`, and `pandoc` using your system's package manager (`brew`, `apt`, `dnf`, or `pacman`).*
3.  **Check Dependencies**:
    ```bash
    make check
    ```
    *This will probe your system for all required external tools and ensure they are ready to use.*

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
| `--overwrite` | Overwrite existing output files without prompting | `--overwrite` |
| `--skip` | Skip existing output files without prompting | `--skip` |

**Example Commands:**
```bash
# Convert HEIC images to JPG using 4 parallel jobs
make start ARGS="--from HEIC --to JPG --path ~/Desktop/Photos --jobs 4"

# Convert Video to GIF with 30 FPS
make start ARGS="--from MP4 --to GIF --fps 30 --path ./video.mp4"

# Force overwrite of existing files or skip them silently
make start ARGS="--from JPG --to PNG --path ./images --overwrite"
```

## Features

-   **Interactive & CLI**: Numeric menu for manual runs, or direct command-line arguments for automated pipelines.
-   **High Performance**: Multi-core parallel batch processing for high-speed conversions.
-   **Smart Input**: Drag-and-drop multiple files/folders; automatically handles escaped spaces and messy paths.
-   **Multi-Format Support**:
    -   **PDF**: Merge, split, or export pages to JPG/PNG.
    -   **Images**: Convert HEIC, JPG, PNG, WEBP, SVG, and RAW formats (Sony ARW, Adobe DNG).
    -   **Video/Audio**: Convert MOV, MP4, WEBM, GIF, AVI, MP3, WAV, M4A; split MP4 by chapter/segment.
    -   **Documents**: Convert Office formats (DOCX, PPTX, RTF) to PDF.
    -   **Notability (Beta)**: Convert `.ntb` note packages to standard PDF (extracts high-res embedded PDFs or page previews).
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

When output files already exist, Convergent protects your work with an interactive collision guard:

1. **Batch Collision Preview Table**: If multiple output files already exist, Convergent displays a unified **Rich Table** showing details of all conflicts, including:
   - File Size (formatted cleanly)
   - Last Modified timestamp
   Users can apply a quick action globally across all conflicts:
   - `[O]` Overwrite All
   - `[S]` Skip All
   - `[K]` Keep All (Auto-Rename)
   - `[I]` Decide Individually

2. **Shift Key "Apply to All" Shortcut (Individual Mode)**:
   If you choose to decide individually, you are prompted for each conflict. To save time, you can hold **Shift** when selecting your option to apply it to all remaining conflicts immediately:
   - **`o` / `s` / `k`** (lowercase): Overwrite / Skip / Keep **only this file**.
   - **`O` / `S` / `K`** (Shift-modified uppercase): Overwrite All / Skip All / Keep All for **all remaining files**.

## Troubleshooting

- **Ghostscript not found**: Ensure `gs` is in your system PATH. Run `brew install ghostscript` to install or fix link.
- **ImageMagick policy error**: If PDF or HEIC processing fails, edit `/usr/local/etc/ImageMagick-7/policy.xml` to allow these formats (change `rights="none"` to `rights="read|write"` for relevant patterns).
- **Pandoc PDF fonts**: If converting documents to PDF fails, ensure you have a LaTeX distribution installed (e.g., `brew install --cask mactex` or `basictex`).
- **RAW Image Support**: On macOS, Sony `ARW` and Adobe `DNG` are supported natively via `sips`. On Linux, ensure `darktable` or `rawtherapee` is installed to provide necessary delegates for ImageMagick.

## Tech Stack & Requirements

| Layer | Technology | Tested On |
|---|---|---|
| **OS** | macOS | 14+ (Sonoma) |
| **Language** | [Python 3](https://www.python.org/) | 3.10+ |
| **Processing Engine** | [FFmpeg](https://ffmpeg.org/) | 6+ |
| **Image Engine** | [ImageMagick](https://imagemagick.org/) | 7+ |
| **PDF Engine** | [Ghostscript](https://ghostscript.com/) | 10+ |
| **Document Engine** | [Pandoc](https://pandoc.org/) | 3+ |
| **CLI Framework** | `argparse` + `tty` | - |
| **UI/Styling** | [Rich](https://github.com/Textualize/rich) | - |

> [!NOTE]
> **Compatibility**: This utility is **macOS-first**. Linux is supported and dependencies can be automatically installed via `apt`, `dnf`, or `pacman`. Windows is **not supported** due to `tty` terminal dependency.

## Project Structure

```
Convergent/
├── Convergent.py        # Entry point: CLI args, main menu, Converter class
├── Makefile             # Build targets: setup, start, check, shortcut, clean
├── requirements.txt     # Python dependencies (rich)
├── modules/             # Format-specific conversion logic
│   ├── audio.py
│   ├── compress.py
│   ├── decompress.py
│   ├── doc.py
│   ├── image.py
│   ├── ntb.py            # Notability .ntb to PDF conversion (Beta)
│   ├── pdf_manip.py
│   └── video.py
└── customs/             # Shared utilities and helpers
    ├── check_deps.py
    ├── console.py       # Fallback mock console for rich-less environments
    ├── file_process.py
    ├── run_command.py
    └── shortcut.py
```

## Owner
**Kaiwen Du** - [GitHub](https://github.com/ItsKaiwenDu)

## License
Licensed under Apache License, Version 2.0. See [LICENSE](LICENSE) for details.
