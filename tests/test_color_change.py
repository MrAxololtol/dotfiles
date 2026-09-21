#!/usr/bin/env python3
"""Exercise palette publication with temporary XDG paths and mocked GUI reloads."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest


REPO = Path(__file__).resolve().parents[1]
GENERATOR = REPO / "local/bin/colorChange"
LAUNCHER = REPO / "config/polybar/launch.sh"

MOCK = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys
import time

name = Path(sys.argv[0]).name
record = {"command": name, "args": sys.argv[1:]}
with open(os.environ["COLOR_TEST_CALLS"], "a") as log:
    log.write(json.dumps(record) + "\n")
if name == "wal":
    time.sleep(float(os.environ.get("COLOR_TEST_DELAY", "0")))
    if os.environ.get("COLOR_TEST_WAL_SUCCESS") == "1":
        target = Path(os.environ["XDG_CACHE_HOME"]) / "wal/colors"
        target.parent.mkdir(parents=True, exist_ok=True)
        palette = ["#101010", "#cc2211"] + ["#888888"] * 14
        if os.environ.get("COLOR_TEST_INVALID_PALETTE") == "1":
            palette[0] = "#112233445566"
        target.write_text("\n".join(palette) + "\n")
        sys.exit(0)
    sys.exit(1)
if name == "pkill":
    # Every consumer must see complete files before the first reload signal.
    config = Path(os.environ["XDG_CONFIG_HOME"])
    assert (config / "polybar/colors.ini").read_text().endswith("\n")
    assert (config / "rofi/colors/generated.rasi").read_text().endswith("}\n")
    assert (Path(os.environ["XDG_CACHE_HOME"]) / "colorChange/last-wallpaper").is_file()
'''


class ColorChangeTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="color-change-test-")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.config = self.root / "config"
        self.cache = self.root / "cache"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.calls_file = self.root / "calls.jsonl"
        self.calls_file.touch()
        for name in ("wal", "pkill", "pgrep", "dunstctl", "polybar"):
            executable = self.bin / name
            executable.write_text(MOCK)
            executable.chmod(0o755)
        self.env = dict(os.environ)
        self.env.update(
            XDG_CONFIG_HOME=str(self.config),
            XDG_CACHE_HOME=str(self.cache),
            PATH=f"{self.bin}:{os.environ['PATH']}",
            COLOR_TEST_CALLS=str(self.calls_file),
        )
        self.env.pop("PYWAL_CACHE_DIR", None)
        self.red = self.wallpaper("red wallpaper.ppm", (0xEEEE, 0x2222, 0x1111))
        self.blue = self.wallpaper("blue wallpaper.ppm", (0x1111, 0x2222, 0xEEEE))

    def wallpaper(self, name, rgb):
        # A 16-bit fixture catches accidental truncation of ImageMagick hex RGB.
        target = self.root / name
        pixel = b"".join(channel.to_bytes(2, "big") for channel in rgb)
        target.write_bytes(b"P6\n8 8\n65535\n" + pixel * 64)
        return target

    def generate(self, wallpaper, **extra_env):
        return subprocess.run(
            [str(GENERATOR), str(wallpaper)],
            env=self.env | extra_env,
            text=True,
            capture_output=True,
            timeout=15,
        )

    def calls(self):
        return [json.loads(line) for line in self.calls_file.read_text().splitlines()]

    def require_imagemagick(self):
        if not (shutil.which("magick") or shutil.which("convert")):
            self.skipTest("ImageMagick is needed to exercise the fallback")

    def assert_red_theme(self):
        bar = (self.config / "polybar/colors.ini").read_text()
        rofi = (self.config / "rofi/colors/generated.rasi").read_text()
        self.assertIn(" bg = #230502\n", bar)
        self.assertIn(" fg = #f36458\n", bar)
        self.assertIn("active:         #f36458;", rofi)

    def test_failed_wal_ignores_stale_palette_and_uses_rgb8(self):
        self.require_imagemagick()
        stale = self.cache / "wal/colors"
        stale.parent.mkdir(parents=True)
        stale.write_text("#00ff00\n" * 16)
        result = self.generate(self.red)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_red_theme()
        saved = self.cache / "colorChange/last-wallpaper"
        self.assertEqual(saved.read_text().strip(), str(self.red))
        calls = self.calls()
        signals = [call["args"] for call in calls if call["command"] == "pkill"]
        self.assertIn(["-USR1", "-u", str(os.getuid()), "-x", "polybar"], signals)
        self.assertIn({"command": "dunstctl", "args": ["reload"]}, calls)
        self.assertFalse(any("dunst" in args for args in signals))
        self.assertEqual(len(list(self.config.rglob("*.??????"))), 0)

    def test_successful_wal_is_generation_only(self):
        result = self.generate(self.red, COLOR_TEST_WAL_SUCCESS="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        wal = next(call for call in self.calls() if call["command"] == "wal")
        for option in ("-n", "-s", "-t", "-e"):
            self.assertIn(option, wal["args"])
        bar = (self.config / "polybar/colors.ini").read_text()
        self.assertIn(" bg = #101010\n", bar)
        self.assertIn(" fg = #db6458\n", bar)

    def test_invalid_wal_palette_falls_back(self):
        self.require_imagemagick()
        result = self.generate(
            self.red, COLOR_TEST_WAL_SUCCESS="1", COLOR_TEST_INVALID_PALETTE="1"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_red_theme()

    def test_failed_extraction_preserves_working_theme_and_state(self):
        first = self.generate(self.red, COLOR_TEST_WAL_SUCCESS="1")
        self.assertEqual(first.returncode, 0, first.stderr)
        paths = list(self.config.rglob("*")) + [self.cache / "colorChange/last-wallpaper"]
        original = {path: path.read_bytes() for path in paths if path.is_file()}
        broken = self.root / "broken.png"
        broken.write_bytes(b"not an image")
        self.calls_file.write_text("")
        result = self.generate(broken)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("could not extract colours", result.stderr)
        self.assertEqual(original, {path: path.read_bytes() for path in original})
        self.assertEqual([call["command"] for call in self.calls()], ["wal"])

    def test_concurrent_updates_finish_with_one_complete_palette(self):
        self.require_imagemagick()
        first = subprocess.Popen(
            [str(GENERATOR), str(self.red)],
            env=self.env | {"COLOR_TEST_DELAY": "0.3"},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            deadline = time.monotonic() + 5
            while not self.calls_file.stat().st_size and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(self.calls_file.stat().st_size, "first generation did not start")
            second = self.generate(self.blue)
            _, error = first.communicate(timeout=15)
            self.assertEqual(first.returncode, 0, error)
            self.assertEqual(second.returncode, 0, second.stderr)
        finally:
            if first.poll() is None:
                first.kill()
                first.communicate()
        bar = (self.config / "polybar/colors.ini").read_text()
        rofi = (self.config / "rofi/colors/generated.rasi").read_text()
        self.assertIn(" bg = #020523\n", bar)
        self.assertIn(" fg = #5864f3\n", bar)
        self.assertIn("active:         #5864f3;", rofi)
        self.assertEqual(
            (self.cache / "colorChange/last-wallpaper").read_text().strip(), str(self.blue)
        )

    def test_launcher_reloads_existing_bar(self):
        # Populate the themes checked by the reload mock before invoking launch.sh.
        result = self.generate(self.red, COLOR_TEST_WAL_SUCCESS="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.calls_file.write_text("")
        launch = subprocess.run([str(LAUNCHER)], env=self.env, capture_output=True, timeout=5)
        self.assertEqual(launch.returncode, 0, launch.stderr)
        calls = self.calls()
        self.assertEqual([call["command"] for call in calls], ["pgrep", "pkill"])
        self.assertEqual(calls[-1]["args"], ["-USR1", "-u", str(os.getuid()), "-x", "polybar"])


if __name__ == "__main__":
    unittest.main()
