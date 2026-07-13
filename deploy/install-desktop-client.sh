#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
project_dir=$(cd -- "$script_dir/.." && pwd)

client_source="$project_dir/desktop/remote_c_client.py"
desktop_source="$project_dir/desktop/io.github.ab2348.RemoteC.desktop"
icon_source="$project_dir/app/static/icon.svg"
waybar_source="$project_dir/deploy/waybar/custom-remote-c.jsonc"
waybar_configurator="$project_dir/deploy/configure-waybar.py"

client_target="${XDG_BIN_HOME:-$HOME/.local/bin}/remote-c-client"
desktop_target="${XDG_DATA_HOME:-$HOME/.local/share}/applications/io.github.ab2348.RemoteC.desktop"
icon_target="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps/io.github.ab2348.RemoteC.svg"
waybar_target="${XDG_CONFIG_HOME:-$HOME/.config}/waybar/modules/custom-remote-c.jsonc"

if ! python3 -c 'import gi; gi.require_version("Gtk", "4.0"); gi.require_version("WebKit", "6.0")' 2>/dev/null; then
    echo "Faltan dependencias: instala gtk4, webkitgtk-6.0 y python-gobject." >&2
    exit 1
fi

install -Dm755 "$client_source" "$client_target"
install -Dm644 "$desktop_source" "$desktop_target"
install -Dm644 "$icon_source" "$icon_target"
install -Dm644 "$waybar_source" "$waybar_target"

if [[ "${1:-}" == "--integrate-waybar" ]]; then
    python3 "$waybar_configurator"
    pkill -SIGUSR2 waybar 2>/dev/null || true
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$(dirname -- "$desktop_target")" >/dev/null 2>&1 || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor" >/dev/null 2>&1 || true
fi

echo "Cliente instalado en $client_target"
echo "Lanzador instalado como io.github.ab2348.RemoteC"
echo "Módulo de Waybar instalado en $waybar_target"
if [[ "${1:-}" != "--integrate-waybar" ]]; then
    echo "Waybar aún no fue modificado. Para integrarlo:"
    echo "  $0 --integrate-waybar"
fi
