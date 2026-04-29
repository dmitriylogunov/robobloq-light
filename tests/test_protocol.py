"""
Tests for the pure protocol module.

Captured packets from real device runs are used as ground truth wherever
possible. These tests run without hardware.
"""

from __future__ import annotations

import pytest

from roboblq_light import protocol
from roboblq_light.protocol import (
    PacketIdGenerator,
    Section,
    build_set_brightness,
    build_set_section_led,
    build_solid_color,
    build_turn_off,
    checksum,
    decode_packet,
)


# ---------------------------------------------------------------------------
# Checksum
# ---------------------------------------------------------------------------

class TestChecksum:
    def test_simple_sum(self):
        assert checksum(b"\x01\x02\x03") == 6

    def test_wraps_at_256(self):
        assert checksum(b"\xff\x01") == 0
        assert checksum(b"\xff\xff") == 254

    def test_empty(self):
        assert checksum(b"") == 0


# ---------------------------------------------------------------------------
# Sequence ID generator
# ---------------------------------------------------------------------------

class TestPacketIdGenerator:
    def test_starts_at_2_after_first_call(self):
        # JS: id starts at 1, next() returns id+1 -> 2 on first call
        gen = PacketIdGenerator()
        assert gen.next() == 2

    def test_wraps_to_1_after_254(self):
        gen = PacketIdGenerator(start=253)
        assert gen.next() == 254
        # Next call would set id=255 which triggers the wrap
        assert gen.next() == 1

    def test_independent_generators(self):
        a = PacketIdGenerator()
        b = PacketIdGenerator()
        a.next(); a.next(); a.next()
        assert b.next() == 2  # b not affected by a


# ---------------------------------------------------------------------------
# Captured packets — ground truth from real device runs
# ---------------------------------------------------------------------------
#
# These hex strings are the exact packets the device accepted in testing.
# We use them to lock the protocol implementation against regression.

CAPTURED_BRIGHTNESS_50 = bytes.fromhex("52 42 07 02 87 32 56".replace(" ", ""))
CAPTURED_BRIGHTNESS_100 = bytes.fromhex("52 42 07 02 87 64 88".replace(" ", ""))
CAPTURED_TURN_OFF       = bytes.fromhex("52 42 06 02 97 33".replace(" ", ""))
CAPTURED_RED            = bytes.fromhex("52 42 0B 02 86 00 FF 00 00 FF 25".replace(" ", ""))


class TestCapturedPacketsRoundTrip:
    """Each captured packet must decode cleanly with valid checksum."""

    @pytest.mark.parametrize("name,packet", [
        ("brightness_50",  CAPTURED_BRIGHTNESS_50),
        ("brightness_100", CAPTURED_BRIGHTNESS_100),
        ("turn_off",       CAPTURED_TURN_OFF),
        ("red",            CAPTURED_RED),
    ])
    def test_decodes(self, name, packet):
        decoded = decode_packet(packet)
        assert decoded["header"] == b"RB"
        assert decoded["length"] == len(packet)


# ---------------------------------------------------------------------------
# Builder reproducibility
# ---------------------------------------------------------------------------
#
# We can't pin the ID byte (it's a counter) but we *can* lock everything else.

def _strip_id(packet: bytes) -> bytes:
    """Replace the ID byte (offset 3) with 0 so we can compare without state."""
    return packet[:3] + b"\x00" + packet[4:]


class TestBuilders:
    def test_brightness_50_matches_capture(self):
        gen = PacketIdGenerator(start=1)  # next() -> 2, matches capture
        pkt = build_set_brightness(50, id_gen=gen)
        assert pkt == CAPTURED_BRIGHTNESS_50

    def test_brightness_100_matches_capture(self):
        gen = PacketIdGenerator(start=1)
        pkt = build_set_brightness(100, id_gen=gen)
        assert pkt == CAPTURED_BRIGHTNESS_100

    def test_turn_off_matches_capture(self):
        gen = PacketIdGenerator(start=1)
        pkt = build_turn_off(id_gen=gen)
        assert pkt == CAPTURED_TURN_OFF

    def test_solid_red_matches_capture(self):
        gen = PacketIdGenerator(start=1)
        pkt = build_solid_color(255, 0, 0, id_gen=gen)
        assert pkt == CAPTURED_RED

    def test_brightness_clamps_high(self):
        gen = PacketIdGenerator(start=1)
        pkt = build_set_brightness(9999, id_gen=gen)
        # value byte should be 100, not the raw input
        assert pkt[5] == 100

    def test_brightness_clamps_low(self):
        gen = PacketIdGenerator(start=1)
        pkt = build_set_brightness(-50, id_gen=gen)
        assert pkt[5] == 0


class TestSection:
    def test_default_flag_is_255(self):
        s = Section(0, 1, 2, 3)
        assert s.flag == 0xFF

    def test_rejects_out_of_range(self):
        with pytest.raises(ValueError):
            Section(0, 256, 0, 0)
        with pytest.raises(ValueError):
            Section(0, -1, 0, 0)


class TestMultiSection:
    def test_packet_length_scales_with_section_count(self):
        gen = PacketIdGenerator(start=1)
        pkt1 = build_set_section_led([Section(0, 0, 0, 0)], id_gen=gen)
        gen2 = PacketIdGenerator(start=1)
        pkt3 = build_set_section_led(
            [Section(0, 1, 2, 3), Section(1, 4, 5, 6), Section(2, 7, 8, 9)],
            id_gen=gen2,
        )
        # 6 + 5*N
        assert len(pkt1) == 6 + 5 * 1
        assert len(pkt3) == 6 + 5 * 3

    def test_empty_section_list_rejected(self):
        with pytest.raises(ValueError):
            build_set_section_led([])


class TestDecoder:
    def test_rejects_bad_header(self):
        bad = bytes.fromhex("XXXX0702873256".replace("X", "0"))
        bad = b"\x00\x00" + bad[2:]
        with pytest.raises(ValueError, match="header"):
            decode_packet(bad)

    def test_rejects_bad_checksum(self):
        bad = CAPTURED_BRIGHTNESS_50[:-1] + b"\x00"
        with pytest.raises(ValueError, match="hecksum"):
            decode_packet(bad)

    def test_rejects_length_mismatch(self):
        # Take a real packet but lie about its length
        bad = bytes(CAPTURED_BRIGHTNESS_50)
        bad = bad[:2] + bytes([99]) + bad[3:]
        with pytest.raises(ValueError, match="ength"):
            decode_packet(bad)
