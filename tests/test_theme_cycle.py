#!/usr/bin/env python3
"""Isolated checks for the rofi theme cycler: temporary HOME, stubbed notifications."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
CYCLER = REPOSITORY / "local/bin/theme-cycle"
AUTO = "auto"
THEMES = ["doric-fire.rasi", "ef-trio-dark.rasi", "vivendi.rasi"]


class ThemeCycleTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="theme-cycle-test-"))
        self.home = self.work / "home"
        self.colors = self.home / ".config/rofi/colors"
        self.colors.mkdir(parents=True)
        (self.colors / "generated.rasi").write_text("* { background: #000000; }\n")
        for name in THEMES:
            (self.colors / name).write_text("* { background: #111111; }\n")

        self.bin = self.work / "bin"
        self.bin.mkdir()
        self.notify_log = self.work / "notify.log"
        stub = '#!/bin/sh\nprintf "%s\\n" "$*" >> "$NOTIFY_LOG"\n'
        for name in ("dunstify", "notify-send"):
            path = self.bin / name
            path.write_text(stub)
            path.chmod(0o755)

        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "XDG_STATE_HOME": str(self.work / "state"),
            "XDG_DATA_HOME": str(self.work / "data"),
            "NOTIFY_LOG": str(self.notify_log),
            "PATH": f"{self.bin}:{os.environ['PATH']}",
        }
        self.state = self.work / "state/rofi-theme/current"
        self.active = self.work / "data/rofi-themes/active.rasi"

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def run_cycle(self, *args):
        return subprocess.run([str(CYCLER), *args], env=self.env,
                              capture_output=True, text=True)

    def state_name(self):
        return self.state.read_text().strip()

    def test_first_cycle_selects_first_theme_and_notifies(self):
        result = self.run_cycle()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state_name(), THEMES[0])
        self.assertEqual(os.readlink(self.active), str(self.colors / THEMES[0]))
        self.assertIn("Rofi theme", self.notify_log.read_text())

    def test_cycles_all_themes_and_wraps_back_to_auto(self):
        for expected in THEMES:
            self.run_cycle()
            self.assertEqual(self.state_name(), expected)
        self.run_cycle()
        self.assertEqual(self.state_name(), AUTO)
        self.assertEqual(os.readlink(self.active), str(self.colors / "generated.rasi"))

    def test_selection_persists_and_ensure_restores_symlink(self):
        self.run_cycle()
        self.run_cycle()
        selected = self.state_name()
        self.active.unlink()
        self.run_cycle("--ensure")
        self.assertEqual(self.state_name(), selected)
        self.assertEqual(os.readlink(self.active), str(self.colors / selected))

    def test_ensure_resets_a_removed_theme_to_auto(self):
        self.run_cycle("--set", "vivendi.rasi")
        (self.colors / "vivendi.rasi").unlink()
        self.run_cycle("--ensure")
        self.assertEqual(self.state_name(), AUTO)
        self.assertEqual(os.readlink(self.active), str(self.colors / "generated.rasi"))

    def test_list_and_set(self):
        listing = self.run_cycle("--list").stdout.split()
        self.assertEqual(listing, [AUTO] + THEMES)
        self.run_cycle("--set", "ef-trio-dark.rasi")
        self.assertEqual(self.state_name(), "ef-trio-dark.rasi")

    def test_wallpaper_change_does_not_override_theme(self):
        source = (REPOSITORY / "local/bin/colorChange").read_text()
        self.assertNotIn('>> "$CONFIG_DIR/rofi/config.rasi"', source)

    def test_configs_use_the_active_theme(self):
        for relative in ("config/rofi/config.rasi", "config/rofi/applaunch/config.rasi"):
            self.assertIn("~/.local/share/rofi-themes/active.rasi",
                          (REPOSITORY / relative).read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
