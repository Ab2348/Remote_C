#!/usr/bin/env python3
"""Native desktop shell for the Remote C web client."""

from __future__ import annotations

import os
import sys
from urllib.parse import urlparse

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")

from gi.repository import Gio, GLib, Gtk, WebKit  # noqa: E402


APPLICATION_ID = "io.github.ab2348.RemoteC"
DEFAULT_URL = "http://127.0.0.1:8765/"


def remote_c_url() -> str:
    """Return a safe HTTP(S) URL for the Remote C server."""
    value = os.environ.get("REMOTE_C_URL", DEFAULT_URL).strip()
    parsed = urlparse(value)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        print(
            "REMOTE_C_URL debe ser una URL HTTP(S) válida; "
            f"usando {DEFAULT_URL}",
            file=sys.stderr,
        )
        return DEFAULT_URL

    return value


class RemoteCWindow(Gtk.ApplicationWindow):
    """Regular GTK window containing the existing Remote C interface."""

    def __init__(self, application: Gtk.Application, server_url: str) -> None:
        super().__init__(
            application=application,
            title="Remote C",
            default_width=480,
            default_height=780,
        )
        self.server_url = server_url
        self._main_load_failed = False
        self.set_size_request(320, 420)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(160)
        self.set_child(self.stack)

        self.web_view = WebKit.WebView()
        settings = self.web_view.get_settings()
        settings.set_enable_developer_extras(
            os.environ.get("REMOTE_C_DEBUG") == "1"
        )
        self.web_view.connect("load-changed", self._on_load_changed)
        self.web_view.connect("load-failed", self._on_load_failed)
        self.stack.add_named(self.web_view, "remote-c")

        self.error_page = self._build_error_page()
        self.stack.add_named(self.error_page, "connection-error")

        self._install_actions()
        self.load_remote_c()

    def _build_error_page(self) -> Gtk.Widget:
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        page.set_halign(Gtk.Align.CENTER)
        page.set_valign(Gtk.Align.CENTER)
        page.set_margin_start(28)
        page.set_margin_end(28)
        page.set_margin_top(28)
        page.set_margin_bottom(28)

        icon = Gtk.Image.new_from_icon_name("network-offline-symbolic")
        icon.set_pixel_size(48)

        title = Gtk.Label(label="Remote C no está disponible")
        title.add_css_class("title-2")

        detail = Gtk.Label(
            label=(
                "No se pudo conectar con el servidor local. "
                "Comprueba el servicio y vuelve a intentarlo."
            )
        )
        detail.set_wrap(True)
        detail.set_justify(Gtk.Justification.CENTER)
        detail.add_css_class("dim-label")

        address = Gtk.Label(label=self.server_url)
        address.set_selectable(True)
        address.add_css_class("monospace")
        address.add_css_class("dim-label")

        retry = Gtk.Button(label="Reintentar")
        retry.add_css_class("suggested-action")
        retry.set_halign(Gtk.Align.CENTER)
        retry.connect("clicked", lambda _button: self.load_remote_c())

        page.append(icon)
        page.append(title)
        page.append(detail)
        page.append(address)
        page.append(retry)
        return page

    def _install_actions(self) -> None:
        reload_action = Gio.SimpleAction.new("reload", None)
        reload_action.connect("activate", lambda *_args: self.load_remote_c())
        self.add_action(reload_action)

        application = self.get_application()
        application.set_accels_for_action("win.reload", ["<Control>r", "F5"])

    def load_remote_c(self) -> None:
        self._main_load_failed = False
        self.stack.set_visible_child_name("remote-c")
        self.web_view.load_uri(self.server_url)

    def _on_load_changed(
        self,
        _web_view: WebKit.WebView,
        load_event: WebKit.LoadEvent,
    ) -> None:
        if (
            load_event == WebKit.LoadEvent.FINISHED
            and not self._main_load_failed
        ):
            self.stack.set_visible_child_name("remote-c")

    def _on_load_failed(
        self,
        _web_view: WebKit.WebView,
        _load_event: WebKit.LoadEvent,
        failing_uri: str,
        error: GLib.Error,
    ) -> bool:
        if failing_uri.rstrip("/") == self.server_url.rstrip("/"):
            self._main_load_failed = True
            print(f"No se pudo cargar {failing_uri}: {error.message}", file=sys.stderr)
            self.stack.set_visible_child_name("connection-error")
            return True

        return False


class RemoteCApplication(Gtk.Application):
    """Single-instance GTK application for Remote C."""

    def __init__(self) -> None:
        super().__init__(
            application_id=APPLICATION_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.server_url = remote_c_url()

    def do_activate(self) -> None:
        window = self.get_active_window()

        if window is None:
            windows = self.get_windows()
            window = windows[0] if windows else RemoteCWindow(self, self.server_url)

        window.present()


def main(argv: list[str] | None = None) -> int:
    application = RemoteCApplication()
    return application.run(argv if argv is not None else sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
