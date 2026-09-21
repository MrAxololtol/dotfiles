#!/usr/bin/env python3
"""Isolated checks for the wallpaper cycler: temp HOME/WALL_DIR, stubbed helpers."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
CYCLER = REPOSITORY / "local/bin/wallpaper-cycle"
NAMES = ["a-red.jpg", "b-blue.png", "c-green.jpg"]


class WallpaperCycleTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="wallpaper-cycle-test-"))
        self.home = self.work / "home"
        self.walls = self.work / "wallpapers"
        self.walls.mkdir(parents=True)
        for name in NAMES:
            (self.walls / name).write_bytes(b"fake")

        self.bin = self.work / "bin"
        self.bin.mkdir()
        shutil.copy2(CYCLER, self.bin / "wallpaper-cycle")
        self.log = self.work / "calls.log"
        set_stub = self.bin / "set-wallpaper"
        set_stub.write_text(
            "#!/bin/sh\n"
            "printf 'set-wallpaper %s\\n' \"$1\" >> \"$CYCLE_LOG\"\n"
            "mkdir -p \"$XDG_CACHE_HOME/colorChange\"\n"
            "printf '%s\\n' \"$1\" > \"$XDG_CACHE_HOME/colorChange/last-wallpaper\"\n"
        )
        theme_stub = self.bin / "theme-cycle"
        theme_stub.write_text(
            "#!/bin/sh\n"
            "printf 'theme-cycle %s\\n' \"$*\" >> \"$CYCLE_LOG\"\n"
        )
        notify_stub = self.bin / "dunstify"
        notify_stub.write_text(
            "#!/bin/sh\nprintf 'notify %s\\n' \"$*\" >> \"$CYCLE_LOG\"\n"
        )
        for path in (set_stub, theme_stub, notify_stub):
            path.chmod(0o755)

        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "WALL_DIR": str(self.walls),
            "XDG_STATE_HOME": str(self.work / "state"),
            "XDG_CACHE_HOME": str(self.work / "cache"),
            "XDG_DATA_HOME": str(self.work / "data"),
            "CYCLE_LOG": str(self.log),
            "PATH": f"{self.bin}:{os.environ['PATH']}",
        }
        self.state = self.work / "state/wallpaper-cycle/current"

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def run_cycle(self):
        return subprocess.run([str(self.bin / "wallpaper-cycle")], env=self.env,
                              capture_output=True, text=True)

    def selected(self):
        return [line.split(" ", 1)[1] for line in self.log.read_text().splitlines()
                if line.startswith("set-wallpaper ")]

    def test_first_cycle_applies_first_wallpaper_and_resets_rofi_to_auto(self):
        result = self.run_cycle()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.selected(), [str(self.walls / NAMES[0])])
        log = self.log.read_text()
        self.assertIn("theme-cycle --set auto", log)
        self.assertIn("notify", log)

    def test_cycles_in_order_and_wraps_around(self):
        for _ in range(len(NAMES) + 1):
            self.run_cycle()
        self.assertEqual([Path(p).name for p in self.selected()],
                         NAMES + [NAMES[0]])

    def test_continues_from_an_externally_set_wallpaper(self):
        cache = self.work / "cache/colorChange"
        cache.mkdir(parents=True)
        (cache / "last-wallpaper").write_text(str(self.walls / NAMES[1]) + "\n")
        self.run_cycle()
        self.assertEqual(Path(self.selected()[-1]).name, NAMES[2])

    def test_state_is_persisted_and_hotkey_uses_the_cycler(self):
        self.run_cycle()
        self.assertEqual(self.state.read_text().strip(), str(self.walls / NAMES[0]))
        sxhkd = (REPOSITORY / "config/sxhkd/sxhkdrc").read_text()
        self.assertIn('super + r\n    "$HOME/.local/bin/wallpaper-cycle"', sxhkd)


if __name__ == "__main__":
    unittest.main(verbosity=2)
