#!/usr/bin/bash

COLORFUL="$HOME/Colorful"

if pgrep -af -- "--colorblocks" >/dev/null; then
    rofi -theme "$COLORFUL/.config/polybar/colorblocks/scripts/rofi/launcher.rasi" -show drun
elif pgrep -af -- "--trans" >/dev/null; then
    rofi -theme "$COLORFUL/.config/polybar/trans/scripts/rofi/launcher.rasi" -show drun
else
    rofi -theme "$COLORFUL/.config/polybar/colorblocks/scripts/rofi/launcher.rasi" -show drun
fi
