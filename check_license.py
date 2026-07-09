#!/usr/bin/env python3
"""Small diagnostic helper for checking a license key from the project root.

Usage:
    python check_license.py "YOUR-LICENSE-KEY"
"""

from __future__ import annotations

import sys

from licensing import API_KEY, LICENSE_SERVER_URL, check_license, get_hwid


def _mask_secret(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def main() -> None:
    key = " ".join(sys.argv[1:]).strip() if len(sys.argv) > 1 else input("Paste license key: ").strip()
    hwid = get_hwid()
    ok, result = check_license(key)

    print(f"HWID: {hwid}")
    print(f"License server: {LICENSE_SERVER_URL}")
    print(f"API key: {_mask_secret(API_KEY)}")
    print(f"Validation: {'OK' if ok else 'FAILED'}")
    print(f"Response: {result}")


if __name__ == "__main__":
    main()
