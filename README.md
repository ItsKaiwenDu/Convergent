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
    -   **Videos**: MOV/MP4 to MP3, GIF (with customizable FPS), or alternative containers (AVI, MOV, MP4).
    -   **Audio**: WAV and M4A to MP3.
    -   **Documents**: DOCX and PPTX to PDF (via Pandoc).
-   **CLI First**: Support for direct command-line arguments for automation and power users.
-   **Robust Path Recognition**: Automatically handles shell-escaped paths (from drag-and-drop) and messy copy-pastes with hidden newlines.
-   **Rich UI**: Powered by the `rich` library for beautiful terminal output and progress tracking.

## Tech Stack

| Layer | Technology |
|---|---|
| **Language** | [Python 3](https://www.python.org/) |
| **CLI Framework** | `argparse` + `tty` |
| **UI/Styling** | [Rich](https://github.com/Textualize/rich) |
| **Processing Engine** | [FFmpeg](https://ffmpeg.org/) (Audio/Video) |
| **Image Engine** | [ImageMagick](https://imagemagick.org/) |
| **PDF Engine** | [Ghostscript](https://ghostscript.com/) |
| **Document Engine** | [Pandoc](https://pandoc.org/) |

## Getting Started

### Prerequisites

-   **Python 3.8+**
-   **Homebrew** (recommended for macOS system dependencies)

### Installation

1.  **Clone or Download**: Ensure `Convergent.py` and `Makefile` are in the same directory.
2.  **Run Setup**:
    ```bash
    make setup
    ```
    *This will install the `rich` Python library and attempt to install `ffmpeg`, `imagemagick`, `ghostscript`, and `pandoc` via Homebrew.*

## Usage

### Interactive Mode
Simply run the following command and follow the on-screen prompts:
```bash
make start
```

### CLI Mode (Arguments)
For automated workflows, you can pass arguments directly using the `ARGS` variable:
```bash
# Convert HEIC images to JPG using 4 parallel jobs
make start ARGS="--from HEIC --to JPG --path ~/Desktop/Photos --jobs 4"

# Convert Video to GIF with 30 FPS
make start ARGS="--from MP4 --to GIF --fps 30 --path ./video.mp4"
```

## Owner
**Kaiwen Du** - [GitHub](https://github.com/ItsKaiwenDu)

## License
Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.
