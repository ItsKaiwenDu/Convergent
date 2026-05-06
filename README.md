![Banner](Banner.png)

# Convergent: Local File Converter Utility

> **Convergent** is a professional, high-performance CLI utility designed for batch file conversion. 
> It leverages the power of FFmpeg and ImageMagick to provide seamless transformations between images, videos, and documents with a premium command-line experience.

## Features

-   **Interactive Menu**: A streamlined numeric interface with category-based source auto-detection for faster workflows.
-   **Parallel Processing**: High-speed batch conversions using multi-core execution (configurable via `--jobs`).
-   **Batch Processing**: Convert entire directories of files in one command.
-   **Multi-Format Support**:
    -   **PDF Combiner & Splitter**: Merge multiple PDFs or split a single PDF into individual pages, custom ranges, or a specific number of equal parts.
    -   **Images**: HEIC to JPG/PNG, JPG/PNG to WEBP/PDF, and cross-conversion between JPG/PNG.
    -   **Videos**: MOV/MP4 to MP3, WEBM, GIF (with customizable FPS), or alternative containers (**AVI**, **MOV**, **MP4**).
    -   **Audio**: WAV and M4A to **MP3**, **M4A**, or **WAV**.
    -   **Documents**: DOCX, PPTX, and RTF to PDF (via Pandoc).
    -   **Archives**: Compress files and folders into **ZIP**, **TAR.GZ**, **7z**, or **RAR** archives (with optional password protection for supported formats). Decompress existing archives to a target directory.
-   **CLI First**: Support for direct command-line arguments for automation and power users.
-   **Robust Path Recognition**: Automatically handles shell-escaped paths (from drag-and-drop) and messy copy-pastes with hidden newlines.
-   **Quick Shortcuts**: Create and save persistent conversion workflows to trigger them with a single keystroke. Optionally fix a target path to skip prompts entirely.
-   **Overwrite Guard**: Protects against accidental data loss by prompting before overwriting existing files. Includes `--overwrite` and `--skip` flags for automated control.
-   **Rich UI**: Powered by the `rich` library for beautiful terminal output and progress tracking.

## Quick Shortcuts

Convergent allows you to save your most frequent workflows as shortcuts for instant access.

- **Create**: Press **A** in the main menu to define a new shortcut with a custom symbol (key) and label title.
- **Remove**: Press **R** in the main menu to delete existing shortcuts.
- **Example**: Create a shortcut `S` for `HEIC to JPG` to batch convert photos with one key.
- **Fixed Paths**: You can optionally save a specific file or folder path in a shortcut to skip the path prompt entirely.
- **Persistence**: Shortcuts are saved in `~/.convergent_shortcuts.json` and appear in the "Your Shortcuts" section of the main menu.

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
> **Compatibility**: This utility is **macOS-first**. Linux is supported but requires manual dependency installation. Windows is **not supported** due to the `tty` terminal dependency.

## Getting Started

### Prerequisites

-   **Python 3.8+** (3.10+ recommended)
-   **Homebrew** (recommended for macOS system dependencies)

### Installation

1.  **Clone or Download**: Ensure `Convergent.py` and `Makefile` are in the same directory.
2.  **Run Setup**:
    ```bash
    make setup
    ```
    *This will install the `rich` Python library and attempt to install `ffmpeg`, `imagemagick`, `ghostscript`, and `pandoc` via Homebrew.*
3.  **Check Dependencies**:
    ```bash
    make check
    ```
    *This will probe your system for all required external tools and ensure they are ready to use.*

## Usage

### Interactive Mode
Simply run the following command and follow the on-screen prompts:
```bash
make start
```

### CLI Mode (Arguments)
For automated workflows, you can pass arguments directly using the `ARGS` variable.

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

- **Ghostscript not found**: Ensure `gs` is in your system PATH. Run `brew install ghostscript` to install or fix the link.
- **ImageMagick policy error**: If PDF or HEIC processing fails, edit `/usr/local/etc/ImageMagick-7/policy.xml` to allow these formats (change `rights="none"` to `rights="read|write"` for the relevant patterns).
- **Pandoc PDF fonts**: If converting documents to PDF fails, ensure you have a LaTeX distribution installed (e.g., `brew install --cask mactex` or `basictex`).

## Owner
**Kaiwen Du** - [GitHub](https://github.com/ItsKaiwenDu)

## License
Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.
