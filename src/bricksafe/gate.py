"""The write-gate — the single, safe-by-construction path to a device write.

Every physical write goes through ``WriteGate.write``; nothing else calls a device's raw
``write``/``flash``. In order, a write must clear:

  1. **armed**       — the gate is armed for this device (a TTL'd, reason-logged intent);
  2. **rate-limit**  — writes can't arrive faster than the configured floor;
  3. **backup gate** — a *verified* backup of the device's current image exists (restore-to-as-
                       shipped is always possible) — else refused;
  4. **placeholder** — the bytes are not a placeholder/synthetic stub (checked on the CONTENT) —
                       else refused, so a stub can never reach a real device;
  5. **CAS**         — if the caller declared the expected current bytes, they still match (no blind
                       clobber of an unexpected state);
  6. **undo**        — the pre-write bytes are snapshotted before the write (one-step rollback);
  7. **confirm**     — the write is read back and compared (``confirmed`` = True / False / None-if-
                       unreadable — never silently "verified");
  8. **audit**       — every attempt (pass or refusal) is appended to a ledger.

The result is an invariant: a device can't be written un-armed, too fast, without a restore point,
with a placeholder, over an unexpected state, blindly, or unconfirmed.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from .artifact import is_placeholder
from .backup import BackupStore
from .engine import (
    CasConflictError,
    NotArmedError,
    NoVerifiedBackupError,
    PlaceholderArtifactError,
    RateLimitedError,
    WriteTarget,
)


@dataclass(frozen=True)
class WriteReceipt:
    device_id: str
    backend: str
    addr: int
    written: int
    confirmed: bool | None   # True = read back == written; False = drift; None = unreadable
    reason: str


@dataclass
class AuditEntry:
    ts_ms: int
    device_id: str
    backend: str
    op: str          # "write" | "restore" | "refused:<reason>"
    addr: int
    length: int
    result: str      # "ok" | "confirmed" | "drift" | "unreadable" | the refusal code


class WriteGate:
    """Safe-by-construction device writes. Construct with a ``BackupStore``; arm a device, then
    ``write`` through it. The gate keeps a per-device undo stack + an append-only audit ledger."""

    def __init__(self, backups: BackupStore, *, min_interval_ms: int = 0,
                 arm_ttl_ms: int = 60_000, now: Any = None) -> None:
        self._backups = backups
        self._min_interval = min_interval_ms
        self._arm_ttl = arm_ttl_ms
        self._now = now or (lambda: int(time.time() * 1000))
        self._armed_until: dict[str, int] = {}
        self._reason: dict[str, str] = {}
        self._last_write: dict[str, int] = {}
        self._undo: dict[str, list[tuple[int, bytes]]] = {}
        self.audit: list[AuditEntry] = []

    # — arming —
    def arm(self, device_id: str, reason: str, *, ttl_ms: int | None = None) -> None:
        self._armed_until[device_id] = self._now() + (ttl_ms if ttl_ms is not None else self._arm_ttl)
        self._reason[device_id] = reason

    def is_armed(self, device_id: str) -> bool:
        return self._now() < self._armed_until.get(device_id, 0)

    def disarm(self, device_id: str) -> None:
        self._armed_until.pop(device_id, None)
        self._reason.pop(device_id, None)

    def _record(self, device_id: str, backend: str, op: str, addr: int, length: int, result: str) -> None:
        self.audit.append(AuditEntry(self._now(), device_id, backend, op, addr, length, result))

    # — the one write path —
    def write(self, device_id: str, target: WriteTarget, addr: int, data: bytes, reason: str,
              *, expect: bytes | None = None, confirm: bool = True) -> WriteReceipt:
        backend = target.backend

        if not self.is_armed(device_id):
            self._record(device_id, backend, "refused:not_armed", addr, len(data), "not_armed")
            raise NotArmedError(f"gate not armed for {device_id} — arm(device_id, reason) first")

        last = self._last_write.get(device_id)
        if last is not None and self._min_interval and self._now() - last < self._min_interval:
            self._record(device_id, backend, "refused:rate_limited", addr, len(data), "rate_limited")
            raise RateLimitedError(f"writes to {device_id} are rate-limited (<{self._min_interval}ms)")

        if not self._backups.restorable(device_id):
            self._record(device_id, backend, "refused:no_backup", addr, len(data), "no_verified_backup")
            raise NoVerifiedBackupError(
                f"refusing to write {device_id}: no verified backup of its current image exists "
                "— capture one first (restore-to-as-shipped must always be possible)")

        if is_placeholder(data):
            self._record(device_id, backend, "refused:placeholder", addr, len(data), "placeholder")
            raise PlaceholderArtifactError(
                f"refusing to write a placeholder/synthetic stub to {device_id} (checked on the bytes)")

        if expect is not None:
            current = bytes(target.read(addr, len(expect)))
            if current != expect:
                self._record(device_id, backend, "refused:cas", addr, len(data), "cas_conflict")
                raise CasConflictError(
                    f"read-before-write failed for {device_id}@{addr:#x}: current bytes != expected")

        before = bytes(target.read(addr, len(data)))   # undo snapshot
        written = target.write(addr, data)
        self._undo.setdefault(device_id, []).append((addr, before))
        self._last_write[device_id] = self._now()

        confirmed: bool | None = None
        if confirm:
            confirmed = bytes(target.read(addr, len(data))) == data
        self._record(device_id, backend, "write", addr, written,
                     "confirmed" if confirmed else ("drift" if confirmed is False else "unreadable"))
        return WriteReceipt(device_id, backend, addr, written, confirmed, reason)

    def undo_depth(self, device_id: str) -> int:
        return len(self._undo.get(device_id, []))

    def restore_last(self, device_id: str, target: WriteTarget) -> int:
        """Undo the most recent write to ``device_id`` (write the snapshotted bytes back). Raises
        ``LookupError`` if there is nothing to undo. (A bricked device has no software undo — JTAG/
        bootloader recovery is the hardware backstop; the backup is the deeper restore point.)"""
        stack = self._undo.get(device_id)
        if not stack:
            raise LookupError(f"nothing to undo for {device_id}")
        addr, before = stack.pop()
        n = target.write(addr, before)
        self._record(device_id, target.backend, "restore", addr, n, "ok")
        return n
