"""A runnable tour of bricksafe — each safety gate refusing, then a clean confirmed flash + undo.

    python examples/demo.py
"""

from __future__ import annotations

from bricksafe import (
    BackupStore,
    BrickSafeError,
    MockDevice,
    WriteGate,
    stamp_placeholder,
)

REAL_FIRMWARE = b"\x7fELF" + b"\xaa" * 60  # a non-placeholder payload standing in for real firmware


def attempt(label: str, fn) -> None:
    try:
        result = fn()
        print(f"  ✓ {label}: {result}")
    except BrickSafeError as exc:
        print(f"  ✗ {label}: {type(exc).__name__} — {exc}")


def main() -> None:
    backups = BackupStore()
    gate = WriteGate(backups, min_interval_ms=0)
    dev = MockDevice()
    print("bricksafe demo — every gate refuses until its precondition is met\n")

    print("→ write before arming:")
    attempt("flash", lambda: gate.write("dev0", dev, 0, REAL_FIRMWARE, "flash v1"))

    print("\n→ armed, but no backup yet:")
    gate.arm("dev0", "flashing v1")
    attempt("flash", lambda: gate.write("dev0", dev, 0, REAL_FIRMWARE, "flash v1"))

    print("\n→ backup captured (restore-tested), but a PLACEHOLDER artifact:")
    backups.capture("dev0", dev, length=64)
    attempt("flash placeholder", lambda: gate.write("dev0", dev, 0, stamp_placeholder("fw", "v1"), "flash"))

    print("\n→ real firmware, but a stale read-before-write expectation (CAS):")
    attempt("flash w/ wrong expect",
            lambda: gate.write("dev0", dev, 0, REAL_FIRMWARE, "flash", expect=b"\x99\x99"))

    print("\n→ all gates satisfied — a clean, confirmed flash:")
    receipt = gate.write("dev0", dev, 0, REAL_FIRMWARE, "flash v1")
    print(f"  ✓ wrote {receipt.written}B · confirmed={receipt.confirmed}")

    print("\n→ one-step undo back to the pre-write bytes:")
    gate.restore_last("dev0", dev)
    print(f"  ✓ restored — device now reads {bytes(dev.read(0, 4))!r}…")

    print(f"\naudit ledger ({len(gate.audit)} entries):")
    for e in gate.audit:
        print(f"  [{e.op:>18}] {e.device_id}@{e.addr:#x} len={e.length} → {e.result}")


if __name__ == "__main__":
    main()