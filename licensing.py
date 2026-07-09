from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, simpledialog
from typing import Any

try:
    import winreg
except ImportError:  # pragma: no cover - Windows-only module.
    winreg = None

import requests


API_HOST = os.environ.get("ZERNIX_LICENSE_API_HOST", os.environ.get("API_HOST", "127.0.0.1"))
API_PORT = os.environ.get("ZERNIX_LICENSE_API_PORT", os.environ.get("API_PORT", "8000"))
API_KEY = os.environ.get("ZERNIX_LICENSE_API_KEY", os.environ.get("API_KEY", "zernix-local-api-key"))
LICENSE_SERVER_URL = os.environ.get("ZERNIX_LICENSE_SERVER_URL", f"http://{API_HOST}:{API_PORT}/validate")
APP_NAME = "Zernix"
LICENSE_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
LICENSE_FILE = os.path.join(LICENSE_DIR, "license.txt")
HIDDEN_PROCESS_FLAGS = 0x08000000 if os.name == "nt" else 0
REQUEST_TIMEOUT_SECONDS = 10
DEMO_MODE_RESULT = "__DEMO_MODE__"
OFFLINE_ROLLBACK_RESULT = "__OFFLINE_ROLLBACK__"
_cached_hwid: str | None = None


def normalize_license_key(user_key: str) -> str:
    """Normalize keys copied from Telegram/chat without changing the server format."""
    key = (user_key or "").strip().upper()
    key = re.sub(r"\s+", "", key)
    return re.sub(r"[^A-Z0-9-]", "", key)


def get_hwid() -> str:
    """Return a stable machine identifier used to bind a license to this PC."""
    global _cached_hwid
    if _cached_hwid:
        return _cached_hwid

    override = _clean_hwid_value(os.environ.get("ZERNIX_HWID", ""))
    if override:
        _cached_hwid = override
        return _cached_hwid

    primary_uuid = _clean_hwid_value(
        _read_wmic_value("csproduct", "uuid")
        or _read_powershell_value("Win32_ComputerSystemProduct", "UUID")
    )
    if primary_uuid:
        _cached_hwid = primary_uuid
        return _cached_hwid

    parts = [
        _read_machine_guid(),
        _read_wmic_value("bios", "serialnumber") or _read_powershell_value("Win32_BIOS", "SerialNumber"),
        _read_wmic_value("baseboard", "serialnumber") or _read_powershell_value("Win32_BaseBoard", "SerialNumber"),
        _read_wmic_value("cpu", "processorid") or _read_powershell_value("Win32_Processor", "ProcessorId"),
        _read_wmic_value("diskdrive", "serialnumber") or _read_powershell_value("Win32_DiskDrive", "SerialNumber"),
    ]
    clean_parts = [_clean_hwid_value(part) for part in parts]
    clean_parts = [part for part in clean_parts if part]
    if not clean_parts:
        raise RuntimeError("Unable to read hardware ID: no stable hardware identifiers were returned.")

    digest = hashlib.sha256("|".join(clean_parts).encode("utf-8")).hexdigest().upper()[:24]
    _cached_hwid = "HWID-" + "-".join(digest[i : i + 4] for i in range(0, len(digest), 4))
    return _cached_hwid


def _read_wmic_value(alias: str, field: str) -> str:
    try:
        result = subprocess.run(
            ["wmic", alias, "get", field],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False,
            creationflags=HIDDEN_PROCESS_FLAGS,
        )
    except OSError:
        return ""

    if result.returncode != 0:
        return ""

    lines = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
    for line in lines:
        if line.lower() != field.lower():
            cleaned = _clean_hwid_value(line)
            if cleaned:
                return cleaned
    return ""


def _read_powershell_value(class_name: str, property_name: str) -> str:
    if os.name != "nt":
        return ""
    command = f"(Get-CimInstance -ClassName {class_name} -ErrorAction SilentlyContinue).{property_name}"
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False,
            timeout=4,
            creationflags=HIDDEN_PROCESS_FLAGS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    for line in (result.stdout or "").splitlines():
        cleaned = _clean_hwid_value(line)
        if cleaned:
            return cleaned
    return ""


def _read_machine_guid() -> str:
    if os.name != "nt" or winreg is None:
        return ""
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            return _clean_hwid_value(str(value))
    except OSError:
        return ""


def _clean_hwid_value(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9-]", "", (value or "").strip().upper())
    compact = cleaned.replace("-", "")
    invalid_values = {
        "",
        "UUID",
        "SERIALNUMBER",
        "PROCESSORID",
        "TOBEFILLEDBYOEM",
        "DEFAULTSTRING",
        "SYSTEMSERIALNUMBER",
        "NONE",
        "NULL",
        "UNKNOWN",
    }
    if compact in invalid_values or len(compact) < 6:
        return ""
    if set(compact) <= {"0"} or set(compact) <= {"F"}:
        return ""
    return cleaned


