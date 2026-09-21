# == Set Locale ==
export LC_CTYPE=en_US.UTF-8

# == Sourcing Files ==
# Base config
source $HOME/.zsh-plugins/vi-mode.zsh/vi-mode.plugin.zsh
source $HOME/.zsh-plugins/wbase.zsh/wbase.zsh

# Enable fish-shell like autosuggestion
ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE='fg=247'
ZSH_AUTOSUGGEST_USE_ASYNC=1
source $HOME/.zsh-plugins/zsh-autosuggestions/zsh-autosuggestions.zsh

# fzf keybindings and completion
if check_prog fzf; then
    source $HOME/.zsh-plugins/fzf/completion.zsh
    source $HOME/.zsh-plugins/fzf/key-bindings.zsh
fi

# Prompt: git status, hostname for ssh sessions, vi mode indicator
source $HOME/.zsh-plugins/git-prompt.zsh/git-prompt.zsh
source $HOME/.zsh-plugins/git-prompt.zsh/examples/wprompt.zsh

# Enable syntax highlighting. Must be loaded after all `zle -N` calls.
source $HOME/.zsh-plugins/fast-syntax-highlighting/fast-syntax-highlighting.plugin.zsh

# Enable fish-shell like history searching. Must be loaded after zsh-syntax-highlighting.
source $HOME/.zsh-plugins/zsh-history-substring-search/zsh-history-substring-search.zsh

# === Keybindings ===
# substring search plugin
bindkey -M main '^[OA' history-substring-search-up
bindkey -M main '^[OB' history-substring-search-down
bindkey -M main '^[[A' history-substring-search-up
bindkey -M main '^[[B' history-substring-search-down
bindkey -M vicmd '^k' history-substring-search-up
bindkey -M vicmd '^j' history-substring-search-down
bindkey '^k' history-substring-search-up
bindkey '^j' history-substring-search-down
bindkey '^H' backward-kill-word

# autosuggest plugin
bindkey '^ ' autosuggest-accept
bindkey '^f' autosuggest-accept

# edit-command-line module
autoload -Uz edit-command-line
bindkey -M vicmd 'V' edit-command-line
#}}}

#{{{ Aliases
alias ...='cd ../..'
alias g='git'
alias grep='grep --color=auto'
if command -v eza >/dev/null 2>&1; then
    alias ls='eza --color=auto --icons'
    alias l='eza --color=auto --icons'
    alias la='eza -lah --color=auto --icons'
    alias lh='eza -lh --color=auto --icons'
    alias ll='eza -lah --color=auto --icons'
elif command -v exa >/dev/null 2>&1; then
    alias ls='exa --color=auto --icons'
    alias l='exa --color=auto --icons'
    alias la='exa -lah --color=auto --icons'
    alias lh='exa -lh --color=auto --icons'
    alias ll='exa -lah --color=auto --icons'
else
    alias ls='ls --color=auto'
    alias l='ls -l --color=auto'
    alias la='ls -lah --color=auto'
    alias lh='ls -lh --color=auto'
    alias ll='ls -lah --color=auto'
fi
alias :q='exit'
alias ssh-public-key='cat ~/.ssh/id_rsa.pub'
alias vim='nvim'
alias notes='nvim /data/sync/Documents/vimwiki/index.md'
#}}}

# source $HOME/.zsh-plugins/vimwiki.zsh
# vimwiki_stats

# Purple terminal colors
export LS_COLORS='di=38;5;141:ln=38;5;117:so=38;5;213:pi=38;5;141:ex=38;5;120:bd=38;5;141:cd=38;5;141:su=38;5;213:sg=38;5;213:tw=38;5;141:ow=38;5;141'

# opencode
export PATH="$HOME/.opencode/bin:$PATH"
