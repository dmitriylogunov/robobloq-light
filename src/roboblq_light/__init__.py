"""
Control a ROBOBLOQ USB ambient LED strip from Python.

Quick start::

    from roboblq_light import Light

    with Light.open() as light:
        light.set_color(255, 220, 180)   # warm white

For lower-level access, see :mod:`roboblq_light.protocol` (pure packet
builders) and :mod:`roboblq_light.device` (HID I/O).
"""

from __future__ import annotations

from . import protocol
from .device import HidLight, StripNotFoundError, find_devices
from .protocol import (
    PRODUCT_ID,
    VENDOR_ID,
    PacketIdGenerator,
    Section,
    build_set_brightness,
    build_set_section_led,
    build_solid_color,
    build_turn_off,
    decode_packet,
)

__all__ = [
    "Light",
    "HidLight",
    "Section",
    "StripNotFoundError",
    "PacketIdGenerator",
    "VENDOR_ID",
    "PRODUCT_ID",
    "find_devices",
    "build_set_brightness",
    "build_set_section_led",
    "build_solid_color",
    "build_turn_off",
    "decode_packet",
    "protocol",
]


class Light:
    """
    High-level facade for a single connected strip.

    Each method builds the appropriate packet via the protocol module and
    sends it through an :class:`HidLight`. Designed to be used as a context
    manager::

        with Light.open() as light:
            light.set_brightness(80)
            light.set_color(60, 0, 160)

    For multi-section control (different colour per LED segment), drop down
    to ``light.send(build_set_section_led([Section(...), Section(...), ...]))``
    or use :class:`HidLight` directly with packets you've built yourself.
    """

    def __init__(self, hid_light: HidLight, *,
                 id_gen: PacketIdGenerator | None = None) -> None:
        self._hid = hid_light
        self._id_gen = id_gen or PacketIdGenerator()

    # ---------------------------------------------------------- open / close

    @classmethod
    def open(cls) -> "Light":
        """Open the first connected strip."""
        return cls(HidLight.open())

    def close(self) -> None:
        self._hid.close()

    def __enter__(self) -> "Light":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # -------------------------------------------------------------- commands

    def set_brightness(self, level: int) -> None:
        """Set global brightness (0-100). Out-of-range values are clamped."""
        self._hid.write(protocol.build_set_brightness(level, id_gen=self._id_gen))

    def turn_off(self) -> None:
        """Switch the strip off entirely."""
        self._hid.write(protocol.build_turn_off(id_gen=self._id_gen))

    def set_color(self, r: int, g: int, b: int) -> None:
        """
        Set the entire strip to a single RGB colour.

        Sends a setSectionLED packet with one section at index 0; the strip's
        firmware broadcasts this to all physical sections.
        """
        self._hid.write(protocol.build_solid_color(r, g, b, id_gen=self._id_gen))
        
    def set_white_bright(self, param1: int, param2: int) -> None:
        """
        Drive the strip's dedicated white LEDs (in addition to RGB).
        
        Most ambient strips with this protocol have warm-white and cool-white
        LEDs alongside the RGB ones. This command controls them. Parameter
        semantics are not yet fully understood — typically one byte is
        intensity, the other is mode/temperature.
        """
        self._hid.write(protocol.build_set_white_bright(
            param1, param2, id_gen=self._id_gen,
        ))        

    # -------------------------------------------------------------- raw send

    def send(self, packet: bytes) -> int:
        """Send an arbitrary, pre-built packet. For protocol experimentation."""
        return self._hid.write(packet)