def check_license(user_key: str) -> tuple[bool, str]:
    """
    Validate a license key against the ZERNIX license server.

    Returns:
        (True, expiry_date) on success, or (False, error_message) on failure.
    """
    key = normalize_license_key(user_key)
    if not key:
        return False, "License key is required."

    try:
        hwid = get_hwid()
    except RuntimeError as exc:
        return False, str(exc)

    payload = {"key": key, "hwid": hwid}
    headers = {"X-API-Key": API_KEY}

    try:
        response = requests.post(
            LICENSE_SERVER_URL,
            json=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.exceptions.ConnectionError:
        return False, "No internet connection or license server is unreachable."
    except requests.exceptions.Timeout:
        return False, "License server request timed out. Please try again."
    except requests.exceptions.RequestException as exc:
        return False, f"License validation failed: {exc}"

    data = _safe_json(response)
    if response.status_code != 200:
        return False, _extract_error(data) or f"License server returned HTTP {response.status_code}."

    if _is_success_response(data):
        expiry_date = _extract_expiry(data) or "unknown"
        return True, expiry_date

    return False, _extract_error(data) or "License validation failed."


def read_saved_license_key() -> str:
    try:
        with open(LICENSE_FILE, "r", encoding="utf-8") as license_file:
            return license_file.read().strip()
    except OSError:
        return ""


def save_license_key(user_key: str) -> None:
    key = normalize_license_key(user_key)
    os.makedirs(LICENSE_DIR, exist_ok=True)
    with open(LICENSE_FILE, "w", encoding="utf-8") as license_file:
        license_file.write(key + "\n")
    _mark_hidden(LICENSE_DIR)
    _mark_hidden(LICENSE_FILE)


def validate_saved_license() -> tuple[bool, str]:
    saved_key = read_saved_license_key()
    if not saved_key:
        return False, "License key is not saved."
    return check_license(saved_key)


def is_demo_mode_enabled() -> bool:
    return os.environ.get("ZERNIX_PORTFOLIO_MODE") == "1" or os.environ.get("ZERNIX_SKIP_LICENSE") == "1"


def ensure_license_or_exit(parent: tk.Misc | None = None) -> str:
    """
    Validate the saved license, or prompt once for a key and save it.

    The app exits immediately when validation fails.
    Set environment variable ZERNIX_PORTFOLIO_MODE=1 (or run with --demo)
    to open the full UI without contacting the license server.
    Set environment variable ZERNIX_OFFLINE_ROLLBACK=1 (or run with --safe-rollback)
    to skip online validation and open the UI for rollback/tools only.
    """
    if is_demo_mode_enabled():
        return DEMO_MODE_RESULT

    if os.environ.get("ZERNIX_OFFLINE_ROLLBACK") == "1":
        try:
            messagebox.showinfo(
                "ZERNIX — safe rollback / безопасный откат",
                "License check is skipped (offline). Use System Reset and Network/VPN repair, then restart ZERNIX normally when online.\n\n"
                "Проверка лицензии отключена. Используйте откат системы и восстановление сети; после появления интернета запустите программу обычно.",
                parent=parent,
            )
        except Exception:
            pass
        return OFFLINE_ROLLBACK_RESULT

    saved_key = read_saved_license_key()
    if saved_key:
        ok, result = check_license(saved_key)
        if ok:
            return result
        messagebox.showerror("License validation failed", result, parent=parent)
        sys.exit(1)

    owns_root = parent is None
    root = parent
    if owns_root:
        root = tk.Tk()
        root.withdraw()

    try:
        key = simpledialog.askstring("ZERNIX License", "Enter your license key:", parent=root)
        if not key:
            messagebox.showerror("License required", "A valid license key is required to start ZERNIX.", parent=root)
            sys.exit(1)

        ok, result = check_license(key)
        if not ok:
            messagebox.showerror("License validation failed", result, parent=root)
            sys.exit(1)

        try:
            save_license_key(key)
        except OSError as exc:
            messagebox.showerror("License save failed", f"License is valid but could not be saved: {exc}", parent=root)
            sys.exit(1)

        return result
    finally:
        if owns_root and root is not None:
            root.destroy()


def _safe_json(response: requests.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _is_success_response(data: dict[str, Any]) -> bool:
    return bool(
        data.get("success") is True
        or data.get("valid") is True
        or str(data.get("status", "")).lower() in {"ok", "success", "valid"}
    )


def _extract_error(data: dict[str, Any]) -> str:
    for field in ("error", "message", "detail"):
        value = data.get(field)
        if value:
            return str(value)
    return ""


def _extract_expiry(data: dict[str, Any]) -> str:
    for field in ("expiry", "expiry_date", "expires_at", "expires", "subscription_expires"):
        value = data.get(field)
        if value:
            return str(value)
    return ""


def _mark_hidden(path: str) -> None:
    if os.name != "nt" or not path:
        return
    try:
        subprocess.run(
            ["attrib", "+h", path],
            capture_output=True,
            text=True,
            check=False,
            creationflags=HIDDEN_PROCESS_FLAGS,
        )
    except OSError:
        pass
