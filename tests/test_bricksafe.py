"""Every safety invariant of the write-gate, proven by a negative control + the happy path.

The contract: a device can't be written un-armed, too fast, without a verified backup, with a
placeholder, over an unexpected state (CAS), blindly (undo), or unconfirmed — and a real device op
fails loud rather than silently no-op.
"""

from __future__ import annotations

import pytest

from bricksafe import (
    BackupStore,
    CasConflictError,
    DeviceUnavailableError,
    MockDevice,
    NotArmedError,
    NoVerifiedBackupError,
    PlaceholderArtifactError,
    RateLimitedError,
    RealDevice,
    WriteGate,
    is_placeholder,
    stamp_placeholder,
)


class _Clock:
    """A deterministic clock so rate-limit / arm-TTL are testable without real time."""

    def __init__(self) -> None:
        self.t = 1_000

    def __call__(self) -> int:
        return self.t


def _gate(min_interval_ms: int = 0):
    clock = _Clock()
    return WriteGate(BackupStore(now=clock), min_interval_ms=min_interval_ms, now=clock), clock


def _backed_up(gate: WriteGate, dev: MockDevice, device_id: str = "dev0") -> None:
    """Arm + capture a verified backup so a write can proceed (the realistic setup)."""
    gate.arm(device_id, "test session")
    gate._backups.capture(device_id, dev, length=64)


REAL = b"\x7fELF" + b"\xaa" * 60   # a non-placeholder "real" payload


class TestHappyPath:
    def test_write_confirms_and_audits(self):
        gate, _ = _gate()
        dev = MockDevice()
        _backed_up(gate, dev)
        r = gate.write("dev0", dev, 0, REAL, "flash v1")
        assert r.written == len(REAL) and r.confirmed is True
        assert bytes(dev.read(0, len(REAL))) == REAL
        assert any(e.op == "write" and e.result == "confirmed" for e in gate.audit)

    def test_lying_device_reports_unconfirmed_not_verified(self):
        gate, _ = _gate()
        dev = MockDevice(lie=True)   # corrupts its readback
        _backed_up(gate, dev)
        r = gate.write("dev0", dev, 0, REAL, "flash")
        assert r.confirmed is False   # drift detected, never silently "verified"


class TestGatesBite:
    def test_unarmed_write_refused(self):
        gate, _ = _gate()
        dev = MockDevice()
        gate._backups.capture("dev0", dev, 64)   # backed up but NOT armed
        with pytest.raises(NotArmedError):
            gate.write("dev0", dev, 0, REAL, "x")

    def test_no_backup_refused(self):
        gate, _ = _gate()
        dev = MockDevice()
        gate.arm("dev0", "x")   # armed but NO backup
        with pytest.raises(NoVerifiedBackupError):
            gate.write("dev0", dev, 0, REAL, "x")

    def test_placeholder_refused_on_the_bytes(self):
        gate, _ = _gate()
        dev = MockDevice()
        _backed_up(gate, dev)
        stub = stamp_placeholder("bitstream", "v1")
        assert is_placeholder(stub)
        with pytest.raises(PlaceholderArtifactError):
            gate.write("dev0", dev, 0, stub, "x")

    def test_cas_conflict_refused(self):
        gate, _ = _gate()
        dev = MockDevice()
        _backed_up(gate, dev)
        # the device is all zeros; declaring a non-matching expectation must refuse
        with pytest.raises(CasConflictError):
            gate.write("dev0", dev, 0, REAL, "x", expect=b"\x99\x99")

    def test_rate_limited(self):
        gate, clock = _gate(min_interval_ms=1000)
        dev = MockDevice()
        _backed_up(gate, dev)
        gate.write("dev0", dev, 0, REAL, "first")
        clock.t += 100   # well under the 1000ms floor
        with pytest.raises(RateLimitedError):
            gate.write("dev0", dev, 0, REAL, "too soon")

    def test_arm_expires(self):
        gate, clock = _gate()
        dev = MockDevice()
        gate.arm("dev0", "x", ttl_ms=500)
        gate._backups.capture("dev0", dev, 64)
        clock.t += 600   # past the TTL
        assert gate.is_armed("dev0") is False
        with pytest.raises(NotArmedError):
            gate.write("dev0", dev, 0, REAL, "x")


class TestUndo:
    def test_restore_last_reverts_the_write(self):
        gate, _ = _gate()
        dev = MockDevice()
        _backed_up(gate, dev)
        gate.write("dev0", dev, 0, REAL, "flash")
        assert gate.undo_depth("dev0") == 1
        gate.restore_last("dev0", dev)
        assert bytes(dev.read(0, len(REAL))) == b"\x00" * len(REAL)   # back to pre-write
        assert gate.undo_depth("dev0") == 0

    def test_restore_with_nothing_raises(self):
        gate, _ = _gate()
        with pytest.raises(LookupError):
            gate.restore_last("dev0", MockDevice())


class TestBackup:
    def test_capture_is_restorable_and_verifies(self):
        store = BackupStore()
        dev = MockDevice()
        dev.write(0, b"factory-image")
        b = store.capture("dev0", dev, length=13)
        assert b.size == 13 and store.restorable("dev0") is True

    def test_empty_read_is_not_a_backup(self):
        store = BackupStore()
        with pytest.raises(ValueError, match="no bytes"):
            store.capture("dev0", MockDevice(space=0), length=0)


class TestRealDeviceFailsLoud:
    def test_real_device_unavailable_and_raises(self):
        dev = RealDevice()
        assert dev.available() is False
        for op in (lambda: dev.read(0, 4), lambda: dev.write(0, b"x"), lambda: dev.flash("active", b"x")):
            with pytest.raises(DeviceUnavailableError):
                op()


class TestPlaceholderGuard:
    def test_detects_binary_and_json_markers_and_spares_real(self):
        assert is_placeholder(stamp_placeholder("k", "v")) is True
        assert is_placeholder(stamp_placeholder("k", "v", as_json=True)) is True
        assert is_placeholder(REAL) is False
        assert is_placeholder(b"") is False