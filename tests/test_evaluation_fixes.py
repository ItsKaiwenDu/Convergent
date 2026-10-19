import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import importlib.util
if importlib.util.find_spec("mcp") is None:
    raise unittest.SkipTest("Optional MCP SDK is not installed; run make setup-mcp")

from customs.run_command import run_command, run_command_output
from mcp_server.server import (
    perform_stt,
    perform_ocr,
    extract_audio,
    pdf_to_images,
    combine_files,
    resize_media,
)
import modules.audio as audio_mod
import modules.video as video_mod
import modules.resize as resize_mod
import modules.stt as stt_mod


class TestEvaluationFixes(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_f01_stt_markdown_fails_when_no_transcript_produced(self):
        """F01: Ensure convert_audio_to_text with MD target fails when Whisper produces no output."""
        dummy_wav = self.dir_path / "speech.wav"
        dummy_wav.write_bytes(b"RIFF" + b"\x00" * 36)

        with patch("modules.stt.find_whisper_binary", return_value="/usr/local/bin/whisper-cli"), \
             patch("modules.stt.extract_audio_for_stt", return_value=dummy_wav), \
             patch("modules.stt.get_model_path", return_value=self.dir_path / "model.bin"), \
             patch("modules.stt.run_command", return_value=(True, "")):
            # Whisper returns success exit code 0 but does not create the .txt file
            ok, err = stt_mod.convert_audio_to_text(dummy_wav, target_ext="MD", model="base")
            self.assertFalse(ok)
            self.assertIn("Whisper failed to produce MD output", err)

    def test_f02_run_command_tolerates_non_utf8_output(self):
        """F02: Ensure run_command doesn't crash on non-UTF8/UTF-16 output bytes."""
        cmd = [sys.executable, "-c", "import sys; sys.stderr.buffer.write(b'\\xfe\\xff\\x00H\\x00i'); sys.exit(0)"]
        ok, err = run_command(cmd)
        self.assertTrue(ok)

        code, out, stderr = run_command_output(cmd)
        self.assertEqual(code, 0)
        self.assertIn("\ufffd", stderr)

    def test_f04_rich_markup_escape_in_file_process(self):
        """F04: Ensure bracketed error text (like font paths) does not crash file_process console logging."""
        from rich.markup import escape, MarkupError
        from rich.console import Console
        from io import StringIO

        bracketed_error = "closing tag '[/System/Library/Fonts/Supplemental/Courier New Bold.ttf]' doesn't match"
        console = Console(file=StringIO())

        # Unescaped string raises MarkupError
        with self.assertRaises(MarkupError):
            console.print(f"[dim]{bracketed_error}[/dim]")

        # Escaped string prints successfully without MarkupError
        escaped = escape(bracketed_error)
        try:
            console.print(f"[dim]{escaped}[/dim]")
        except MarkupError:
            self.fail("console.print raised MarkupError on escaped bracketed string!")

    def test_f05_combine_files_allows_existing_directory_target(self):
        """F05: combine_files should allow an existing directory as output_path when destination combined file does not exist."""
        p1 = self.dir_path / "doc1.pdf"
        p2 = self.dir_path / "doc2.pdf"
        p1.touch()
        p2.touch()

        out_dir = self.dir_path / "my_output_dir"
        out_dir.mkdir()

        with patch("mcp_server.server.conv.combine_pdfs", return_value=out_dir / "combined.pdf"):
            res = combine_files(file_paths=[str(p1), str(p2)], output_path=str(out_dir), overwrite=False)
            self.assertTrue(res.get("success"), msg=res.get("error"))
            self.assertEqual(res.get("output_file"), str(out_dir / "combined.pdf"))

    def test_f05_convenience_tools_accept_and_forward_overwrite(self):
        """F05: Convenience tools must accept overwrite parameter and forward it to convergent_convert."""
        f = self.dir_path / "input.png"
        f.touch()

        with patch("mcp_server.server.convergent_convert", return_value={"success": True, "converted_files": []}) as mock_conv:
            perform_ocr(input_path=str(f), overwrite=False)
            self.assertFalse(mock_conv.call_args[1]["overwrite"])

            perform_stt(input_path=str(self.dir_path / "audio.mp3"), overwrite=False)
            self.assertFalse(mock_conv.call_args[1]["overwrite"])

            extract_audio(video_path=str(self.dir_path / "video.mp4"), overwrite=False)
            self.assertFalse(mock_conv.call_args[1]["overwrite"])

            pdf_to_images(pdf_path=str(self.dir_path / "doc.pdf"), overwrite=False)
            self.assertFalse(mock_conv.call_args[1]["overwrite"])

    def test_f06_audio_bitrate_applied_to_m4a_ogg_aac(self):
        """F06: convert_audio and video audio extraction apply bitrate to M4A, OGG, and AAC."""
        src_wav = self.dir_path / "test.wav"
        src_wav.touch()

        with patch("modules.audio.run_command", return_value=(True, "")) as mock_cmd:
            audio_mod.convert_audio(src_wav, "M4A", bitrate="320k")
            cmd = mock_cmd.call_args[0][0]
            self.assertIn("-b:a", cmd)
            self.assertIn("320k", cmd)

            audio_mod.convert_audio(src_wav, "OGG", bitrate="128k")
            cmd = mock_cmd.call_args[0][0]
            self.assertIn("-b:a", cmd)
            self.assertIn("128k", cmd)

            audio_mod.convert_audio(src_wav, "AAC", bitrate="256k")
            cmd = mock_cmd.call_args[0][0]
            self.assertIn("-b:a", cmd)
            self.assertIn("256k", cmd)

        src_mp4 = self.dir_path / "test.mp4"
        src_mp4.touch()
        with patch("modules.video.run_command", return_value=(True, "")) as mock_video_cmd:
            video_mod.convert_video(src_mp4, "M4A", bitrate="192k")
            cmd = mock_video_cmd.call_args[0][0]
            self.assertIn("-b:a", cmd)
            self.assertIn("192k", cmd)

            video_mod.convert_video(src_mp4, "OGG", bitrate="128k")
            cmd = mock_video_cmd.call_args[0][0]
            self.assertIn("-b:a", cmd)
            self.assertIn("128k", cmd)

    def test_f07_stt_model_alias_normalization_and_input_validation(self):
        """F07: perform_stt resolves canonical model names and rejects unsupported inputs like opus."""
        dummy_audio = self.dir_path / "audio.mp3"
        dummy_audio.touch()

        with patch("mcp_server.server.convergent_convert", return_value={"success": True, "converted_files": []}):
            res_medium = perform_stt(input_path=str(dummy_audio), model="medium")
            self.assertEqual(res_medium.get("model_used"), "small")
            self.assertEqual(res_medium.get("model_requested"), "medium")

            res_turbo = perform_stt(input_path=str(dummy_audio), model="large-v3")
            self.assertEqual(res_turbo.get("model_used"), "turbo")
            self.assertEqual(res_turbo.get("model_requested"), "large-v3")

        dummy_opus = self.dir_path / "test.opus"
        dummy_opus.touch()
        res_opus = perform_stt(input_path=str(dummy_opus))
        self.assertFalse(res_opus.get("success"))
        self.assertIn("Invalid input format '.opus'", res_opus.get("error"))

    def test_f08_resize_media_surfaces_missing_magick_and_ffprobe(self):
        """F08: resize_media surfaces explicit missing dependency errors when magick or ffprobe is not in PATH."""
        dummy_img = self.dir_path / "test.png"
        dummy_img.touch()

        with patch("shutil.which", return_value=None):
            res_img = resize_media(file_path=str(dummy_img), width=200)
            self.assertFalse(res_img.get("success"))
            self.assertIn("ImageMagick ('magick') is not installed", res_img.get("error"))

            dummy_video = self.dir_path / "test.mp4"
            dummy_video.touch()
            res_vid = resize_media(file_path=str(dummy_video), width=200)
            self.assertFalse(res_vid.get("success"))
            self.assertIn("FFmpeg ('ffprobe') is not installed", res_vid.get("error"))


if __name__ == "__main__":
    unittest.main()
