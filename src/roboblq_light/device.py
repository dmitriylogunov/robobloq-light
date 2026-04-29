"""
HID I/O for the ROBOBLOQ light strip.

Wraps ``hidapi`` to expose a small, focused API:

- :func:`find_devices` — enumerate matching strips on the system.
- :class:`HidLight` — open a strip and write packets to it.

Keeping I/O isolated here means the protocol layer stays trivially testable
without hardware, and any future transport change (BLE, dongle) can sit
alongside without touching protocol code.
"""

from __future__ import annotations

import logging
from typing import Iterator

import hid  # type: ignore[import-not-found]

from . import protocol

log = logging.getLogger(__name__)


class StripNotFoundError(RuntimeError):
    """Raised when no matching strip is connected (or another app holds it)."""


class HidLight:
    """
    A connected ROBOBLOQ light strip.

    Use as a context manager so the HID handle is released promptly::

        with HidLight.open() as light:
            light.write(protocol.build_solid_color(255, 0, 0))

    The :class:`Light` facade in ``__init__`` is usually nicer for everyday
    use; this class is the lower-level alternative when you want to send
    raw packets you've built yourself.
    """

    def __init__(self, device: "hid.device", path: bytes) -> None:
        self._device = device
        self._path = path
        self._closed = False

    # ------------------------------------------------------------------ open

    @classmethod
    def open(cls) -> "HidLight":
        """Locate and open the first connected strip's data interface."""
        info = _find_data_interface()
        if info is None:
            raise StripNotFoundError(
                f"No strip found (VID=0x{protocol.VENDOR_ID:04X} "
                f"PID=0x{protocol.PRODUCT_ID:04X} interface={protocol.INTERFACE}). "
                "Is it plugged in? Is SyncLight still running and holding the handle?"
            )
        device = hid.device()
        device.open_path(info["path"])
        device.set_nonblocking(True)
        log.debug("Opened strip at %s", info["path"])
        return cls(device, info["path"])

    # --------------------------------------------------------------- context

    def __enter__(self) -> "HidLight":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        if not self._closed:
            try:
                self._device.close()
            finally:
                self._closed = True

    # ----------------------------------------------------------------- write

    def write(self, packet: bytes) -> int:
        """
        Send a raw protocol packet to the strip.

        On Windows, HID writes need a leading report-ID byte. The strip uses
        report ID 0 (no explicit report ID), so we prepend 0x00 here. The
        return value is the number of bytes hidapi reports as written —
        typically the device's full output report size (e.g. 65), with the
        unused tail being zero-padded by the OS. The strip ignores the
        padding.

        :return: bytes written including the report-ID prefix.
        :raises OSError: if the device has been disconnected.
        """
        if self._closed:
            raise RuntimeError("HidLight is closed")
        n = self._device.write(b"\x00" + packet)
        if n < 0:
            raise OSError("HID write failed")
        log.debug("wrote %d bytes: %s", n, packet.hex(" "))
        return n


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------

def find_devices() -> Iterator[dict]:
    """Yield all HID interfaces matching the strip's VID/PID."""
    yield from hid.enumerate(protocol.VENDOR_ID, protocol.PRODUCT_ID)


def _find_data_interface() -> dict | None:
    """
    Return the dict for the strip's vendor-defined data interface (MI_00,
    usage page 0xFF00) or None if not found. Falls back to interface_number
    matching alone if the usage page isn't reported.
    """
    candidates = list(find_devices())
    for d in candidates:
        if (d.get("interface_number") == protocol.INTERFACE
                and d.get("usage_page") == protocol.USAGE_PAGE):
            return d
    for d in candidates:
        if d.get("interface_number") == protocol.INTERFACE:
            return d
    return None
