#!/usr/bin/env python3
"""Capture only an isolated synthetic Rofi menu; never enumerate real networks."""
from pathlib import Path
import argparse
import os
import re
import signal
import subprocess
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('output', type=Path)
args = parser.parse_args()
output = args.output.resolve()
output.parent.mkdir(parents=True, exist_ok=True)
adapter = Path.home() / '.config/networkmanager-dmenu/rofi'
rows = [
    'Home Wi-Fi  ·  WPA2  ·  96%',
    'Studio  ·  WPA2  ·  64%',
    'Guest Wi-Fi  ·  WPA2  ·  22%',
    'Disable WiFi',
    'Enable Bluetooth',
    'Rescan WiFi Networks',
    'Saved connections',
    'Office VPN:VPN',
    'Launch Connection Manager',
]
# An opaque rectangular outer window ensures no desktop pixels appear in corners.
process = subprocess.Popen(
    [str(adapter), '-dmenu', '-i', '-p', 'Networks', '-a', '0', '-no-auto-select',
     '-theme-str', 'window { border-radius: 0px; background-color: @background; }'],
    stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    text=True, start_new_session=True,
)
try:
    process.stdin.write('\n'.join(rows) + '\n')
    process.stdin.close()
    deadline = time.monotonic() + 8
    window_id = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError('Preview closed before capture: ' + process.stderr.read())
        tree = subprocess.run(['xwininfo', '-root', '-tree'], check=True,
                              capture_output=True, text=True).stdout
        for line in tree.splitlines():
            if 'rofi' not in line.lower():
                continue
            match = re.match(r'\s*(0x[0-9a-fA-F]+)\s', line)
            if not match:
                continue
            # Require the window to belong to this preview's process group.
            pid_info = subprocess.run(['xprop', '-id', match.group(1), '_NET_WM_PID'],
                                      capture_output=True, text=True).stdout
            pid_match = re.search(r'=\s*(\d+)', pid_info or '')
            if not pid_match:
                continue
            try:
                owned = os.getpgid(int(pid_match.group(1))) == process.pid
            except ProcessLookupError:
                owned = False
            if owned:
                window_id = match.group(1)
                break
        if window_id:
            break
        time.sleep(0.1)
    if not window_id:
        raise RuntimeError('The synthetic Rofi window was not found; no screenshot taken')
    time.sleep(0.5)
    subprocess.run(['import', '-silent', '-window', window_id, str(output)],
                   check=True, timeout=10, stdout=subprocess.DEVNULL,
                   stderr=subprocess.PIPE)
    print(f'Saved synthetic Wi-Fi menu preview: {output}')
finally:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=3)
