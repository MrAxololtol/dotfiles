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

# apt installs nothing at all when one name is unresolvable, so resolve the
# list against this system first. The list is the author's apt-mark showmanual
# dump and contains packages that other distros do not ship.
WANTED=()
while IFS= read -r pkg; do
    [ -n "$pkg" ] && WANTED+=("$pkg")
done < <(grep -vE '^[[:space:]]*(#|$)' "$DOTFILES/packages/apt-manual.txt")

AVAILABLE=()
SKIPPED=()
for pkg in "${WANTED[@]}"; do
    if apt-cache show -- "$pkg" >/dev/null 2>&1; then
        AVAILABLE+=("$pkg")
    else
        SKIPPED+=("$pkg")
    fi
done

# Drop a package when another selected package both conflicts with and provides
# it (Debian's nodejs ships npm and Conflicts: npm, so the standalone npm would
# break the install).
declare -A PROVIDES=() CONFLICTS=()
while read -r kind pkg name; do
    case "$kind" in
        P) PROVIDES["$pkg"]+=" $name" ;;
        C) CONFLICTS["$pkg"]+=" $name" ;;
    esac
done < <(apt-cache show -- "${AVAILABLE[@]}" 2>/dev/null | awk '
    /^Package:/ { pkg=$2 }
    /^Provides:/ { line=substr($0, index($0, ":")+2); n=split(line, items, ","); for (i=1; i<=n; i++) { name=items[i]; gsub(/^[ \t]+|[ \t]+$/, "", name); sub(/[ \t]*\(.*/, "", name); if (name != "") print "P", pkg, name } }
    /^Conflicts:/ { line=substr($0, index($0, ":")+2); n=split(line, items, ","); for (i=1; i<=n; i++) { name=items[i]; gsub(/^[ \t]+|[ \t]+$/, "", name); sub(/[ \t]*\(.*/, "", name); if (name != "") print "C", pkg, name } }
')

declare -A DROP=()
for pkg in "${AVAILABLE[@]}"; do
    for conflict in ${CONFLICTS[$pkg]:-}; do
        [ "${DROP[$conflict]:-}" = 1 ] && continue
        if [[ " ${PROVIDES[$pkg]:-} " == *" $conflict "* ]]; then
            DROP[$conflict]=1
        fi
    done
done

SELECTED=()
for pkg in "${AVAILABLE[@]}"; do
    [ "${DROP[$pkg]:-}" = 1 ] && continue
    SELECTED+=("$pkg")
done

echo "==> apt packages (${#SELECTED[@]} of ${#WANTED[@]} entries)"
if [ "${#SKIPPED[@]}" -gt 0 ]; then
    echo "  skipped (not available here): ${SKIPPED[*]}"
fi
for pkg in "${!DROP[@]}"; do
    echo "  dropped (provided by a conflicting package): $pkg"
done

$SUDO apt update
$SUDO apt install -y "${SELECTED[@]}"

echo "==> pip: pywal"
if command -v pip3 >/dev/null 2>&1; then
    pip3 install --user pywal \
        || pip3 install --user --break-system-packages pywal \
        || echo "  (pip install failed, skipping)"
else
    echo "  (pip3 not found, skipping)"
fi

echo "==> zsh plugins"
clone() { # <url> <dir>
    if [ -d "$2/.git" ]; then
        echo "  have $(basename "$2")"
        return 0
    fi
    git clone --depth=1 "$1" "$2" || echo "  (clone failed: $(basename "$2"), skipping)"
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
