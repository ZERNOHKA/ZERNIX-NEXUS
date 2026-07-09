from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


SIGNATURE_ALGORITHM = "RSASSA-PKCS1v15-SHA256"


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def integrity_message(exe_name: str, sha256: str, size: int) -> bytes:
    return f"{exe_name}|{sha256.lower()}|{int(size)}".encode("utf-8")


def resolve_private_key(cli_path: str | None) -> Path:
    private_key = cli_path or os.environ.get("ZERNIX_MANIFEST_PRIVATE_KEY") or "license_private.pem"
    return Path(private_key).resolve()


def sign_payload(message: bytes, private_key_path: Path) -> str:
    private_key_bytes = private_key_path.read_bytes()
    password_value = os.environ.get("ZERNIX_MANIFEST_PRIVATE_KEY_PASSWORD")
    password = password_value.encode("utf-8") if password_value else None
    private_key = serialization.load_pem_private_key(
        private_key_bytes,
        password=password,
        backend=default_backend(),
    )
    signature = private_key.sign(message, padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signature).decode("ascii")


def main() -> None:
    parser = argparse.ArgumentParser(description="Write signed ZERNIX executable integrity manifest.")
    parser.add_argument("exe_path", type=Path, help="Path to the built executable.")
    parser.add_argument("manifest_path", type=Path, help="Path to write zernix.integrity.json.")
    parser.add_argument("--private-key", dest="private_key", default=None, help="Manifest signing private key.")
    args = parser.parse_args()

    exe_path = args.exe_path.resolve()
    if not exe_path.is_file():
        raise FileNotFoundError(f"Built executable not found: {exe_path}")

    private_key_path = resolve_private_key(args.private_key)
    if not private_key_path.is_file():
        raise FileNotFoundError(
            f"Manifest signing key not found: {private_key_path}. "
            "Set ZERNIX_MANIFEST_PRIVATE_KEY or place license_private.pem outside release output."
        )

    sha256 = compute_sha256(exe_path)
    size = exe_path.stat().st_size
    exe_name = exe_path.name
    signature = sign_payload(integrity_message(exe_name, sha256, size), private_key_path)

    payload = {
        "exe": exe_name,
        "sha256": sha256,
        "size": size,
        "signature_algorithm": SIGNATURE_ALGORITHM,
        "signature": signature,
    }
    args.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Integrity manifest written: {args.manifest_path}")


if __name__ == "__main__":
    main()
