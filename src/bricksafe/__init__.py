"""bricksafe — never brick a device: safe-by-construction firmware writes.

A small, dependency-free Python library of the safety primitives a firmware/hardware control plane
needs so a device write can't go wrong:

  - a single **write-gate** (arm → rate-limit → backup-gate → placeholder-guard → read-before-write
    CAS → undo-snapshot → write → confirm-readback → audit);
  - **backup-before-write** as a hard gate (restore-to-as-shipped is always possible);
  - a **byte-level placeholder guard** (a synthetic stub can never masquerade as real firmware);
  - **fail-loud** real-device backends (a real write never silently no-ops) + an in-memory mock so
    the whole loop is testable with zero hardware.

Distilled from a production hardware control plane; domain-neutral and reusable for any FPGA / MCU /
embedded / IoT fleet tool.
"""

from __future__ import annotations

from .artifact import PLACEHOLDER_MAGIC, is_placeholder, sha256, stamp_placeholder
from .backup import Backup, BackupStore
from .devices import MockDevice, RealDevice
from .engine import (
    BrickSafeError,
    CasConflictError,
    DeviceUnavailableError,
    FlashEngine,
    NotArmedError,
    NoVerifiedBackupError,
    PlaceholderArtifactError,
    RateLimitedError,
    WriteTarget,
)
from .gate import AuditEntry, WriteGate, WriteReceipt

__version__ = "0.1.0"

__all__ = [
    "WriteGate", "WriteReceipt", "AuditEntry",
    "BackupStore", "Backup",
    "MockDevice", "RealDevice",
    "FlashEngine", "WriteTarget",
    "is_placeholder", "stamp_placeholder", "sha256", "PLACEHOLDER_MAGIC",
    "BrickSafeError", "NotArmedError", "RateLimitedError", "CasConflictError",
    "NoVerifiedBackupError", "PlaceholderArtifactError", "DeviceUnavailableError",
    "__version__",
]
