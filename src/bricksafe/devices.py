"""Reference device backends — a mock (in-memory, for tests + hardware-free development) and a
fail-loud real-device base (the seam real transports plug into).

The mock is a complete ``WriteTarget`` + ``FlashEngine`` whose byte space IS its state, so the whole
safety loop (CAS, backup, confirm-readback, undo) runs with zero hardware. The real base is the
opposite by design: until its transport is wired it is **unavailable** and every op **raises** —
because a real write that silently no-ops is the worst failure of all (it mock-masks a missing
device). Subclass ``RealDevice``, set ``_available``/the transport, and the same gate drives it.
"""

from __future__ import annotations

from .engine import DeviceUnavailableError, FlashEngine


class MockDevice(FlashEngine):
    """In-memory flashable device: a ``WriteTarget`` + ``FlashEngine`` over a byte bank. A ``lying``
    variant corrupts its readback so the gate's confirm sees a mismatch (exercises the unhappy path,
    not just the happy one)."""

    def __init__(self, backend: str = "mock", *, space: int = 4096, lie: bool = False) -> None:
        self._backend = backend
        self._space = bytearray(space)
        self._lie = lie

    @property
    def backend(self) -> str:
        return self._backend

    def read(self, addr: int, n: int) -> bytes:
        if self._lie:
            return bytes((self._space[addr + i] ^ 0xFF) & 0xFF for i in range(n))
        return bytes(self._space[addr:addr + n])

    def write(self, addr: int, data: bytes) -> int:
        self._space[addr:addr + len(data)] = data
        return len(data)

    def available(self) -> bool:
        return True

    def flash(self, slot: str, data: bytes) -> int:
        off = 0 if slot in ("active", "", None) else (int(slot) if str(slot).isdigit() else 0)
        return self.write(off, data)

    def readback(self, slot: str, n: int) -> bytes | None:
        off = 0 if slot in ("active", "", None) else (int(slot) if str(slot).isdigit() else 0)
        return self.read(off, n)


class RealDevice(FlashEngine):
    """Base for a real device backend. Lib/hardware-gated: ``available()`` is False and every
    read/write/flash RAISES ``DeviceUnavailableError`` until the transport is present. Subclass it,
    set ``_available`` (and the real transport behind read/write/flash) — the gate is unchanged."""

    backend: str = "real"
    _available: bool = False

    def available(self) -> bool:
        return self._available

    def _unavailable(self, op: str) -> DeviceUnavailableError:
        return DeviceUnavailableError(
            f"{self.backend} cannot {op}: no transport/hardware present — a real op never "
            "silently no-ops. Wire the transport + attach the device.")

    def read(self, addr: int, n: int) -> bytes:
        raise self._unavailable("read")

    def write(self, addr: int, data: bytes) -> int:
        raise self._unavailable("write")

    def flash(self, slot: str, data: bytes) -> int:
        raise self._unavailable("flash")
