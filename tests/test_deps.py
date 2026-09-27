import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from customs.check_deps import (
    get_command_output,
    get_imagemagick_version,
    get_libreoffice_version,
    get_whisper_version,
)


class TestCheckDeps(unittest.TestCase):
    def test_get_imagemagick_version_parsing(self):
        sample_output = "Version: ImageMagick 7.1.1-29 Q16-HDRI x86_64 https://imagemagick.org"
        with patch("customs.check_deps.get_command_output", return_value=sample_output):
            ver = get_imagemagick_version()
            self.assertEqual(ver, "7.1.1-29")

        # Fallback when output has no version pattern
        with patch("customs.check_deps.get_command_output", return_value="ImageMagick installed"):
            ver = get_imagemagick_version()
            self.assertEqual(ver, "Found")

        # Not found
        with patch("customs.check_deps.get_command_output", return_value=None):
            ver = get_imagemagick_version()
            self.assertIsNone(ver)

    def test_get_libreoffice_version_parsing(self):
        sample_output = "LibreOffice 24.2.0.3 420(Build:3)"
        with patch("shutil.which", return_value="/usr/bin/soffice"):
            with patch("customs.check_deps.get_command_output", return_value=sample_output):
                ver = get_libreoffice_version()
                self.assertEqual(ver, "24.2.0.3")

    def test_get_whisper_version(self):
        with patch("shutil.which", side_effect=lambda x: "/usr/local/bin/whisper-cli" if x == "whisper-cli" else None):
            ver = get_whisper_version()
            self.assertEqual(ver, "Found")


    def test_installed_tools_do_not_prompt_or_install(self):
        from customs.check_deps import ensure_dependencies
        with patch("customs.check_deps.dependency_available", return_value=True), \
             patch("customs.check_deps.get_char") as prompt, \
             patch("customs.check_deps.subprocess.run") as run:
            self.assertTrue(ensure_dependencies(["ffmpeg"], interactive=True))
        prompt.assert_not_called()
        run.assert_not_called()

    def test_noninteractive_missing_tool_is_actionable(self):
        from customs.check_deps import ensure_dependencies, MissingDependencyError
        with patch("customs.check_deps.dependency_available", return_value=False), \
             patch("customs.check_deps.get_char") as prompt, \
             patch("customs.check_deps.subprocess.run") as run:
            with self.assertRaisesRegex(MissingDependencyError, "--install ffmpeg"):
                ensure_dependencies(["ffmpeg"])
        prompt.assert_not_called()
        run.assert_not_called()

    def test_declining_installation_does_not_run_installer(self):
        from customs.check_deps import ensure_dependencies
        with patch("customs.check_deps.dependency_available", return_value=False), \
             patch("customs.check_deps.sys.stdin.isatty", return_value=True), \
             patch("customs.check_deps.install_command", return_value=["brew", "install", "ffmpeg"]), \
             patch("customs.check_deps.get_char", return_value="n"), \
             patch("customs.check_deps.subprocess.run") as run:
            self.assertFalse(ensure_dependencies(["ffmpeg"], interactive=True))
        run.assert_not_called()

    def test_opt_in_install_is_deduplicated_verified_and_noninteractive(self):
        from customs.check_deps import ensure_dependencies
        from unittest.mock import MagicMock
        import subprocess
        with patch("customs.check_deps.dependency_available", side_effect=[False, True]) as probe, \
             patch("customs.check_deps.install_command", return_value=["brew", "install", "ffmpeg"]), \
             patch("customs.check_deps.get_char") as prompt, \
             patch("customs.check_deps.subprocess.run", return_value=MagicMock(returncode=0)) as run:
            self.assertTrue(ensure_dependencies(["ffmpeg", "ffmpeg"], install=True))
        self.assertEqual(probe.call_count, 2)
        prompt.assert_not_called()
        run.assert_called_once()
        self.assertEqual(run.call_args.kwargs["stdin"], subprocess.DEVNULL)
        self.assertIs(run.call_args.kwargs["stdout"], sys.stderr)

    def test_failed_install_never_reports_ready(self):
        from customs.check_deps import ensure_dependencies, MissingDependencyError
        from unittest.mock import MagicMock
        with patch("customs.check_deps.dependency_available", return_value=False), \
             patch("customs.check_deps.install_command", return_value=["brew", "install", "ffmpeg"]), \
             patch("customs.check_deps.subprocess.run", return_value=MagicMock(returncode=1)):
            with self.assertRaisesRegex(MissingDependencyError, "Could not install"):
                ensure_dependencies(["ffmpeg"], install=True)

    def test_conversion_dependencies_follow_selected_operation(self):
        from Convergent import Converter
        conv = Converter()
        with patch("Convergent.ensure_dependencies", return_value=True) as ensure, \
             patch("modules.image.shutil.which", return_value=None):
            conv.prepare_conversion(["PNG"], "PDF")
            self.assertEqual(ensure.call_args.args[0], ["imagemagick"])
            conv.prepare_conversion(["MP4"], "MP3")
            self.assertEqual(ensure.call_args.args[0], ["ffmpeg"])
            conv.prepare_conversion(["MD"], "PDF")
            self.assertEqual(ensure.call_args.args[0], ["pandoc", "typst"])

    def test_native_image_conversion_needs_no_installation(self):
        from modules.image import required_dependencies
        with patch("modules.image.sys.platform", "darwin"), \
             patch("modules.image.shutil.which", return_value="/usr/bin/sips"):
            self.assertEqual(required_dependencies("PNG", "JPG"), [])
            self.assertEqual(required_dependencies("PNG", "PDF"), [])
            self.assertEqual(required_dependencies("PNG", "JPG", strip_metadata=True), ["imagemagick"])

    def test_missing_model_never_downloads_without_consent(self):
        from modules.stt import prepare_model
        from customs.check_deps import MissingDependencyError
        with patch("modules.stt.get_model_path", side_effect=FileNotFoundError) as model:
            with self.assertRaisesRegex(MissingDependencyError, "--install-deps"):
                prepare_model("tiny")
        model.assert_called_once_with("tiny", auto_download=False)

    def test_first_use_model_download_runs_before_conversion(self):
        from modules.stt import prepare_model
        with patch("modules.stt.get_model_path", side_effect=[FileNotFoundError(), Path("model.bin")]) as model:
            self.assertTrue(prepare_model("tiny", install=True))
        self.assertEqual([c.kwargs["auto_download"] for c in model.call_args_list], [False, True])


    def test_unattended_linux_install_never_requests_sudo_password(self):
        from customs.check_deps import install_command
        with patch("customs.check_deps.sys.platform", "linux"), \
             patch("customs.check_deps.os.geteuid", return_value=1000), \
             patch("customs.check_deps.shutil.which", side_effect=lambda name: "/usr/bin/apt" if name == "apt" else None):
            self.assertEqual(install_command("ffmpeg"), ["sudo", "-n", "/usr/bin/apt", "install", "-y", "ffmpeg"])
            self.assertIsNone(install_command("whisper"))

    def test_missing_tools_do_not_block_dependency_status(self):
        from customs.check_deps import check_dependencies
        with patch("customs.check_deps.dependency_available", return_value=False):
            check_dependencies()


if __name__ == "__main__":
    unittest.main()
