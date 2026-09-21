#!/usr/bin/env bash
#
# install-packages.sh -- install the packages this setup needs.
#
#   - apt packages from packages/apt-manual.txt
#   - pywal (pip --user)
#   - zsh plugins that are not bundled in zsh/plugins
#
set -euo pipefail

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUDO=""
[ "$(id -u)" -eq 0 ] || SUDO="sudo"

echo "==> apt packages ($(grep -cvE '^[[:space:]]*(#|$)' "$DOTFILES/packages/apt-manual.txt") entries)"
$SUDO apt update
# shellcheck disable=SC2046
$SUDO apt install -y $(grep -vE '^[[:space:]]*(#|$)' "$DOTFILES/packages/apt-manual.txt" | tr '\n' ' ')

echo "==> pip: pywal"
if command -v pip >/dev/null 2>&1; then
    pip install --user pywal \
        || pip install --user --break-system-packages pywal \
        || echo "  (pip install failed, skipping)"
fi

echo "==> zsh plugins"
clone() { # <url> <dir>
    if [ -d "$2/.git" ]; then
        echo "  have $(basename "$2")"
        return 0
    fi
    git clone --depth=1 "$1" "$2"
}
mkdir -p "$HOME/.zsh-plugins"
clone https://github.com/zdharma-continuum/fast-syntax-highlighting    "$HOME/.zsh-plugins/fast-syntax-highlighting"
clone https://github.com/zsh-users/zsh-autosuggestions                "$HOME/.zsh-plugins/zsh-autosuggestions"
clone https://github.com/zsh-users/zsh-completions                    "$HOME/.zsh-plugins/zsh-completions"
clone https://github.com/zsh-users/zsh-history-substring-search       "$HOME/.zsh-plugins/zsh-history-substring-search"
clone https://github.com/woefe/git-prompt.zsh                         "$HOME/.zsh-plugins/git-prompt.zsh"
clone https://github.com/junegunn/fzf                                 "$HOME/.zsh-plugins/fzf"
cp -f "$HOME/.zsh-plugins/fzf/shell/completion.zsh"   "$HOME/.zsh-plugins/fzf/" 2>/dev/null || true
cp -f "$HOME/.zsh-plugins/fzf/shell/key-bindings.zsh" "$HOME/.zsh-plugins/fzf/" 2>/dev/null || true

echo "==> fonts"
command -v fc-cache >/dev/null 2>&1 && fc-cache -f >/dev/null || true

echo "Done."
