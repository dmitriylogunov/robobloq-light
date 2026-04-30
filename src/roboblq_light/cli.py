"""
Command-line interface for ``roboblq_light``.

Run with ``python -m roboblq_light`` or, after installing, the ``rgblight``
script.

Examples::

    python -m roboblq_light probe
    python -m roboblq_light brightness 80
    python -m roboblq_light color 255 220 180
    python -m roboblq_light preset day
    python -m roboblq_light off
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Callable

from . import Light, find_devices, protocol


# A small built-in palette. The "day" / "night" choices come from the original
# ambient-lighting recommendation: warm white for focus, deep violet for
# low-light gaming.
# Other colours are tuned for ambient lighting use —
# the named hue dominates, but the other channels are non-zero so the strip
# casts illuminating light rather than a colour-distorting wash.
PRESETS: dict[str, tuple[int, int, int]] = {
    # Ambient
    "day":     (255, 220, 180),  # warm white
    "night":   (60,  0,   160),  # deep violet
    "off":     (0,   0,   0),

    # Tinted whites — colour identity preserved, room stays usable
    "red":     (255, 60,  40),
    "orange":  (255, 120, 50),
    "yellow":  (255, 200, 80),
    "green":   (120, 255, 100),
    "teal":    (80,  200, 180),
    "cyan":    (120, 210, 255),
    "blue":    (80,  120, 255),
    "purple":  (160, 80,  200),
    "pink":    (255, 140, 180),
    "magenta": (255, 110, 200),
    "white":   (255, 240, 220),  # unchanged
}

# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

def _cmd_probe(_: argparse.Namespace) -> int:
    devices = list(find_devices())
    if not devices:
        print(f"No strip found "
              f"(VID=0x{protocol.VENDOR_ID:04X} "
              f"PID=0x{protocol.PRODUCT_ID:04X}).")
        return 1
    for d in devices:
        print(f"  Path:        {d['path']!r}")
        print(f"  Interface:   {d.get('interface_number')}")
        print(f"  Usage page:  0x{d.get('usage_page', 0):04X}")
        print(f"  Usage:       0x{d.get('usage', 0):04X}")
        print(f"  Manufacturer:{d.get('manufacturer_string')}")
        print(f"  Product:     {d.get('product_string')}")
        print("  ---")
    return 0


def _cmd_brightness(args: argparse.Namespace) -> int:
    with Light.open() as light:
        light.set_brightness(args.level)
    return 0


def _cmd_off(_: argparse.Namespace) -> int:
    with Light.open() as light:
        light.turn_off()
    return 0


def _cmd_color(args: argparse.Namespace) -> int:
    with Light.open() as light:
        light.set_color(args.r, args.g, args.b)
    return 0


def _cmd_preset(args: argparse.Namespace) -> int:
    rgb = PRESETS.get(args.name)
    if rgb is None:
        print(f"Unknown preset: {args.name}. "
              f"Known: {', '.join(sorted(PRESETS))}")
        return 1
    with Light.open() as light:
        light.set_color(*rgb)
    return 0

def _cmd_white(args: argparse.Namespace) -> int:
    with Light.open() as light:
        light.set_white_bright(args.p1, args.p2)
    return 0

# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rgblight",
        description="Control a ROBOBLOQ USB ambient LED strip.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="enable debug logging",
    )
    sub = parser.add_subparsers(dest="command", required=False)

    sub.add_parser("probe", help="list connected strips").set_defaults(
        func=_cmd_probe
    )

    p_bright = sub.add_parser("brightness", help="set brightness 0-100")
    p_bright.add_argument("level", type=int)
    p_bright.set_defaults(func=_cmd_brightness)

    sub.add_parser("off", help="turn the strip off").set_defaults(
        func=_cmd_off
    )

    p_color = sub.add_parser("color", help="set entire strip to one RGB colour")
    p_color.add_argument("r", type=int)
    p_color.add_argument("g", type=int)
    p_color.add_argument("b", type=int)
    p_color.set_defaults(func=_cmd_color)

    p_preset = sub.add_parser(
        "preset",
        help=f"apply a named preset ({', '.join(sorted(PRESETS))})",
    )
    p_preset.add_argument("name")
    p_preset.set_defaults(func=_cmd_preset)

    p_white = sub.add_parser("white", help="set white-LED parameters (experimental)")
    p_white.add_argument("p1", type=int, help="first byte (0-255)")
    p_white.add_argument("p2", type=int, help="second byte (0-255)")
    p_white.set_defaults(func=_cmd_white)    

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(message)s",
    )

    if args.command is None:
        parser.print_help()
        print()
        print("Available presets:")
        for name, (r, g, b) in PRESETS.items():
            print(f"  {name:<10} rgb({r:>3}, {g:>3}, {b:>3})")
        return 0

    func: Callable[[argparse.Namespace], int] = args.func
    return func(args)


if __name__ == "__main__":
    sys.exit(main())
