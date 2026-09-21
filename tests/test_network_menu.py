"""Run with: python3 -m unittest discover -s tests -p 'test_network_menu.py'."""

import configparser
import contextlib
import importlib.machinery
import importlib.util
import io
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET


REPOSITORY = Path(__file__).resolve().parents[1]
MENU_DIRECTORY = REPOSITORY / 'config' / 'networkmanager-dmenu'
ADAPTER = MENU_DIRECTORY / 'rofi'
loader = importlib.machinery.SourceFileLoader('wifi_rofi_adapter', str(ADAPTER))
spec = importlib.util.spec_from_loader(loader.name, loader)
adapter = importlib.util.module_from_spec(spec)
loader.exec_module(adapter)


class IconTests(unittest.TestCase):
    def test_bundled_format_produces_percentage_and_matching_icon(self):
        config = configparser.ConfigParser()
        config.read(MENU_DIRECTORY / 'config.ini')
        for signal, expected_icon in [(0, 'wifi-0'), (25, 'wifi-1'),
                                      (50, 'wifi-2'), (75, 'wifi-3'),
                                      (100, 'wifi-4')]:
            with self.subTest(signal=signal):
                row = config.get('dmenu', 'format').format(
                    name='Example Wi-Fi', sec='WPA2', signal=signal)
                self.assertEqual(row, f'Example Wi-Fi  ·  WPA2  ·  {signal}%')
                self.assertEqual(adapter.icon_for_row(row, 'Networks'), expected_icon)

    def test_all_mapped_icons_are_bundled_svg_files(self):
        names = set(adapter.ACTION_ICONS.values())
        names.update(adapter.PROFILE_ICONS.values())
        names.update(f'wifi-{level}' for level in range(5))
        names.update(('trash', 'cancel', 'network', 'saved'))
        namespace = '{http://www.w3.org/2000/svg}'
        for name in sorted(names):
            with self.subTest(icon=name):
                icon = MENU_DIRECTORY / 'icons' / f'{name}.svg'
                self.assertTrue(icon.is_file(), f'Missing bundled icon: {icon}')
                svg = ET.parse(icon).getroot()
                self.assertEqual(svg.tag, namespace + 'svg')
                viewbox = [float(value) for value in svg.attrib['viewBox'].split()]
                self.assertEqual(len(viewbox), 4)
                self.assertGreater(viewbox[2], 0)
                self.assertGreater(viewbox[3], 0)
                shapes = {'path', 'circle', 'ellipse', 'rect', 'line',
                          'polyline', 'polygon'}
                self.assertTrue(any(element.tag in {namespace + shape for shape in shapes}
                                    for element in svg.iter()),
                                f'Icon contains no drawable shapes: {icon}')

    def test_signal_boundaries(self):
        for strength, level in [(0, 0), (1, 1), (25, 1), (26, 2), (50, 2),
                                (51, 3), (75, 3), (76, 4), (100, 4), (999, 4)]:
            with self.subTest(strength=strength):
                self.assertEqual(adapter.icon_for_row(
                    f'My Network  ·  WPA2  ·  {strength}%', 'Networks'), f'wifi-{level}')

    def test_wifi_names_cannot_mimic_actions_or_profile_types(self):
        for name in ['Enable WiFi', 'Delete a Connection', 'Saved connections',
                     'office:VPN', 'home  ·  fake  ·  99%', 'Ää <&> "quotes"',
                     "-p Passphrase $(printf danger)"]:
            with self.subTest(name=name):
                row = f'{name}  ·  WPA2 WPA3  ·  25%'
                self.assertEqual(adapter.icon_for_row(row, 'Networks'), 'wifi-1')
                self.assertEqual(adapter.add_icons(row, 'Networks').split('\0')[0], row)

    def test_all_action_types(self):
        for row, icon in adapter.ACTION_ICONS.items():
            self.assertEqual(adapter.icon_for_row(row, 'Networks'), icon)
        self.assertEqual(adapter.icon_for_row('Saved connections', 'Networks'), 'saved')
        for kind, icon in adapter.PROFILE_ICONS.items():
            self.assertEqual(adapter.icon_for_row(f'profile:name:{kind}', 'Networks'), icon)
        self.assertEqual(adapter.icon_for_row('Future action', 'Networks'), 'network')

    def test_submenus_take_precedence_over_ambiguous_profile_names(self):
        names = ['Disable Networking', 'a:VPN', 'foo  ·  WPA2  ·  99%']
        for prompt, icon in [('CHOOSE ADAPTER:', 'wifi-4'),
                             ('CHOOSE CONNECTION:', 'saved'),
                             ('CHOOSE CONNECTION TO DELETE:', 'trash')]:
            for row in names:
                self.assertEqual(adapter.icon_for_row(row, prompt), icon)
        self.assertEqual(adapter.icon_for_row('Yes', "DELETE 'profile'?"), 'trash')
        self.assertEqual(adapter.icon_for_row('No', "DELETE 'profile'?"), 'cancel')

    def test_row_order_whitespace_and_existing_metadata(self):
        original = '  wifi  ·  --  ·  88%  \n\n \nSaved connections\nfoo\0icon\x1fold.svg\n'
        actual = adapter.add_icons(original, 'Networks')
        before, after = original.split('\n'), actual.split('\n')
        self.assertEqual(len(before), len(after))
        for source, decorated in zip(before, after):
            if '\0' in source or not source.strip():
                self.assertEqual(source, decorated)
            else:
                self.assertEqual(source, decorated.split('\0')[0])
                self.assertIn('\0icon\x1f', decorated)
        self.assertEqual(adapter.add_icons('', 'Passphrase'), '')

    def launch(self, args, text, selection, status):
        calls = []
        output = io.StringIO()
        def fake_rofi(command, **kwargs):
            calls.append((command, kwargs))
            # Rofi inherits stdout so the adapter never rewrites its selection.
            print(selection, end='')
            return subprocess.CompletedProcess(command, status)
        with patch.object(sys, 'argv', [str(ADAPTER), *args]), \
             patch.object(sys, 'stdin', io.StringIO(text)), \
             patch.object(adapter.subprocess, 'run', side_effect=fake_rofi), \
             contextlib.redirect_stdout(output):
            actual_status = adapter.main()
        self.assertEqual(actual_status, status)
        self.assertEqual(output.getvalue(), selection)
        return calls[0]

    def test_selection_active_indices_and_exit_codes(self):
        args = ['-theme', '/tmp/custom.rasi', '-dmenu', '-p', 'Networks ', '-a', '0,2']
        text = 'network  ·  WPA2  ·  75%\nSaved connections\nEnable WiFi'
        command, options = self.launch(args, text, 'network  ·  WPA2  ·  75%\n', 0)
        self.assertEqual(command[-len(args):], args)
        self.assertEqual(command[0], '/usr/bin/rofi')
        self.assertEqual(options['input'].count('\n'), text.count('\n'))
        self.assertNotIn('capture_output', options)
        self.launch(args, text, '', 1)
        self.launch(args, text, '', 2)

    def test_password_and_empty_input(self):
        args = ['-dmenu', '-p', 'Passphrase', '-password']
        command, options = self.launch(args, '', ' \'a<&> secret\n', 0)
        self.assertIn('-password', command)
        self.assertEqual(options['input'], '')
        self.assertIn('listview { enabled: false; }', command[-1])
        self.launch(['-dmenu', '-p', 'Networks '], '', '', 1)


