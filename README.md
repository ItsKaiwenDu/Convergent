![Banner](Banner.png)

# Convergent: Local File Converter Utility

**Version**: Build 49 (May 19, 2026)

> **Convergent** is a professional, high-performance CLI utility designed for batch file conversion. 
> It leverages power of FFmpeg and ImageMagick to provide seamless transformations between images, videos, and documents with a premium command-line experience.

## Features

-   **Interactive & CLI**: Streamlined numeric menu or direct command-line arguments for automation.
-   **High Performance**: Multi-core parallel batch processing for high-speed conversions.
-   **Smart Input**: Drag-and-drop multiple files/folders; handles messy paths and escaped characters automatically.
-   **Multi-Format Support**:
    -   **PDF**: Merge, split, or export pages as JPG/PNG.
    -   **Images**: HEIC, JPG, PNG, WEBP, Sony ARW, and Adobe DNG (RAW) cross-conversion.
    -   **Video/Audio**: MOV, MP4, WEBM, GIF, AVI, MP3, WAV, and M4A support.
    -   **Documents**: Convert Office files (DOCX, PPTX, RTF) to PDF.
    -   **Archives**: Compress or decompress ZIP, RAR, 7z, and TAR (.gz, .bz2, .xz) archives (optional password protection for ZIP).
    -   **Split**: Split a PDF into individual pages, or split an MP4 by chapter/segment.
-   **Shortcuts**: Save and edit persistent workflows for one-key triggers.
-   **Safety First**: Overwrite guard with an interactive **collision preview list** and skip flags.
-   **Premium UI**: Rich terminal output with progress bars, status indicators, and real-time per-file timing for benchmarking.

## Quick Shortcuts

Convergent allows you to save your most frequent workflows as shortcuts for instant access.

- **Create**: Press **+** in main menu to define a new shortcut with a custom symbol (key) and label title.
- **Remove**: Press **-** in main menu to delete existing shortcuts.
- **Edit**: Press **=** in main menu to modify an existing shortcut's properties.
- **Example**: Create a shortcut `S` for `HEIC to JPG` to batch convert photos with one key.
- **Fixed Paths**: You can optionally save a specific file or folder path in a shortcut to skip path prompt entirely.
- **Persistence**: Shortcuts are saved in `~/.convergent_shortcuts.json` and appear in "Your Shortcuts" section of main menu.

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

## Getting Started

### Prerequisites

-   **Python 3.8+** (3.10+ recommended)
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
Remove all compiled Python cache (`__pycache__`) directories across the project:
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

## Troubleshooting

- **Ghostscript not found**: Ensure `gs` is in your system PATH. Run `brew install ghostscript` to install or fix link.
- **ImageMagick policy error**: If PDF or HEIC processing fails, edit `/usr/local/etc/ImageMagick-7/policy.xml` to allow these formats (change `rights="none"` to `rights="read|write"` for relevant patterns).
- **Pandoc PDF fonts**: If converting documents to PDF fails, ensure you have a LaTeX distribution installed (e.g., `brew install --cask mactex` or `basictex`).
- **RAW Image Support**: On macOS, Sony `ARW` and Adobe `DNG` are supported natively via `sips`. On Linux, ensure `darktable` or `rawtherapee` is installed to provide the necessary delegates for ImageMagick.

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
│   ├── pdf_manip.py
│   └── video.py
└── customs/             # Shared utilities and helpers
    ├── check_deps.py
    ├── file_process.py
    ├── run_command.py
    └── shortcut.py
```

## Owner
**Kaiwen Du** - [GitHub](https://github.com/ItsKaiwenDu)

## License
Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.
