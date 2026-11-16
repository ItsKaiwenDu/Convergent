# Example Usage

Common workflows using the interactive `Makefile` menu or direct CLI flags.

## User Makefile Examples

| Goal | Step-by-Step Commands |
| :--- | :--- |
| **Convert a file or folder (e.g., JPG → PDF)** | 1. Run `make start`.<br>2. Choose **Convert** and select your source/target format.<br>3. Drag & drop or type the file/folder path. |
| **Resize or change video FPS (e.g., MP4 60 FPS → MP4 30 FPS)** | 1. Run `make start`.<br>2. Choose **Resize**.<br>3. Enter the video path and set the target resolution or FPS. |
| **Combine or split PDFs, videos, or audio** | 1. Run `make start`.<br>2. Choose **Combine** or **Split** and follow the prompts. |
| **Extract text (OCR) or transcribe audio (STT)** | 1. Run `make start`.<br>2. Choose **OCR** (images/PDFs) or **Speech-to-Text** (audio/video). |
| **Compress or decompress archives** | 1. Run `make start`.<br>2. Choose **Compress** or **Decompress** and provide the path. |
| **Check tools, cache, or run tests** | Run `make check` (dependencies), `make cache` (disk usage), or `make test` (test suite). |

## CLI Mode Examples

| Goal | Command |
| :--- | :--- |
| **JPG → PDF** | `make start ARGS="--from JPG --to PDF --path photo.jpg"` |
| **MOV → MP4 (with hardware acceleration)** | `make start ARGS="--from MOV --to MP4 --path clip.mov --hwaccel auto"` |
| **MOV → GIF at 30 FPS** | `make start ARGS="--from MOV --to GIF --fps 30 --path clip.mov"` |
| **WAV → MP3 at 320 kbps** | `make start ARGS="--from WAV --to MP3 --bitrate 320k --path audio.wav"` |
| **PDF → PNG at 300 DPI** | `make start ARGS="--from PDF --to PNG --dpi 300 --path document.pdf"` |
| **Markdown → Formatted PDF** | `make start ARGS="--from MD --to PDF --md-pdf-mode formatted --path notes.md"` |
| **Batch convert folder (strip EXIF & overwrite)** | `make start ARGS="--from HEIC --to JPG --path ./photos --strip-metadata --overwrite -j 4"` |
| **Speech-to-Text (Video/Audio → TXT)** | `make start ARGS="--stt --model base --language en --path lecture.mp4"` |
| **Run a saved shortcut** | `make start ARGS="--shortcut 1 --path ./input"` |
| **Start local MCP server** | `make mcp` |
