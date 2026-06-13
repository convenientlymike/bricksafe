# Security policy

`bricksafe` is a defense-in-depth library for *your* device writes. It ships **zero runtime
dependencies** and performs **no network I/O**.

## Design posture

The guards are conservative by construction: when a safety condition cannot be *proven* — an
unreadable confirm-readback, a missing or unverifiable backup, a placeholder detected in the bytes —
the write-gate **refuses** rather than assuming success. A real-device backend **fails loud** (raises)
rather than silently no-op. The library never weakens these defaults silently.

## Reporting a vulnerability

If you find a way to drive a device write that *should* have been refused (a gate bypass), please open
a private security advisory on the GitHub repository, or email convenientlymike@gmail.com. Please
include a minimal reproduction. We'll acknowledge within a few days.

## Supported versions

The latest minor release on `main` receives fixes.
