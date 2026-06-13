# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-06-12

### Added
- Initial release. The safe-by-construction write path for firmware/hardware control planes,
  distilled from a production hardware control plane and made domain-neutral.
- `WriteGate` — the one device-write path: `arm → rate-limit → backup-gate → placeholder-guard →
  read-before-write CAS → undo-snapshot → write → confirm-readback → audit`. Per-device undo stack
  + an append-only audit ledger.
- `BackupStore` — backup-before-write as a hard gate; `capture` runs a restore-test (re-read +
  re-hash) and `restorable()` re-verifies, so a stale/corrupt backup is treated as no backup.
- `is_placeholder` / `stamp_placeholder` — a byte-level guard so a placeholder/synthetic stub can
  never masquerade as real firmware and reach a real device.
- `MockDevice` (in-memory, runs the whole loop with zero hardware) + `RealDevice` (fail-loud base
  for real transports — every op raises until the hardware is present).
- Typed exceptions for every refusal; `mypy --strict` clean; zero runtime dependencies.