class PackagingTests(unittest.TestCase):
    def test_installer_rewrites_launcher_for_paths_with_spaces_and_quotes(self):
        installer = (REPOSITORY / 'install.sh').read_text()
        command = 'python3 - "$HOME/.config/networkmanager-dmenu/config.ini"'
        match = re.search(re.escape(command) + r" <<'PY'\n(.*?)\nPY\n",
                          installer, re.DOTALL)
        self.assertIsNotNone(match, 'Could not find the installer launcher rewrite')
        with tempfile.TemporaryDirectory(prefix='network-menu-install-') as temporary:
            directory = Path(temporary) / "User's files $literal" / 'networkmanager-dmenu'
            directory.mkdir(parents=True)
            config_path = directory / 'config.ini'
            config_path.write_text((MENU_DIRECTORY / 'config.ini').read_text())
            subprocess.run([sys.executable, '-', str(config_path)],
                           input=match.group(1), text=True, check=True,
                           capture_output=True)
            config = configparser.ConfigParser()
            config.read(config_path)
            launcher = shlex.split(config.get('dmenu', 'dmenu_command'))
            self.assertEqual(launcher, [str(directory / 'rofi')])
            self.assertEqual(Path(launcher[0]).name, 'rofi')
            self.assertEqual(config.get('dmenu', 'format').format(
                name='Example', sec='WPA2', signal=75), 'Example  ·  WPA2  ·  75%')


if __name__ == '__main__':
    unittest.main(verbosity=2)
