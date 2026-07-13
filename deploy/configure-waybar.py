#!/usr/bin/env python3
"""Install or remove Remote C from the user's carlos-clean Waybar layout."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path


MODULE_NAME = "custom/remote-c"
LAYOUT_GROUP = "group/rightbox#main"
STYLE_MARKER_START = "/* Remote C: inicio */"
STYLE_MARKER_END = "/* Remote C: fin */"
STYLE_BLOCK = f"""

{STYLE_MARKER_START}
#custom-remote-c {{
  padding: 0px 5px;
  margin: 0px;
  min-height: 0px;
}}
{STYLE_MARKER_END}
"""


class ConfigurationError(RuntimeError):
    pass


def config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def backup(path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    destination = path.with_name(f"{path.name}.bak.remote-c.{timestamp}")
    shutil.copy2(path, destination)
    return destination


def layout_module_block(content: str) -> tuple[int, int, str]:
    group_match = re.search(
        rf'"{re.escape(LAYOUT_GROUP)}"\s*:\s*\{{',
        content,
    )
    if group_match is None:
        raise ConfigurationError(
            f"No se encontró {LAYOUT_GROUP} en el layout"
        )

    modules_match = re.search(
        r'"modules"\s*:\s*\[(?P<body>.*?)\]',
        content[group_match.end() :],
        flags=re.DOTALL,
    )
    if modules_match is None:
        raise ConfigurationError(
            f"No se encontró la lista de módulos de {LAYOUT_GROUP}"
        )

    body_start = group_match.end() + modules_match.start("body")
    body_end = group_match.end() + modules_match.end("body")
    return body_start, body_end, content[body_start:body_end]


def add_layout_module(content: str) -> str:
    body_start, body_end, body = layout_module_block(content)
    if f'"{MODULE_NAME}"' in body:
        return content

    anchor = re.search(r'(?P<indent>\s*)"custom/updates"\s*,?', body)
    if anchor is None:
        raise ConfigurationError(
            "No se encontró custom/updates como punto de inserción seguro"
        )

    indent = anchor.group("indent")
    insertion_point = body_start + anchor.start()
    insertion = f'{indent}"{MODULE_NAME}",'
    return content[:insertion_point] + insertion + content[insertion_point:]


def remove_layout_module(content: str) -> str:
    body_start, body_end, body = layout_module_block(content)
    updated = re.sub(
        rf'^[ \t]*"{re.escape(MODULE_NAME)}"[ \t]*,?[ \t]*\r?\n?',
        "",
        body,
        count=1,
        flags=re.MULTILINE,
    )
    return content[:body_start] + updated + content[body_end:]


def add_style(content: str) -> str:
    if STYLE_MARKER_START in content:
        return content
    return content.rstrip() + STYLE_BLOCK + "\n"


def remove_style(content: str) -> str:
    pattern = re.compile(
        rf'\n*{re.escape(STYLE_MARKER_START)}.*?'
        rf'{re.escape(STYLE_MARKER_END)}\n*',
        flags=re.DOTALL,
    )
    return pattern.sub("\n", content).rstrip() + "\n"


def update_file(path: Path, transform) -> Path | None:
    if not path.is_file():
        raise ConfigurationError(f"No existe {path}")

    current = path.read_text(encoding="utf-8")
    updated = transform(current)
    if updated == current:
        return None

    backup_path = backup(path)
    path.write_text(updated, encoding="utf-8")
    return backup_path


def configure(remove: bool) -> list[Path]:
    waybar = config_home() / "waybar"
    paths = (
        waybar / "layouts" / "carlos-clean.jsonc",
        waybar / "config.jsonc",
    )
    layout_transform = remove_layout_module if remove else add_layout_module
    style_transform = remove_style if remove else add_style
    backups: list[Path] = []

    for path in paths:
        result = update_file(path, layout_transform)
        if result is not None:
            backups.append(result)

    result = update_file(waybar / "user-style.css", style_transform)
    if result is not None:
        backups.append(result)

    return backups


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--remove",
        action="store_true",
        help="retira Remote C del layout y del CSS",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        backups = configure(remove=args.remove)
    except (ConfigurationError, OSError) as error:
        print(f"No se pudo configurar Waybar: {error}", file=sys.stderr)
        return 1

    action = "retirado de" if args.remove else "añadido a"
    print(f"Remote C fue {action} carlos-clean.")
    for path in backups:
        print(f"Respaldo: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
