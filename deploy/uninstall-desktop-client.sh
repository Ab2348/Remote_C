#!/usr/bin/env bash
set -euo pipefail

client_target="${XDG_BIN_HOME:-$HOME/.local/bin}/remote-c-client"
desktop_target="${XDG_DATA_HOME:-$HOME/.local/share}/applications/io.github.ab2348.RemoteC.desktop"
icon_target="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps/io.github.ab2348.RemoteC.svg"
waybar_target="${XDG_CONFIG_HOME:-$HOME/.config}/waybar/modules/custom-remote-c.jsonc"

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

if [[ "${1:-}" == "--integrate-waybar" ]]; then
    python3 "$script_dir/configure-waybar.py" --remove
    pkill -SIGUSR2 waybar 2>/dev/null || true
fi

rm -f -- "$client_target" "$desktop_target" "$icon_target" "$waybar_target"

echo "Cliente de escritorio de Remote C desinstalado."
