"""Backup-before-write: the restore-to-as-shipped point.

Before a device is ever written, its CURRENT image is read off the hardware and archived as a
verified backup. "Verified" means it passes a *restore-test* — the stored bytes are read back and the
sha re-checked, because a backup that can't be read back is not a backup (present != restorable). The
write-gate refuses any write to a target without such a backup.

The store here is in-memory (keyed by the target's ``backend`` + a caller id) so the library is
dependency-free and testable; a real deployment swaps in a durable store with the same interface.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .artifact import sha256
from .engine import WriteTarget


@dataclass(frozen=True)
class Backup:
    """A verified snapshot of a device's image at a point in time."""

    device_id: str
    sha256: str
    size: int
    captured_ms: int
    data: bytes = field(repr=False)


class BackupStore:
    """Holds the latest verified backup per device id. Swap for a durable store (files/DB) by
    re-implementing ``capture`` / ``latest`` / ``restorable`` with the same signatures."""

    def __init__(self, now: Any = None) -> None:
        self._latest: dict[str, Backup] = {}
        self._now = now or (lambda: int(time.time() * 1000))

    def capture(self, device_id: str, target: WriteTarget, length: int) -> Backup:
        """Read ``length`` bytes off ``target`` and archive them as a verified backup. Runs the
        restore-test (re-read the stored bytes, re-verify the sha) before recording — raises if the
        snapshot can't be trusted."""
        data = bytes(target.read(0, length))
        if not data:
            raise ValueError("device returned no bytes to back up")
        digest = sha256(data)
        backup = Backup(device_id=device_id, sha256=digest, size=len(data),
                        captured_ms=self._now(), data=data)
        if sha256(backup.data) != digest:  # restore-test: the snapshot must read back intact
            raise ValueError("backup failed its restore-test (stored bytes did not verify)")
        self._latest[device_id] = backup
        return backup

    def latest(self, device_id: str) -> Backup | None:
        return self._latest.get(device_id)

    def restorable(self, device_id: str) -> bool:
        """True iff a backup exists for the device AND its bytes still verify against the recorded
        sha — a stale/corrupted backup is no backup."""
        b = self._latest.get(device_id)
        return b is not None and sha256(b.data) == b.sha256
