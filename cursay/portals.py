from __future__ import annotations

import logging
import secrets
import time
from collections.abc import Callable
from typing import Any

import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

from .config import APP_ID


LOG = logging.getLogger(__name__)
PORTAL_BUS = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"
REQUEST_IFACE = "org.freedesktop.portal.Request"
SESSION_IFACE = "org.freedesktop.portal.Session"
SHORTCUT_IFACE = "org.freedesktop.portal.GlobalShortcuts"
REGISTRY_IFACE = "org.freedesktop.host.portal.Registry"
_REGISTERED_PEERS: set[str] = set()
REPEAT_RELEASE_GAP_SECONDS = 0.30
FIRST_REPEAT_DEADLINE_SECONDS = 0.85
RELEASE_WATCH_INTERVAL_MS = 50


def _token(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def _register_host_app(bus: dbus.SessionBus) -> None:
    """Associate this unsandboxed D-Bus peer with our installed desktop app ID."""
    peer = str(bus.get_unique_name())
    if peer in _REGISTERED_PEERS:
        return
    registry = dbus.Interface(bus.get_object(PORTAL_BUS, PORTAL_PATH), REGISTRY_IFACE)
    try:
        registry.Register(APP_ID, dbus.Dictionary({}, signature="sv"))
        LOG.info("Registered portal host app id %s for peer %s", APP_ID, peer)
    except dbus.DBusException as exc:
        # Older portals infer the app id from the launcher and may not expose Registry.
        if exc.get_dbus_name() not in {
            "org.freedesktop.DBus.Error.UnknownInterface",
            "org.freedesktop.DBus.Error.UnknownMethod",
        }:
            raise
        LOG.info("Host app registry is unavailable; using portal launcher detection")
    _REGISTERED_PEERS.add(peer)


class PortalRequest:
    def __init__(self, bus: dbus.SessionBus, path: str, callback: Callable[[int, dict], None]) -> None:
        self.bus = bus
        self.path = path
        self.callback = callback
        self.match = None
        obj = bus.get_object(PORTAL_BUS, path)
        self.match = obj.connect_to_signal("Response", self._response, dbus_interface=REQUEST_IFACE)

    def _response(self, response: int, results: dict) -> None:
        try:
            self.callback(int(response), dict(results))
        finally:
            self.close()

    def close(self) -> None:
        if self.match is not None:
            self.match.remove()
            self.match = None


class GlobalShortcutPortal:
    def __init__(
        self,
        on_pressed: Callable[[], None],
        on_released: Callable[[], None],
        on_status: Callable[[str], None],
    ) -> None:
        DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SessionBus()
        _register_host_app(self.bus)
        self.portal = dbus.Interface(self.bus.get_object(PORTAL_BUS, PORTAL_PATH), SHORTCUT_IFACE)
        self.on_pressed = on_pressed
        self.on_released = on_released
        self.on_status = on_status
        self.session_path: str | None = None
        self.requests: list[PortalRequest] = []
        self.signal_matches: list[Any] = []
        self.key_down = False
        self.key_repeating = False
        self.last_activation_at = 0.0
        self.release_watch_id: int | None = None

    def start(self, preferred_trigger: str) -> None:
        LOG.info("Requesting GlobalShortcuts session with preferred trigger %s", preferred_trigger)
        self.on_status("Requesting the global shortcut…")
        options = dbus.Dictionary(
            {
                "handle_token": dbus.String(_token("shortcut_request")),
                "session_handle_token": dbus.String(_token("shortcut_session")),
            },
            signature="sv",
        )
        try:
            path = str(self.portal.CreateSession(options))
            self.requests.append(PortalRequest(self.bus, path, lambda code, result: self._created(code, result, preferred_trigger)))
        except dbus.DBusException as exc:
            self.on_status(f"Shortcut portal unavailable: {exc.get_dbus_message()}")

    def _created(self, response: int, result: dict, preferred_trigger: str) -> None:
        LOG.info("GlobalShortcuts CreateSession response=%s keys=%s", response, sorted(result))
        if response != 0 or "session_handle" not in result:
            self.on_status("Global shortcut permission was not granted")
            return
        self.session_path = str(result["session_handle"])
        self.signal_matches.extend(
            [
                self.bus.add_signal_receiver(
                    self._activated,
                    signal_name="Activated",
                    dbus_interface=SHORTCUT_IFACE,
                    bus_name=PORTAL_BUS,
                    path=PORTAL_PATH,
                ),
                self.bus.add_signal_receiver(
                    self._deactivated,
                    signal_name="Deactivated",
                    dbus_interface=SHORTCUT_IFACE,
                    bus_name=PORTAL_BUS,
                    path=PORTAL_PATH,
                ),
            ]
        )
        shortcut_options = dbus.Dictionary(
            {
                "description": dbus.String("Hold to dictate with Cursay"),
                "preferred_trigger": dbus.String(preferred_trigger),
            },
            signature="sv",
        )
        shortcuts = dbus.Array(
            [dbus.Struct((dbus.String("push-to-talk"), shortcut_options), signature=None)],
            signature="(sa{sv})",
        )
        options = dbus.Dictionary({"handle_token": dbus.String(_token("bind"))}, signature="sv")
        try:
            path = str(self.portal.BindShortcuts(self.session_path, shortcuts, "", options))
            self.requests.append(PortalRequest(self.bus, path, self._bound))
        except dbus.DBusException as exc:
            self.on_status(f"Could not bind shortcut: {exc.get_dbus_message()}")

    def _bound(self, response: int, _result: dict) -> None:
        LOG.info("GlobalShortcuts BindShortcuts response=%s", response)
        if response == 0:
            self.on_status("Global push-to-talk is ready")
        else:
            self.on_status("Global shortcut setup was cancelled")

    def _activated(self, session: str, shortcut_id: str, _timestamp: int, _options: dict) -> None:
        if str(session) == self.session_path and str(shortcut_id) == "push-to-talk":
            self.last_activation_at = time.monotonic()
            self._ensure_release_watch()
            if not self.key_down:
                self.key_down = True
                self.key_repeating = False
                LOG.info("Global shortcut pressed")
                self.on_pressed()
                return
            # GNOME forwards key-repeat activations while the keys are held.
            # Strict push-to-talk ignores every activation until Deactivated.
            if not self.key_repeating:
                LOG.info("Global shortcut key repeat detected; suppressing repeats")
            self.key_repeating = True

    def _ensure_release_watch(self) -> None:
        if self.release_watch_id is None:
            self.release_watch_id = GLib.timeout_add(
                RELEASE_WATCH_INTERVAL_MS,
                self._check_inferred_release,
            )

    def _check_inferred_release(self) -> bool:
        if not self.key_down:
            self.release_watch_id = None
            return False
        gap = time.monotonic() - self.last_activation_at
        deadline = REPEAT_RELEASE_GAP_SECONDS if self.key_repeating else FIRST_REPEAT_DEADLINE_SECONDS
        if gap < deadline:
            return True
        LOG.info("Global shortcut release inferred after activation stream ended (gap=%.3fs)", gap)
        self.release_watch_id = None
        self._emit_release()
        return False

    def _emit_release(self) -> None:
        self.key_down = False
        self.key_repeating = False
        self.on_released()

    def _deactivated(self, session: str, shortcut_id: str, _timestamp: int, _options: dict) -> None:
        if (
            str(session) == self.session_path
            and str(shortcut_id) == "push-to-talk"
            and self.key_down
        ):
            LOG.info("Global shortcut released")
            if self.release_watch_id is not None:
                GLib.source_remove(self.release_watch_id)
                self.release_watch_id = None
            self._emit_release()

    def configure(self) -> None:
        if not self.session_path:
            self.on_status("The shortcut session is not ready yet")
            return
        try:
            LOG.info("Opening GlobalShortcuts configuration dialog")
            self.portal.ConfigureShortcuts(
                self.session_path,
                "",
                dbus.Dictionary({}, signature="sv"),
            )
        except dbus.DBusException as exc:
            self.on_status(f"Could not open shortcut settings: {exc.get_dbus_message()}")

    def close(self) -> None:
        if self.release_watch_id is not None:
            GLib.source_remove(self.release_watch_id)
            self.release_watch_id = None
        for request in self.requests:
            request.close()
        self.requests.clear()
        for match in self.signal_matches:
            try:
                match.remove()
            except Exception:
                pass
        self.signal_matches.clear()
        if self.session_path:
            try:
                dbus.Interface(self.bus.get_object(PORTAL_BUS, self.session_path), SESSION_IFACE).Close()
            except dbus.DBusException:
                pass
            self.session_path = None
