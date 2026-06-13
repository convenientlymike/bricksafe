"""The byte-level artifact guard.

The most dangerous mistake in a mock-first control plane is letting a *placeholder* artifact — the
synthetic stub you build/test with when there's no real toolchain — reach a *real* device. A label
("source=real") is not enough: a label can be wrong, stale, or forged. So the guard inspects the
BYTES. A placeholder carries a magic header (or a ``{"placeholder": true}`` JSON marker); the gate
refuses to write a placeholder to a real device on the content, not the claim.

``stamp_placeholder`` is the single producer of that signature; ``is_placeholder`` is the single
recognizer. Keep them paired — both ingest and the flash path consult ``is_placeholder``.
"""

from __future__ import annotations

import hashlib
import json

#: The 12-byte magic prefixing a binary placeholder stub.
PLACEHOLDER_MAGIC = b"BRCKSAFE\x00PLC"


def stamp_placeholder(kind: str, version: str, *, as_json: bool = False) -> bytes:
    """Produce a deterministic placeholder artifact for ``(kind, version)`` — same inputs → same
    bytes (no clocks/randomness), so a rebuild is reproducible + diffable. Binary blobs carry the
    magic header; JSON artifacts carry a ``"placeholder": true`` marker."""
    if as_json:
        body = {"kind": kind, "version": version, "placeholder": True}
        return json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(f"{kind}:{version}".encode()).digest()
    return PLACEHOLDER_MAGIC + kind.encode()[:16].ljust(16, b"\x00") + \
        version.encode()[:16].ljust(16, b"\x00") + digest


def is_placeholder(data: bytes) -> bool:
    """True iff ``data`` IS a placeholder stub — a binary blob with the magic header, or a JSON
    object with ``"placeholder": true``. The single definition consulted before any real write,
    so a stub can never masquerade as real firmware and brick a device."""
    if not data:
        return False
    if data.startswith(PLACEHOLDER_MAGIC):
        return True
    try:
        obj = json.loads(data)
    except (ValueError, TypeError):
        return False
    return isinstance(obj, dict) and obj.get("placeholder") is True


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
