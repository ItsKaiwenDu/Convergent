![Banner](Banner.png)

# Convergent: Local File Converter Utility

> **Convergent** is a professional, high-performance CLI utility designed for batch file conversion. 
> It leverages the power of FFmpeg and ImageMagick to provide seamless transformations between images, videos, and documents with a premium command-line experience.

## Features

-   **Interactive Menu**: A user-friendly, arrow-key driven interface for quick conversions.
-   **Batch Processing**: Convert entire directories of files in one command.
-   **Multi-Format Support**:
    -   **Images**: HEIC to JPG/PNG, JPG to PNG/WEBP/PDF, etc.
    -   **Videos**: MOV/MP4 to MP3, GIF, or alternative video containers.
    -   **Documents**: DOCX and PPTX to PDF (via Pandoc).
-   **CLI First**: Support for direct command-line arguments for automation and power users.
-   **Rich UI**: Powered by the `rich` library for beautiful terminal output and progress tracking.

## Tech Stack

| Layer | Technology |
|---|---|
| **Language** | [Python 3](https://www.python.org/) |
| **CLI Framework** | `argparse` + `tty` |
| **UI/Styling** | [Rich](https://github.com/Textualize/rich) |
| **Processing Engine** | [FFmpeg](https://ffmpeg.org/) (Audio/Video) |
| **Image Engine** | [ImageMagick](https://imagemagick.org/) |
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
    *This will install the `rich` Python library and attempt to install `ffmpeg`, `imagemagick`, and `pandoc` via Homebrew.*

## Usage

### Interactive Mode
Simply run the following command and follow the on-screen prompts:
```bash
make start
```

### CLI Mode (Arguments)
For automated workflows, you can pass arguments directly using the `ARGS` variable:
```bash
make start ARGS="--from HEIC --to JPG --path ~/Desktop/Photos"
```

## Owner
**Kaiwen Du** - [GitHub](https://github.com/ItsKaiwenDu)

## License
Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.
