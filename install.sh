#!/usr/bin/env bash
#
# install.sh -- copy this repo into $HOME, backing up whatever was there.
#
#   ./install.sh                configs, shell files, ~/.local/bin, fonts, wallpapers
#   ./install.sh --system       also install usr-local-bin/ into /usr/local/bin (sudo)
#   ./install.sh --packages     also run install-packages.sh
#   ./install.sh --wallpapers   also download the animated wallpapers
#   ./install.sh --all          everything above
#
set -euo pipefail

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP="$HOME/dotfiles-backup-$(date +%s)"
DO_SYSTEM=0; DO_PACKAGES=0; DO_WALLPAPERS=0

usage() {
    sed -n '2,10p' "$0"
    exit 0
}

for arg in "$@"; do
    case "$arg" in
        --system)     DO_SYSTEM=1 ;;
        --packages)   DO_PACKAGES=1 ;;
        --wallpapers) DO_WALLPAPERS=1 ;;
        --all)        DO_SYSTEM=1; DO_PACKAGES=1; DO_WALLPAPERS=1 ;;
        -h|--help)    usage ;;
        *) echo "install.sh: unknown option: $arg" >&2; usage ;;
    esac
done

say() { printf '  %s\n' "$*"; }

backup_path() {
    local target="$1" rel
    [ -e "$target" ] || return 0
    rel="${target#"$HOME"/}"
    mkdir -p "$BACKUP/$(dirname "$rel")"
    cp -a "$target" "$BACKUP/$rel"
    say "backed up ~/$rel"
}

install_path() { # <src> <dst>
    local src="$1" dst="$2"
    backup_path "$dst"
    rm -rf "$dst"
    mkdir -p "$(dirname "$dst")"
    cp -a "$src" "$dst"
}

echo "==> Backups go to $BACKUP"

echo "==> ~/.config"
for src in "$DOTFILES"/config/*; do
    install_path "$src" "$HOME/.config/$(basename "$src")"
done

echo "==> shell files"
for src in "$DOTFILES"/home/.[!.]*; do
    install_path "$src" "$HOME/$(basename "$src")"
done

echo "==> ~/.local/bin"
mkdir -p "$HOME/.local/bin"
for src in "$DOTFILES"/local/bin/*; do
    install_path "$src" "$HOME/.local/bin/$(basename "$src")"
done
# The bar's Wi-Fi menu works without a separate system-wide install.
install_path "$DOTFILES/usr-local-bin/networkmanager_dmenu" "$HOME/.local/bin/networkmanager_dmenu"
chmod +x "$HOME/.local/bin/"* 2>/dev/null || true

# networkmanager-dmenu does not expand ~ in the launcher executable itself.
python3 - "$HOME/.config/networkmanager-dmenu/config.ini" <<'PY'
from pathlib import Path
import shlex
import sys

config = Path(sys.argv[1])
launcher = shlex.quote(str(config.parent / "rofi"))
config.write_text(config.read_text().replace(
    "dmenu_command = ~/.config/networkmanager-dmenu/rofi",
    "dmenu_command = " + launcher,
))
PY

echo "==> zsh plugins (bundled)"
for src in "$DOTFILES"/zsh/plugins/*; do
    install_path "$src" "$HOME/.zsh-plugins/$(basename "$src")"
done

echo "==> fonts"
mkdir -p "$HOME/.local/share/fonts" "$HOME/.fonts"
cp -a "$DOTFILES"/fonts/share/. "$HOME/.local/share/fonts/"
cp -a "$DOTFILES"/fonts/home/. "$HOME/.fonts/" 2>/dev/null || true
command -v fc-cache >/dev/null 2>&1 && fc-cache -f >/dev/null || true

echo "==> wallpapers"
mkdir -p "$HOME/Pictures/Wallpapers"
for src in "$DOTFILES"/wallpapers/*; do
    case "$src" in
        *.jpg|*.jpeg|*.png|*.webp) cp -a "$src" "$HOME/Pictures/Wallpapers/" ;;
    esac
done

if [ "$DO_WALLPAPERS" = 1 ]; then
    echo "==> animated wallpapers"
    dest="$HOME/Pictures/Wallpapers/animated"
    mkdir -p "$dest"
    base="https://raw.githubusercontent.com/m4nqn/Colorful/main/wallpapers-animated"
    for f in city-drive-sunset-retro-live-wallpaper.mp4 Cyberpunk-2077-City-Live-Wallpaper.mp4; do
        if [ -s "$dest/$f" ]; then say "have $f"; continue; fi
        curl -fL --progress-bar "$base/$f" -o "$dest/$f" || say "failed: $f"
    done
fi

if [ "$DO_SYSTEM" = 1 ]; then
    echo "==> /usr/local/bin (sudo)"
    sudo cp -a "$DOTFILES"/usr-local-bin/. /usr/local/bin/
fi

if [ "$DO_PACKAGES" = 1 ]; then
    echo "==> packages"
    "$DOTFILES/install-packages.sh"
fi

echo
echo "Done. Old files are in $BACKUP"
echo "Log out and back in (or restart bspwm with super+alt+r) to pick everything up."
