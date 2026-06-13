<div align="center">

# 🧱🛡️ bricksafe

**Never brick a device.** Safe-by-construction firmware writes — a tiny, dependency-free Python
library of the safety primitives a hardware control plane needs so a device write *can't* go wrong.

[![CI](https://github.com/convenientlymike/bricksafe/actions/workflows/ci.yml/badge.svg)](https://github.com/convenientlymike/bricksafe/actions/workflows/ci.yml)
&nbsp;[![License: MIT](https://img.shields.io/badge/License-MIT-8B5CF6.svg)](LICENSE)
&nbsp;![Python](https://img.shields.io/badge/python-3.10+-3776AB?logo=python&logoColor=white)
&nbsp;![Typed](https://img.shields.io/badge/typed-mypy%20strict-2563EB)
&nbsp;![Deps](https://img.shields.io/badge/runtime%20deps-0-22C55E)

<em>A flash that skips a backup, writes a placeholder to real hardware, clobbers an unexpected state,
or "succeeds" without reading back — is how you brick a board. bricksafe makes every one of those
impossible by construction.</em>

</div>

---

## Why

Writing firmware to real hardware is **irreversible and unforgiving**. The failure modes are always
the same, across FPGAs, MCUs, capture cards, and IoT fleets:

- you flash before capturing a backup → **no way back to as-shipped**;
- a *placeholder* stub (the synthetic artifact you build/test with when there's no real toolchain)
  reaches a **real** device → **brick**;
- a blind write clobbers a state you didn't expect → **corruption**;
- the write "succeeds" but you never read it back → **silent half-flash**;
- a real-device call **silently no-ops** because the hardware wasn't actually there → **you think
  you flashed, but you didn't**.

`bricksafe` is the distilled safety layer that closes all of them — extracted from a production
hardware control plane and made domain-neutral. One **write-gate** is the only path to a device
write, and a write must clear every gate or it is refused, loudly, with an audit trail.

## ✨ What it gives you

- 🚪 **One write-gate, eight checks.** `arm → rate-limit → backup-gate → placeholder-guard →
  read-before-write CAS → undo-snapshot → write → confirm-readback → audit`. Nothing else touches a
  device's raw `write`/`flash`.
- 💾 **Backup-before-write is a HARD gate.** A device can't be written until a **verified** backup of
  its current image exists — and "verified" means it passed a *restore-test* (re-read, re-hash),
  because a backup that can't be read back is not a backup. *Restore-to-as-shipped is always possible.*
- 🧬 **Byte-level placeholder guard.** A placeholder/synthetic stub is refused on its **bytes**, not
  a label — so a stub can never masquerade as real firmware and reach a real device.
- 🔁 **One-step undo + append-only audit.** Every write snapshots the pre-write bytes; every attempt
  (pass *or* refusal) is recorded with its reason.
- 📣 **Fail-loud real backends.** A real-device op **raises** until its transport is present — it
  never silently no-ops (the worst failure: thinking you flashed when you didn't).
- 🧪 **Mock-first, zero hardware.** A complete in-memory `MockDevice` runs the whole safety loop, so
  you build and test the entire control plane with no hardware — then real transports drop into the
  same gate unchanged.
- 🪶 **Zero runtime dependencies, `mypy --strict`, fully typed.**

## ▶️ Try it

```python
from bricksafe import BackupStore, WriteGate, MockDevice, stamp_placeholder

backups = BackupStore()
gate = WriteGate(backups)
dev = MockDevice()                       # in-memory device; swap for a real backend later

gate.write("dev0", dev, 0, b"firmware", "flash v1")
# ❌ NotArmedError — you must declare intent first

gate.arm("dev0", "flashing v1")
gate.write("dev0", dev, 0, b"firmware", "flash v1")
# ❌ NoVerifiedBackupError — no restore point exists yet

backups.capture("dev0", dev, length=64)  # read + archive the current image (restore-tested)
gate.write("dev0", dev, 0, stamp_placeholder("fw", "v1"), "flash")
# ❌ PlaceholderArtifactError — refused on the BYTES, never reaches the device

receipt = gate.write("dev0", dev, 0, b"\x7fELF...real firmware...", "flash v1")
assert receipt.confirmed is True         # written AND read back == written
gate.restore_last("dev0", dev)           # one-step undo, any time
```

Every refusal is a typed exception; every action is in `gate.audit`. Run the full demo:

```bash
python examples/demo.py
```

## 🏗 Architecture

```
                         ┌───────────────────────── WriteGate.write ─────────────────────────┐
  arm(reason) ──────────▶│ 1 armed?  2 rate-limit?  3 verified backup?  4 not a placeholder?  │
                         │ 5 CAS (read-before-write)  6 undo-snapshot  7 write  8 confirm-rb  │
                         └───────────────┬───────────────────────────────────┬───────────────┘
                                         │ refuse (typed error + audit)       │ WriteReceipt + audit
                                         ▼                                    ▼
            BackupStore.restorable()  is_placeholder(bytes)            WriteTarget.read/write
            (restore-tested backup)   (magic header / JSON marker)     (MockDevice | RealDevice…)
```

- **`engine.py`** — `WriteTarget` (read/write/backend) + `FlashEngine` (available/flash/readback) +
  the typed errors.
- **`gate.py`** — `WriteGate`: the one safe write path + undo + audit ledger.
- **`backup.py`** — `BackupStore`: capture (restore-tested) + `restorable()`.
- **`artifact.py`** — `is_placeholder` / `stamp_placeholder`: the byte-level guard.
- **`devices.py`** — `MockDevice` (in-memory, for tests) + `RealDevice` (fail-loud base for real
  transports).

A real deployment subclasses `RealDevice` (wire the transport behind `read`/`write`/`flash`, flip
`available()` when the hardware enumerates) and swaps `BackupStore` for a durable store — the gate
and all its guarantees are unchanged.

## 📦 Install

```bash
pip install bricksafe        # or: uv pip install bricksafe
```

From source:

```bash
git clone https://github.com/convenientlymike/bricksafe && cd bricksafe
uv venv && uv pip install -e ".[dev]"
pytest -q
```

**Supported OS:** pure Python, OS-independent (no shelling out, `pathlib`/stdlib only).

## 🔒 Security

`bricksafe` is defense-in-depth for *your* device writes; it ships **zero runtime dependencies** and
performs no network I/O. The guards are conservative by construction — when a check can't be proven
(unreadable readback, a missing backup), the gate **refuses** rather than assuming success. See
[SECURITY.md](SECURITY.md).

## License

MIT — see [LICENSE](LICENSE).

<div align="center"><sub>Distilled from a production hardware control plane. Domain-neutral and reusable for any FPGA / MCU / embedded / IoT fleet tool.</sub></div>