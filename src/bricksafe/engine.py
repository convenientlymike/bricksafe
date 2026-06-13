"""The device-side primitives + the errors the write-gate raises.

``WriteTarget`` is the minimal contract a flashable device must satisfy — read, write, and a stable
``backend`` name. ``FlashEngine`` adds the slot-addressed flash/readback primitive. A device backend
implements both; the write-gate is the ONLY thing that calls the raw ``write``/``flash`` (everything
else goes through ``WriteGate.write``, which arms, rate-limits, reads-before-writing, requires a
verified backup, confirms the readback, audits, and records an undo).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable


class BrickSafeError(Exception):
    """Base for every refusal the safety layer raises."""


class NotArmedError(BrickSafeError):
    """A write was attempted while the gate was not armed for the target."""


class RateLimitedError(BrickSafeError):
    """Writes are arriving faster than the configured floor allows."""


class CasConflictError(BrickSafeError):
    """Read-before-write check failed: the device's current bytes are not what the caller
    expected, so the write would clobber an unexpected state."""


class NoVerifiedBackupError(BrickSafeError):
    """The hard gate: a target may not be written until a verified backup of its current
    image exists (restore-to-as-shipped must always be possible)."""


class PlaceholderArtifactError(BrickSafeError):
    """A placeholder / synthetic stub artifact was about to be written to a REAL device.
    Refused on the BYTES (not a label) so a stub can never masquerade as real firmware."""


class DeviceUnavailableError(BrickSafeError):
    """A real device op was attempted but the transport/hardware is not present. Fails LOUD —
    a real write never silently no-ops (that would mock-mask a missing device)."""


@runtime_checkable
class WriteTarget(Protocol):
    """The minimal flashable-device contract the write-gate operates on."""

    @property
    def backend(self) -> str:
        """A stable backend key (e.g. ``mock``, ``real_fpga``) — recorded in the audit ledger."""
        ...

    def read(self, addr: int, n: int) -> bytes:
        """Read ``n`` bytes at ``addr`` (the gate's CAS + confirm-readback + backup source)."""
        ...

    def write(self, addr: int, data: bytes) -> int:
        """Raw write — called ONLY by the write-gate. Returns bytes written."""
        ...


class FlashEngine(ABC):
    """A slot-addressed flash primitive. ``available()`` is True only when the device can really
    be flashed (a mock is always available; a real engine is False until its hardware is present)."""

    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    def flash(self, slot: str, data: bytes) -> int:
        """Write ``data`` to ``slot``. THE raw irreversible primitive — only via the write-gate."""

    def readback(self, slot: str, n: int) -> bytes | None:
        """Read ``n`` bytes back from ``slot`` to confirm a flash, or None if unreadable (the gate
        records that as ``confirmed=None`` — never 'verified'). Default: not readable."""
        return None
