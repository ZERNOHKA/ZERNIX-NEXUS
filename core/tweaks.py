import os
import re
import subprocess
import winreg
import base64
import json
import shutil
import sys
import hashlib
import time
import psutil
import platform
import wmi
import ctypes
from ctypes import wintypes
try:
    import win32api
except Exception:
    win32api = None
try:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
except Exception:
    default_backend = None
    hashes = None
    serialization = None
    padding = None

BACKUP_FILE = "settings_backup.json"
HIDDEN_PROCESS_FLAGS = 0x08000000
INTEGRITY_FILE = "zernix.integrity.json"
INTEGRITY_SIGNATURE_ALGORITHM = "RSASSA-PKCS1v15-SHA256"
INTEGRITY_PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA2QPiWQAr3GyOAQUn1oE5
INvI/fSseHTbUO+n28R6NgAwMtwkLhSbapLMEw/LnkQpEAumb5wiiX8iwbvmRXCa
nMKc4LcSV3DaUZJwMpYnA5NYsbWbOJ/kwaoEqAxg+IjvJpu2jekV8hN+aH9WjRic
hNd11p5rIso3IzEq+QAzKbWm+unB+rx7ridQYFLjNY6Bb3/pFAdZuC1txYsqqgCj
lIAZ7zdJhatJ8SJuFGMyRk/xQ/jPR03LWKAeWVsOEhNNe+wHTrdimt97qUdKGtsZ
TyrdN/2j6jjcEA+gRLWqegTU+dBD3AiugVetBTPmSWXB56TmYI60um1h74B0siUW
OQIDAQAB
-----END PUBLIC KEY-----
"""
_HWND_BROADCAST = 0xFFFF
_WM_SETTINGCHANGE = 0x001A
_SMTO_ABORTIFHUNG = 0x0002
_STATUS_CACHE = {"secure_boot": (None, 0.0), "kb5077181": (None, 0.0)}

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
try:
    _psapi = ctypes.WinDLL("psapi.dll", use_last_error=True)
    _EmptyWorkingSet = _psapi.EmptyWorkingSet
except Exception:
    _EmptyWorkingSet = None

_OpenProcess = _kernel32.OpenProcess
_OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_OpenProcess.restype = wintypes.HANDLE

if _EmptyWorkingSet:
    _EmptyWorkingSet.argtypes = [wintypes.HANDLE]
    _EmptyWorkingSet.restype = wintypes.BOOL

_CloseHandle = _kernel32.CloseHandle
_CloseHandle.argtypes = [wintypes.HANDLE]
_CloseHandle.restype = wintypes.BOOL

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_PROCESS_SET_QUOTA = 0x0100
_SUSPICIOUS_DEBUG_TOOLS = {
    "ollydbg.exe",
    "x64dbg.exe",
    "x32dbg.exe",
    "ida64.exe",
    "ida.exe",
    "idaq.exe",
    "idaq64.exe",
    "windbg.exe",
    "ghidra.exe",
    "dnspy.exe",
    "cheatengine.exe",
    "procmon.exe",
    "procexp.exe",
}

_REG_ROOT_TAG = {
    winreg.HKEY_LOCAL_MACHINE: "HKLM",
    winreg.HKEY_CURRENT_USER: "HKCU",
}

CRITICAL_SERVICE_EXCLUSIONS = ("adsk", "autodesk", "flexnet", "adobe")
ANTICHEAT_SERVICE_EXCLUSIONS = ("faceit", "easyanticheat", "battleye", "bedaisy", "vgc", "vgk")

# Never stop/disable through gaming optimizer — breaks VPN/WMI/Discord/adapters.
NETWORK_CRITICAL_SERVICE_NAMES = frozenset(
    {
        "Winmgmt",
        "IKEEXT",
        "iphlpsvc",
        "WinHttpAutoProxySvc",
        "PolicyAgent",
        "BFE",
        "Dnscache",
        "Dhcp",
        "NlaSvc",
        "netprofm",
        "Wcmsvc",
        "RasMan",
        "SstpSvc",
        "RemoteAccess",
        "lmhosts",
        "CryptSvc",
        "EventLog",
    }
)


def _zernix_appdata_dir() -> str:
    path = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Zernix")
    os.makedirs(path, exist_ok=True)
    return path


def _user_prefs_path() -> str:
    return os.path.join(_zernix_appdata_dir(), "user_prefs.json")


def _load_user_prefs() -> dict:
    try:
        with open(_user_prefs_path(), "r", encoding="utf-8") as fp:
            data = json.load(fp)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def preserve_virtualization_enabled() -> bool:
    return bool(_load_user_prefs().get("preserve_virtualization"))


def set_preserve_virtualization_enabled(value: bool) -> None:
    prefs = _load_user_prefs()
    prefs["preserve_virtualization"] = bool(value)
    try:
        with open(_user_prefs_path(), "w", encoding="utf-8") as fp:
            json.dump(prefs, fp, ensure_ascii=False, indent=2)
    except OSError:
        pass


CRITICAL_PROCESS_EXCLUSIONS = {
    "revit.exe",
    "3dsmax.exe",
    "acad.exe",
    "inventor.exe",
    "maya.exe",
    "photoshop.exe",
    "illustrator.exe",
    "afterfx.exe",
    "premiere pro.exe",
}
SAFEGUARD_WARNING = (
    "Внимание: обнаружен запущенный рабочий софт Autodesk/Adobe. "
    "Закройте рабочий софт перед оптимизацией"
)
CPU_PARKING_MIN_CORES = "0cc5b647-c1df-4637-891a-dec35c318583"
CPU_PARKING_MAX_CORES = "ea062031-0e34-4ff1-9b6d-eb1059334028"
CS2_2026_LAUNCH_OPTIONS = (
    "-high -novid -nojoy -allow_third_party_software "
    "-mainthreadpriority 2 +thread_pool_option 0 "
    "+engine_low_latency_sleep_after_client_tick true"
)


def _safe_physical_cores():
    return psutil.cpu_count(logical=False) or max(1, (psutil.cpu_count(logical=True) or 2) // 2)


def _parse_intel_generation(cpu_name: str) -> int:
    if not cpu_name:
        return 0
    name = cpu_name.lower()
    m = re.search(r"i[3579]-\s*(\d{4,5})", name)
    if not m:
        return 0
    model = m.group(1)
    if len(model) == 5:
        return int(model[:2])
    return int(model[0])


def _is_intel_hybrid_cpu(cpu_name: str) -> bool:
    name = (cpu_name or "").lower()
    if "intel" not in name:
        return False
    gen = _parse_intel_generation(cpu_name)
    if gen < 12:
        return False
    physical = _safe_physical_cores()
    logical = psutil.cpu_count(logical=True) or physical
    # Typical Intel hybrid CPUs have mixed HT behavior and are not logical=physical*2.
    return logical != physical * 2


def _is_windows_11() -> bool:
    try:
        return platform.release() == "10" and int(platform.version().split(".")[-1]) >= 22000
    except Exception:
        return False


def _is_high_end_or_hybrid_cpu() -> bool:
    logical = psutil.cpu_count(logical=True) or 0
    cpu_name = ""
    try:
        cpu_name = wmi.WMI().Win32_Processor()[0].Name.strip()
    except Exception:
        cpu_name = platform.processor() or ""
    return logical > 8 or _is_intel_hybrid_cpu(cpu_name)


def _get_monitor_refresh_rate() -> int:
    if win32api:
        try:
            devmode = win32api.EnumDisplaySettings(None, -1)
            hz = int(getattr(devmode, "DisplayFrequency", 0) or 0)
            if hz > 0:
                return hz
        except Exception:
            pass
    try:
        c = wmi.WMI()
        ctrls = c.Win32_VideoController()
        if ctrls:
            hz = int(getattr(ctrls[0], "CurrentRefreshRate", 0) or 0)
            if hz > 0:
                return hz
    except Exception:
        pass
    return 0


def _get_cpu_name() -> str:
    try:
        return wmi.WMI().Win32_Processor()[0].Name.strip()
    except Exception:
        return platform.processor() or ""


def _safe_logical_cores() -> int:
    return psutil.cpu_count(logical=True) or _safe_physical_cores()


def _safe_ram_gb() -> int:
    try:
        return max(4, round(psutil.virtual_memory().total / (1024**3)))
    except Exception:
        return 8


def is_admin():
    try:
        if bool(ctypes.windll.shell32.IsUserAnAdmin()):
            return True
    except Exception:
        pass
    try:
        result = subprocess.run(
            "net session",
            shell=True,
            capture_output=True,
            text=True,
            check=False,
            creationflags=HIDDEN_PROCESS_FLAGS,
        )
        return result.returncode == 0
    except Exception:
        return False


def is_debugger_present() -> bool:
    try:
        if bool(ctypes.windll.kernel32.IsDebuggerPresent()):
            return True
    except Exception:
        pass
    try:
        kernel32 = ctypes.windll.kernel32
        is_present = ctypes.c_bool(False)
        current_process = kernel32.GetCurrentProcess()
        ok = kernel32.CheckRemoteDebuggerPresent(current_process, ctypes.byref(is_present))
        if ok and bool(is_present.value):
            return True
    except Exception:
        pass
    return False


def has_suspicious_debug_tools() -> bool:
    try:
        for proc in psutil.process_iter(["name"]):
            name = str((proc.info or {}).get("name") or "").lower()
            if name in _SUSPICIOUS_DEBUG_TOOLS:
                return True
    except Exception:
        pass
    return False


def _compute_file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _integrity_message(exe_name: str, sha256: str, size: int) -> bytes:
    return f"{exe_name}|{sha256.lower()}|{int(size)}".encode("utf-8")


def _verify_integrity_signature(payload: dict, exe_name: str, sha256: str, size: int) -> bool:
    if not all((serialization, default_backend, hashes, padding)):
        return False
    signature_algorithm = str(payload.get("signature_algorithm") or "")
    if signature_algorithm != INTEGRITY_SIGNATURE_ALGORITHM:
        return False
    signature_b64 = str(payload.get("signature") or "").strip()
    if not signature_b64:
        return False
    try:
        signature = base64.b64decode(signature_b64, validate=True)
        public_key = serialization.load_pem_public_key(INTEGRITY_PUBLIC_KEY_PEM, backend=default_backend())
        public_key.verify(
            signature,
            _integrity_message(exe_name, sha256, size),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False


def verify_exe_integrity(min_exe_size_bytes: int = 2 * 1024 * 1024) -> bool:
    # Dev mode (python main.py): skip strict checks.
    if not getattr(sys, "frozen", False):
        return True
    exe_path = sys.executable
    try:
        if not os.path.isfile(exe_path):
            return False
        file_size = os.path.getsize(exe_path)
        if file_size < int(min_exe_size_bytes):
            return False
    except Exception:
        return False

    integrity_path = os.path.join(os.path.dirname(exe_path), INTEGRITY_FILE)
    if not os.path.isfile(integrity_path):
        return False

    try:
        with open(integrity_path, "r", encoding="utf-8") as file_obj:
            payload = json.load(file_obj)
        expected_exe = str(payload.get("exe") or "").strip()
        expected_sha256 = str(payload.get("sha256") or "").strip().lower()
        expected_size = int(payload.get("size") or 0)
        if expected_exe and expected_exe != os.path.basename(exe_path):
            return False
        if expected_size != file_size or not expected_sha256:
            return False
        actual_sha256 = _compute_file_sha256(exe_path).lower()
        if actual_sha256 != expected_sha256:
            return False
        return _verify_integrity_signature(payload, os.path.basename(exe_path), expected_sha256, expected_size)
    except Exception:
        return False

def get_system_info():
    """Collect hardware data displayed on the system dashboard."""
    try:
        def _clean_cpu_name(raw_name: str) -> str:
            cleaned = (raw_name or "").strip()
            cleaned = cleaned.replace("(R)", "").replace("(TM)", "")
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            if len(cleaned) > 25:
                cleaned = re.sub(r"\s*@\s*[\d.,]+\s*GHz.*$", "", cleaned, flags=re.IGNORECASE).strip()
            return cleaned or "Нет данных"

        def _get_all_gpu_names() -> str:
            try:
                res = subprocess.run(
                    "wmic path win32_VideoController get name",
                    shell=True,
                    capture_output=True,
                    text=True,
                    check=False,
                    creationflags=HIDDEN_PROCESS_FLAGS,
                )
                lines = [ln.strip() for ln in (res.stdout or "").splitlines() if ln.strip()]
                gpu_list = []
                for ln in lines:
                    low = ln.lower()
                    if low == "name":
                        continue
                    if ln not in gpu_list:
                        gpu_list.append(ln)
                if gpu_list:
                    return " + ".join(gpu_list)
            except Exception:
                pass

            try:
                controllers = wmi.WMI().Win32_VideoController()
                names = []
                for ctrl in controllers:
                    name = str(getattr(ctrl, "Name", "") or "").strip()
                    if name and name not in names:
                        names.append(name)
                if names:
                    return " + ".join(names)
            except Exception:
                pass
            return "Нет данных"

        c = wmi.WMI()
        raw_cpu = c.Win32_Processor()[0].Name.strip()
        cpu = _clean_cpu_name(raw_cpu)
        gpu_name = _get_all_gpu_names()

        ram = f"{round(psutil.virtual_memory().total / (1024**3))} GB"

        os_ver = f"{platform.system()} {platform.release()}"
        if platform.release() == "10" and int(platform.version().split(".")[-1]) >= 22000:
            os_ver = "Windows 11"

        return {"os": os_ver, "cpu": cpu, "gpu": gpu_name, "ram": ram}
    except Exception:
        return {"os": "Error", "cpu": "Error", "gpu": "Error", "ram": "Error"}

def _backup_read_value(root, path, name):
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_READ) as key:
            val, typ = winreg.QueryValueEx(key, name)
        return val, typ
    except Exception:
        return None, None

def _backup_store(data, root, path, name):
    val, typ = _backup_read_value(root, path, name)
    if val is None:
        return
    tag = _REG_ROOT_TAG.get(root)
    if not tag:
        return
    data[f"{tag}|{path}|{name}"] = {"value": val, "type": typ}

def create_full_backup():
    """Создание точки восстановления реестра"""
    keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Policies\Microsoft\Windows\DataCollection", "AllowTelemetry"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Power\PowerThrottling", "PowerThrottlingOff"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\PriorityControl", "Win32PrioritySeparation"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\DeviceGuard", "EnableVirtualizationBasedSecurity"),
        (winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", "MenuShowDelay"),
        (winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", "ForegroundLockTimeout"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile", "NetworkThrottlingIndex"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile", "SystemResponsiveness"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games", "GPU Priority"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games", "Priority"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games", "Scheduling Category"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games", "SFIO Priority"),
        (winreg.HKEY_CURRENT_USER, r"System\GameConfigStore", "GameDVR_Enabled"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\GameBar", "AllowAutoGameMode"),
        (winreg.HKEY_CURRENT_USER, r"Control Panel\Mouse", "MouseSpeed"),
        (winreg.HKEY_CURRENT_USER, r"Control Panel\Mouse", "MouseThreshold1"),
        (winreg.HKEY_CURRENT_USER, r"Control Panel\Mouse", "MouseThreshold2"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem", "NtfsDisableLastAccessUpdate"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem", "LongPathsEnabled"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management", "DisablePagingExecutive"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management", "LargeSystemCache"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\PriorityControl", "IRQPriority"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\DiagTrack", "Start"),
    ]
    data = {}
    for root, path, name in keys:
        _backup_store(data, root, path, name)

    try:
        with open(BACKUP_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return "✅ Бэкап создан! Теперь можно безопасно бустить."
    except OSError as e:
        return f"❌ Не удалось записать бэкап: {e}"

def optimize_system_all():
    """Apply core quick-performance bundle: Smart Priority (22), Ultimate Performance, per-interface TCP registry."""
    if not is_admin():
        return "❌ Ошибка! Запустите программу от имени Администратора!"
    try:
        priority_status = apply_smart_priority_control()
        power_status = enable_ultimate_performance()
        network_status = apply_zernix_network_registry()
        return f"🚀 System optimization completed. {priority_status} | {power_status} | {network_status}"
    except Exception as e:
        return f"❌ Ошибка буста: {e}"


def _run_cmd(command: str):
    return subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        check=False,
        creationflags=HIDDEN_PROCESS_FLAGS,
    )


def _broadcast_system_change():
    """Notify Windows shell/services about setting updates without reboot."""
    try:
        user32 = ctypes.windll.user32
        user32.SendMessageTimeoutW(
            _HWND_BROADCAST,
            _WM_SETTINGCHANGE,
            0,
            "Policy",
            _SMTO_ABORTIFHUNG,
            200,
            None,
        )
    except Exception:
        pass


def check_vbs_status():
    """Return VBS/Memory Integrity registry status."""
    path = r"SYSTEM\CurrentControlSet\Control\DeviceGuard"
    value = _read_reg_dword(winreg.HKEY_LOCAL_MACHINE, path, "EnableVirtualizationBasedSecurity", None)
    if value is None:
        return None, "[ZERNIX] VBS status unavailable."
    enabled = int(value) != 0
    return enabled, ("[ZERNIX] VBS is enabled." if enabled else "[ZERNIX] VBS is disabled.")


def disable_vbs_integrity():
    """Disable VBS by setting DeviceGuard flag to 0."""
    if preserve_virtualization_enabled():
        return (
            "[ZERNIX] VBS / Memory Integrity toggle skipped — "
            "«Developer / keep Hyper-V & virtualization» is enabled in Presets."
        )
    if not is_admin():
        return "❌ VBS toggle requires admin rights."
    try:
        ok, rp = _ensure_restore_point_before_registry_changes()
        if not ok:
            return rp
        with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\DeviceGuard") as k:
            winreg.SetValueEx(k, "EnableVirtualizationBasedSecurity", 0, winreg.REG_DWORD, 0)
        _broadcast_system_change()
        return f"[ZERNIX] VBS disabled (EnableVirtualizationBasedSecurity=0). | {rp}"
    except Exception as e:
        return f"❌ VBS disable failed: {e}"


def disable_dynamic_tick():
    """Disable Dynamic Tick for lower timer wake latency (bcdedit). Faceit-safe subset only — never nointegritychecks/testsSigning."""
    if not is_admin():
        return "❌ Dynamic Tick tweak requires admin rights."
    try:
        result = _run_cmd("bcdedit /set disabledynamictick yes")
        if result.returncode == 0:
            return "[ZERNIX] Dynamic Tick disabled."
        details = (result.stderr or result.stdout or "").strip()
        return f"⚠️ Dynamic Tick tweak failed: {details or 'unknown error'}"
    except Exception as e:
        return f"❌ Dynamic Tick tweak failed: {e}"


def detect_problematic_kb5077181():
    """Detect problematic cumulative update KB5077181."""
    try:
        cmd = (
            'powershell -NoProfile -ExecutionPolicy Bypass -Command '
            '"if (Get-HotFix -Id KB5077181 -ErrorAction SilentlyContinue) { Write-Output 1 } else { Write-Output 0 }"'
        )
        res = _run_cmd(cmd)
        text = f"{res.stdout}\n{res.stderr}".strip()
        detected = "1" in text
        return detected, ("Detected problematic Windows update (KB5077181)" if detected else "KB5077181 not detected")
    except Exception:
        return False, "KB5077181 check unavailable"


def apply_realtime_priority_mode():
    """Apply real-time priority bias for gaming and cs2.exe when running."""
    if not is_admin():
        return "❌ Realtime priority mode requires admin rights."
    try:
        changed = []
        games_task = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games"
        with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, games_task) as key:
            winreg.SetValueEx(key, "GPU Priority", 0, winreg.REG_DWORD, 8)
            winreg.SetValueEx(key, "Priority", 0, winreg.REG_DWORD, 8)
            winreg.SetValueEx(key, "Scheduling Category", 0, winreg.REG_SZ, "High")
        changed.append("MMCSS Games priority=Realtime bias")

        for proc in psutil.process_iter(["name"]):
            name = str((proc.info or {}).get("name") or "").lower()
            if name == "cs2.exe":
                try:
                    proc.nice(psutil.REALTIME_PRIORITY_CLASS)
                    changed.append("cs2.exe priority=Realtime")
                except Exception:
                    changed.append("cs2.exe priority unchanged")
                break
        _broadcast_system_change()
        return "[ZERNIX] Realtime priority mode applied: " + ", ".join(changed) + "."
    except Exception as e:
        return f"❌ Realtime priority mode failed: {e}"


def create_system_restore_point():
    """Force-create Windows restore point before risky tweaks."""
    if not is_admin():
        return "❌ Ошибка: для создания точки восстановления нужны права администратора."
    try:
        # Allow immediate restore-point creation even if one was created recently.
        _run_cmd(
            'powershell -NoProfile -ExecutionPolicy Bypass -Command '
            '"New-Item -Path \'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\SystemRestore\' '
            '-Force | Out-Null; '
            'Set-ItemProperty -Path \'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\SystemRestore\' '
            '-Name \'SystemRestorePointCreationFrequency\' -Type DWord -Value 0"'
        )
        cmd = (
            'powershell -NoProfile -ExecutionPolicy Bypass -Command '
            '"Checkpoint-Computer -Description \'ZERNIX_Experimental\' -RestorePointType MODIFY_SETTINGS"'
        )
        res = _run_cmd(cmd)
        if res.returncode == 0:
            return "✅ Restore Point создан: ZERNIX_Experimental."
        details = (res.stderr or res.stdout or "").strip()
        return f"⚠️ Restore Point не создан: {details or 'неизвестная ошибка'}"
    except Exception as e:
        return f"❌ Ошибка создания Restore Point: {e}"


def get_cpu_temperature_c():
    """Best-effort CPU temp read via WMI; returns None when unavailable."""
    try:
        sensors = wmi.WMI(namespace="root\\wmi").MSAcpi_ThermalZoneTemperature()
        values = []
        for s in sensors:
            raw = int(getattr(s, "CurrentTemperature", 0) or 0)
            if raw > 0:
                values.append((raw / 10.0) - 273.15)
        if values:
            return round(max(values), 1)
    except Exception:
        pass
    try:
        probes = wmi.WMI().Win32_TemperatureProbe()
        values = []
        for p in probes:
            raw = int(getattr(p, "CurrentReading", 0) or 0)
            if raw > 0:
                values.append(float(raw))
        if values:
            return round(max(values), 1)
    except Exception:
        pass
    return None


def check_cpu_thermal_safety(limit_c: float = 80.0):
    temp_c = get_cpu_temperature_c()
    if temp_c is None:
        return True, "ℹ️ Температура CPU недоступна (датчик/WMI не предоставил данные)."
    if temp_c > limit_c:
        return (
            False,
            "⚠️ Внимание! Ваш процессор перегрет. Экстремальная оптимизация может привести к падению FPS",
        )
    return True, f"✅ Температура CPU в норме: {temp_c}°C."


def run_experimental_tweak_safely(tweak_callable, tweak_name: str = "Experimental tweak"):
    """
    Mandatory safety pipeline for Experimental/Extreme tweaks:
    1) force restore point
    2) thermal safety check
    3) execute tweak if safe
    """
    restore_msg = create_system_restore_point()
    if restore_msg.startswith("❌") or restore_msg.startswith("⚠️"):
        restore_msg = f"Restore point skipped: {restore_msg}"
    is_safe, thermal_msg = check_cpu_thermal_safety()
    if not is_safe:
        return f"{tweak_name}: blocked. {thermal_msg}"
    try:
        result = tweak_callable()
    except Exception as e:
        result = f"❌ {tweak_name} failed: {e}"
    return f"{restore_msg} | {thermal_msg} | {result}"


def _ensure_restore_point_before_registry_changes():
    """Best-effort forced restore point before registry edits."""
    try:
        msg = create_system_restore_point()
        if msg.startswith("❌"):
            return True, f"Restore point skipped: {msg}"
        return True, msg
    except Exception as e:
        return True, f"Restore point skipped: {e}"


def apply_smart_priority_control(forced_value: int = None):
    """
    Smart Priority Control:
    - CS2 2026 scheduler profile -> 22 (decimal)
    """
    blocked = _safeguard_blocks_tweaks()
    if blocked:
        return blocked
    if not is_admin():
        return "❌ Smart Priority Control requires admin rights."
    try:
        ok, rp = _ensure_restore_point_before_registry_changes()
        if not ok:
            return rp
        if forced_value is not None:
            value = int(forced_value)
        else:
            value = 22
        with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\PriorityControl") as k:
            winreg.SetValueEx(k, "Win32PrioritySeparation", 0, winreg.REG_DWORD, int(value))
        _broadcast_system_change()
        return f"[ZERNIX] Smart Priority Control applied: Win32PrioritySeparation={value}. | {rp}"
    except Exception as e:
        return f"❌ Smart Priority Control failed: {e}"


def _measure_quick_ping_ms(host: str = "1.1.1.1") -> int:
    try:
        res = _run_cmd(f"ping -n 1 -w 900 {host}")
        text = f"{res.stdout}\n{res.stderr}"
        match = re.search(r"(?:time|время)\s*[=<]?\s*(\d+)\s*(?:ms|мс)", text, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    except Exception:
        pass
    return 45


def apply_cs2_network_presets(ping_type):
    """
    CS2 Sub-Tick Optimizer.
    ping_type can be:
    - int/float ping in ms
    - "auto" to detect quickly
    """
    try:
        if isinstance(ping_type, (int, float)):
            ping_ms = int(ping_type)
        elif str(ping_type).strip().lower() == "auto":
            ping_ms = _measure_quick_ping_ms()
        else:
            ping_ms = int(str(ping_type).strip())
    except Exception:
        ping_ms = 45

    if ping_ms < 30:
        interp = "0.015625"
        ratio = "1"
    elif ping_ms > 60:
        interp = "0.03125"
        ratio = "2"
    else:
        interp = "0.015625"
        ratio = "1"

    cfg_dir = find_cs2_cfg_directory()
    if not cfg_dir:
        return "⚠️ CS2 network presets skipped: cfg folder not found."

    autoexec_path = os.path.join(cfg_dir, "autoexec.cfg")
    try:
        body = ""
        if os.path.isfile(autoexec_path):
            with open(autoexec_path, "r", encoding="utf-8", errors="ignore") as f:
                body = f.read()
        lines = {
            "cl_interp": f"cl_interp {interp}",
            "cl_interp_ratio": f"cl_interp_ratio {ratio}",
            "cl_net_buffer_ticks": "cl_net_buffer_ticks 0",
            "engine_low_latency_sleep_after_client_tick": "engine_low_latency_sleep_after_client_tick true",
        }
        for key, line in lines.items():
            if re.search(rf"^{re.escape(key)}\s+.*$", body, flags=re.MULTILINE):
                body = re.sub(rf"^{re.escape(key)}\s+.*$", line, body, flags=re.MULTILINE)
            else:
                if body and not body.endswith("\n"):
                    body += "\n"
                body += line + "\n"
        with open(autoexec_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        return (
            f"[ZERNIX] CS2 network presets applied for {ping_ms}ms: "
            f"cl_interp={interp}, cl_interp_ratio={ratio}, sub-tick sync enabled."
        )
    except Exception as e:
        return f"❌ CS2 network presets failed: {e}"


def _cfg_upsert_line(body: str, key: str, line: str) -> str:
    pattern = rf"^{re.escape(key)}\s+.*$"
    if re.search(pattern, body, flags=re.MULTILINE):
        return re.sub(pattern, line, body, flags=re.MULTILINE)
    if body and not body.endswith("\n"):
        body += "\n"
    return body + line + "\n"


def _cfg_upsert_entry(body: str, key: str, line: str) -> str:
    if str(key).startswith("__pattern__:"):
        pattern = str(key).split(":", 1)[1]
        if re.search(pattern, body, flags=re.MULTILINE):
            return re.sub(pattern, line, body, flags=re.MULTILINE)
        if body and not body.endswith("\n"):
            body += "\n"
        return body + line + "\n"
    return _cfg_upsert_line(body, key, line)


def _critical_exclusion_running() -> bool:
    try:
        for proc in psutil.process_iter(["name"]):
            name = str((proc.info or {}).get("name") or "").lower()
            if name in CRITICAL_PROCESS_EXCLUSIONS:
                return True
    except Exception:
        pass
    return False


def _safeguard_blocks_tweaks() -> str:
    return SAFEGUARD_WARNING if _critical_exclusion_running() else ""


def apply_cs2_competitive_2026_cfg():
    """
    Apply current CS2 competitive cfg values while avoiding Autodesk licensing conflicts.
    """
    blocked = _safeguard_blocks_tweaks()
    if blocked:
        return blocked

    cfg_dir = find_cs2_cfg_directory()
    if not cfg_dir:
        return "⚠️ CS2 competitive cfg skipped: cfg folder not found."

    autoexec_path = os.path.join(cfg_dir, "autoexec.cfg")
    lines = {
        "rate": "rate 786432",
        "cl_interp": "cl_interp 0",
        "cl_interp_ratio": "cl_interp_ratio 1",
        "cl_net_buffer_ticks": "cl_net_buffer_ticks 0",
        "r_low_latency": "r_low_latency 2",
        "r_player_visibility_mode": "r_player_visibility_mode 1",
        "setting.csm_quality_level": "setting.csm_quality_level 3",
    }
    try:
        body = ""
        if os.path.isfile(autoexec_path):
            with open(autoexec_path, "r", encoding="utf-8", errors="ignore") as f:
                body = f.read()
        for key, line in lines.items():
            body = _cfg_upsert_entry(body, key, line)
        with open(autoexec_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        return "[ZERNIX] CS2 competitive 2026 cfg applied: rate/interp/reflex/contrast/shadows."
    except Exception as e:
        return f"❌ CS2 competitive 2026 cfg failed: {e}"


def _write_cs2_autoexec_lines(lines: dict, success_message: str):
    blocked = _safeguard_blocks_tweaks()
    if blocked:
        return blocked

    cfg_dir = find_cs2_cfg_directory()
    if not cfg_dir:
        return "⚠️ CS2 cfg folder not found."

    autoexec_path = os.path.join(cfg_dir, "autoexec.cfg")
    try:
        body = ""
        if os.path.isfile(autoexec_path):
            with open(autoexec_path, "r", encoding="utf-8", errors="ignore") as f:
                body = f.read()
        for key, line in lines.items():
            body = _cfg_upsert_entry(body, key, line)
        with open(autoexec_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        return success_message
    except Exception as e:
        return f"❌ CS2 autoexec update failed: {e}"


def apply_zernix_audio_pro():
    """Apply Source 2 spatial audio commands for footsteps and voice mute bind."""
    lines = {
        "snd_headphone_eq": "snd_headphone_eq 1",
        "snd_spatialize_lerp": "snd_spatialize_lerp 0.8",
        "__pattern__:^bind\\s+\"v\"\\s+\"voice_modenable_toggle\"$": 'bind "v" "voice_modenable_toggle"',
    }
    return _write_cs2_autoexec_lines(lines, "[ZERNIX] Audio Pro applied: crisp EQ, spatial L/R, voice mute bind.")

def apply_zernix_network_registry():
    """Apply low-latency TCP/MMCSS registry settings for CS2."""
    blocked = _safeguard_blocks_tweaks()
    if blocked:
        return blocked
    if not is_admin():
        return "❌ Network registry optimization requires admin rights."

    try:
        changed = 0
        interfaces_path = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, interfaces_path, 0, winreg.KEY_READ) as root_key:
            index = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(root_key, index)
                except OSError:
                    break
                index += 1
                subpath = interfaces_path + "\\" + subkey_name
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subpath, 0, winreg.KEY_READ) as read_key:
                        has_ip = False
                        for value_name in ("DhcpIPAddress", "IPAddress"):
                            try:
                                value, _ = winreg.QueryValueEx(read_key, value_name)
                                if str(value).strip() and str(value).strip() not in ("0.0.0.0", "[]"):
                                    has_ip = True
                                    break
                            except OSError:
                                continue
                    if not has_ip:
                        continue
                    with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, subpath) as write_key:
                        winreg.SetValueEx(write_key, "TcpAckFrequency", 0, winreg.REG_DWORD, 1)
                        winreg.SetValueEx(write_key, "TCPNoDelay", 0, winreg.REG_DWORD, 1)
                    changed += 1
                except OSError:
                    continue

        with winreg.CreateKey(
            winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"
        ) as key:
            # Safer default-adjacent value — 0xFFFFFFFF has been associated with brittle networking on some setups.
            winreg.SetValueEx(key, "NetworkThrottlingIndex", 0, winreg.REG_DWORD, 10)
            winreg.SetValueEx(key, "SystemResponsiveness", 0, winreg.REG_DWORD, 20)

        _broadcast_system_change()
        return f"[ZERNIX] Network registry optimized: TcpAckFrequency/TCPNoDelay on {changed} interface(s); NetworkThrottlingIndex=10 (conservative)."
    except Exception as e:
        return f"❌ Network registry optimization failed: {e}"


def detect_hybrid_core_topology():
    """Detect likely Intel hybrid topology (P/E cores) and recommendation."""
    try:
        cpu_name = ""
        try:
            cpu_name = wmi.WMI().Win32_Processor()[0].Name.strip()
        except Exception:
            cpu_name = platform.processor() or ""
        hybrid = _is_intel_hybrid_cpu(cpu_name)
        logical = psutil.cpu_count(logical=True) or 0
        physical = _safe_physical_cores()
        recommendation = (
            "Рекомендуется параметр запуска Steam: +thread_pool_option 0"
            if hybrid
            else "Гибридная топология не обнаружена."
        )
        return {
            "hybrid": bool(hybrid),
            "logical": logical,
            "physical": physical,
            "recommendation": recommendation,
            "launch_flag": "+thread_pool_option 0" if hybrid else "",
        }
    except Exception:
        return {"hybrid": False, "logical": 0, "physical": 0, "recommendation": "Не удалось определить топологию CPU.", "launch_flag": ""}


def get_thread_pool_recommendation():
    try:
        info = detect_hybrid_core_topology()
        if info.get("hybrid"):
            return f"🧠 Hybrid CPU detected. Add Steam launch option: {info.get('launch_flag')}."
        return "ℹ️ Hybrid CPU topology not detected."
    except Exception as e:
        return f"⚠️ Thread pool recommendation unavailable: {e}"


def get_secure_boot_status():
    """Read Secure Boot state via PowerShell Confirm-SecureBootUEFI."""
    try:
        res = _run_cmd(
            'powershell -NoProfile -ExecutionPolicy Bypass -Command '
            '"try { Confirm-SecureBootUEFI } catch { $null }"'
        )
        text = (res.stdout or "").strip().lower()
        if "true" in text:
            return True, "Secure Boot ON"
        if "false" in text:
            return False, "Secure Boot OFF: Возможен низкий Trust Factor в VAC Live"
    except Exception:
        pass
    return None, "Secure Boot status unavailable"


def apply_pro_telemetry():
    """Enable advanced CS2 telemetry HUD."""
    cfg_dir = find_cs2_cfg_directory()
    if not cfg_dir:
        return "⚠️ Pro Telemetry skipped: CS2 cfg folder not found."
    path = os.path.join(cfg_dir, "autoexec.cfg")
    lines = [
        "cl_hud_telemetry_frametime_show 2",
        "cl_hud_telemetry_ping_show 2",
        "cl_hud_telemetry_net_misdelivery_show 2",
        "cl_hud_telemetry_serverrecvmargin_graph_show 1",
    ]
    try:
        body = ""
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                body = f.read()
        for line in lines:
            key = line.split(" ", 1)[0]
            if re.search(rf"^{re.escape(key)}\s+.*$", body, flags=re.MULTILINE):
                body = re.sub(rf"^{re.escape(key)}\s+.*$", line, body, flags=re.MULTILINE)
            else:
                if body and not body.endswith("\n"):
                    body += "\n"
                body += line + "\n"
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        return "📊 Pro Telemetry enabled in CS2 autoexec."
    except Exception as e:
        return f"❌ Pro Telemetry failed: {e}"


def enable_ultimate_performance():
    if not is_admin():
        return "❌ Ultimate Performance: нужен Админ."
    guid = "e9a42b02-d5df-448d-aa00-03f14749eb61"
    _run_cmd(f"powercfg -duplicatescheme {guid}")
    res = _run_cmd(f"powercfg -setactive {guid}")
    if res.returncode == 0:
        return "⚡ Электропитание: Ultimate Performance активирован."
    return "⚠️ Ultimate Performance: схема не активирована."


def apply_usb_latency_tweaks():
    if not is_admin():
        return "❌ USB tweaks: нужен Админ."
    try:
        path = r"SYSTEM\CurrentControlSet\Control\USB\USBFlags"
        key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, path)
        winreg.SetValueEx(key, "DisableSelectiveSuspend", 0, winreg.REG_DWORD, 1)
        winreg.CloseKey(key)
        return "🖱️ USB Selective Suspend отключен."
    except Exception as e:
        return f"❌ Ошибка USB tweaks: {e}"


def apply_visual_tweaks():
    try:
        desk = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop")
        winreg.SetValueEx(desk, "MinAnimate", 0, winreg.REG_SZ, "0")
        winreg.CloseKey(desk)

        dwm = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        winreg.SetValueEx(dwm, "EnableTransparency", 0, winreg.REG_DWORD, 0)
        winreg.CloseKey(dwm)
        return "🎨 Визуальные эффекты и прозрачность отключены."
    except Exception as e:
        return f"❌ Ошибка visual tweaks: {e}"


def apply_system_stability_tweaks():
    try:
        if not is_admin():
            return "❌ System Stability tweaks require admin rights."

        dwm_key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\Dwm")
        winreg.SetValueEx(dwm_key, "OverlayTestMode", 0, winreg.REG_DWORD, 5)
        winreg.CloseKey(dwm_key)

        graphics_key = winreg.CreateKey(
            winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers"
        )
        winreg.SetValueEx(graphics_key, "HwSchMode", 0, winreg.REG_DWORD, 2)
        winreg.CloseKey(graphics_key)
        _broadcast_system_change()
        return "✅ System Stability tweaks applied (restart recommended)."
    except Exception as e:
        return f"❌ System Stability tweaks failed: {e}"


def set_max_performance_visuals():
    """Disable animations and transparency to reduce UI overhead."""
    try:
        desk = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop")
        winreg.SetValueEx(desk, "MinAnimate", 0, winreg.REG_SZ, "0")
        winreg.SetValueEx(desk, "UserPreferencesMask", 0, winreg.REG_BINARY, b"\x90\x12\x03\x80\x10\x00\x00\x00")
        winreg.CloseKey(desk)

        adv = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects")
        winreg.SetValueEx(adv, "VisualFXSetting", 0, winreg.REG_DWORD, 2)
        winreg.CloseKey(adv)

        personalize = winreg.CreateKey(
            winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        )
        winreg.SetValueEx(personalize, "EnableTransparency", 0, winreg.REG_DWORD, 0)
        winreg.CloseKey(personalize)
        return "🎨 Visuals: animations and transparency disabled."
    except Exception as e:
        return f"❌ Visuals optimization failed: {e}"

def optimize_network():
    if not is_admin():
        return "❌ Ошибка сети (нужен Админ)"
    try:
        cmds = [
            "netsh int tcp set global autotuninglevel=normal",
            "netsh int tcp set global rss=enabled",
            "netsh int tcp set global fastopen=enabled",
        ]
        ok = 0
        errors = []
        for c in cmds:
            result = _run_cmd(c)
            if result.returncode == 0:
                ok += 1
            else:
                errors.append((result.stderr or result.stdout or c).strip())
        if ok == len(cmds):
            return "🌐 Сеть: TCP-профиль оптимизирован."
        return f"⚠️ Сеть: применено частично ({ok}/{len(cmds)}). {errors[0] if errors else ''}".strip()
    except Exception as e:
        return f"❌ Ошибка настройки сети: {e}"

def _get_steam_install_path():
    candidates = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam"),
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
    ]
    for hroot, subkey in candidates:
        try:
            key = winreg.OpenKey(hroot, subkey, 0, winreg.KEY_READ)
            path, _ = winreg.QueryValueEx(key, "InstallPath")
            winreg.CloseKey(key)
            path = os.path.normpath(os.path.expandvars(str(path)))
            if path and os.path.isdir(path):
                return path
        except OSError:
            continue
    return None

def _steam_library_roots(steam_path):
    roots = []
    if steam_path:
        roots.append(steam_path)
    for rel in (r"config\libraryfolders.vdf", r"steamapps\libraryfolders.vdf"):
        if not steam_path:
            break
        vdf = os.path.join(steam_path, rel)
        if not os.path.isfile(vdf):
            continue
        try:
            with open(vdf, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
            for m in re.finditer(r'"path"\s+"([^"]+)"', text):
                raw = m.group(1).replace("\\\\", "\\")
                p = os.path.normpath(raw)
                if p and p not in roots:
                    roots.append(p)
        except OSError:
            continue
        break
    return roots

def find_cs2_cfg_directory():
    steam = _get_steam_install_path()
    if not steam:
        return None
    subpaths = [
        os.path.join("steamapps", "common", "Counter-Strike Global Offensive", "game", "csgo", "cfg"),
        os.path.join("steamapps", "common", "Counter-Strike Global Offensive", "csgo", "cfg"),
    ]
    seen = set()
    for root in _steam_library_roots(steam):
        if not root or root in seen:
            continue
        seen.add(root)
        for sub in subpaths:
            candidate = os.path.join(root, sub)
            if os.path.isdir(candidate):
                return candidate
    return None

def _cs2_autoexec_body():
    lines = [
        "// ZERNIX NEXUS — CS2 autoexec",
        "rate 1000000",
        "cl_interp_ratio 1",
        "cl_interp 0.015625",
        "cl_net_buffer_ticks 0",
        "m_rawinput 1",
        "engine_low_latency_sleep_after_client_tick true",
        "engine_no_focus_sleep 0",
        'bind w "+forward"',
        'bind s "+back"',
        'bind a "+left"',
        'bind d "+right"',
        'echo "ZERNIX NEXUS autoexec loaded"',
    ]
    return "\n".join(lines)


def get_cs2_2026_launch_options():
    return get_smart_launch_options()


def build_cs2_adaptive_profile():
    """
    Build one hardware-aware CS2 profile from CPU topology, RAM and monitor Hz.
    """
    cpu_name = _get_cpu_name()
    physical = _safe_physical_cores()
    logical = _safe_logical_cores()
    ram_gb = _safe_ram_gb()
    refresh_hz = _get_monitor_refresh_rate()
    hybrid = _is_intel_hybrid_cpu(cpu_name)
    cpu_name_lower = (cpu_name or "").lower()
    vendor = "AMD" if "amd" in cpu_name_lower or "ryzen" in cpu_name_lower else "Intel" if "intel" in cpu_name_lower else "CPU"
    if hybrid:
        p_cores = max(1, min(physical, logical - physical))
        e_cores = max(0, physical - p_cores)
    else:
        p_cores = physical
        e_cores = 0
    high_end = logical >= 16 or p_cores >= 8 or (vendor == "AMD" and physical >= 8)

    if hybrid:
        cpu_flag = "+thread_pool_option 0"
        thread_note = f"Intel hybrid scheduler ({p_cores}P/{e_cores}E)"
    elif vendor == "AMD":
        game_threads = max(4, min(physical + 1, logical, 16))
        cpu_flag = f"-threads {game_threads}"
        thread_note = f"AMD balanced thread cap ({game_threads} threads)"
    else:
        game_threads = max(4, min(physical + 1, logical, 16))
        cpu_flag = f"-threads {game_threads}"
        thread_note = f"Intel classic cores ({game_threads} threads)"

    if refresh_hz > 0:
        fps_multiplier = 3 if high_end and ram_gb >= 16 else 2
        fps_cap = max(refresh_hz + 1, min(600, refresh_hz * fps_multiplier))
    else:
        fps_cap = 400 if high_end and ram_gb >= 16 else 240

    priority_value = 22 if hybrid or logical >= 16 else 26
    pagefile_initial_mb = min(32768, ram_gb * 1024)
    pagefile_maximum_mb = min(65536, int(pagefile_initial_mb * 1.5))

    base_flags = [
        "-high",
        "-novid",
        "-nojoy",
        "-fullscreen",
        "+engine_low_latency_sleep_after_client_tick true",
    ]
    parts = base_flags + [cpu_flag]
    if refresh_hz > 0:
        parts.append(f"-freq {refresh_hz}")

    cfg_lines = {
        "rate": "rate 786432",
        "cl_interp": "cl_interp 0",
        "cl_interp_ratio": "cl_interp_ratio 1",
        "cl_net_buffer_ticks": "cl_net_buffer_ticks 0",
        "r_low_latency": "r_low_latency 2",
        "r_player_visibility_mode": "r_player_visibility_mode 1",
        "setting.csm_quality_level": "setting.csm_quality_level 3",
        "engine_low_latency_sleep_after_client_tick": "engine_low_latency_sleep_after_client_tick true",
        "engine_no_focus_sleep": "engine_no_focus_sleep 0",
        "fps_max": f"fps_max {fps_cap}",
        "cl_hud_telemetry_frametime_show": "cl_hud_telemetry_frametime_show 2",
    }

    return {
        "cpu_name": cpu_name or "Unknown CPU",
        "physical_cores": physical,
        "logical_threads": logical,
        "performance_cores": p_cores,
        "efficiency_cores": e_cores,
        "vendor": vendor,
        "ram_gb": ram_gb,
        "refresh_hz": refresh_hz,
        "hybrid": bool(hybrid),
        "high_end": bool(high_end),
        "thread_note": thread_note,
        "priority_value": priority_value,
        "fps_cap": fps_cap,
        "pagefile_initial_mb": pagefile_initial_mb,
        "pagefile_maximum_mb": pagefile_maximum_mb,
        "launch_options": " ".join(parts),
        "cfg_lines": cfg_lines,
    }


def get_smart_launch_options():
    """
    Build CS2 launch options using 2026 CPU topology logic.
    Intel 12th+ hybrid: use Source2 thread_pool_option.
    AMD/older Intel: use a bounded -threads value based on physical cores.
    """
    return build_cs2_adaptive_profile()["launch_options"]


def apply_cs2_adaptive_system_profile():
    """Apply the fully automatic CS2 profile for the current PC."""
    profile = build_cs2_adaptive_profile()
    results = []

    cfg_dir = find_cs2_cfg_directory()
    if cfg_dir:
        autoexec_path = os.path.join(cfg_dir, "autoexec.cfg")
        try:
            body = ""
            if os.path.isfile(autoexec_path):
                with open(autoexec_path, "r", encoding="utf-8", errors="ignore") as f:
                    body = f.read()
            for key, line in profile["cfg_lines"].items():
                body = _cfg_upsert_entry(body, key, line)
            with open(autoexec_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(body)
            results.append(f"[ZERNIX] Adaptive CS2 cfg applied: fps_max {profile['fps_cap']}.")
        except Exception as e:
            results.append(f"❌ Adaptive CS2 cfg failed: {e}")
    else:
        results.append("⚠️ Adaptive CS2 cfg skipped: cfg folder not found.")

    results.append(clean_ram())
    if is_admin():
        results.append(apply_smart_priority_control(profile["priority_value"]))
        results.append(optimize_pagefile())
        results.append(enable_ultimate_performance())
        results.append(optimize_services())
        results.append(apply_cpu_turbo())
    else:
        results.append("⚠️ Adaptive system registry/power steps skipped: run as Administrator.")

    try:
        for proc in psutil.process_iter(["name"]):
            if str((proc.info or {}).get("name") or "").lower() == "cs2.exe":
                proc.nice(psutil.HIGH_PRIORITY_CLASS)
                results.append("[ZERNIX] Running cs2.exe priority set to High.")
                break
    except Exception as e:
        results.append(f"⚠️ CS2 process priority skipped: {e}")

    summary = (
        f"[ZERNIX] Auto profile: {profile['physical_cores']} cores/"
        f"{profile['logical_threads']} threads, RAM {profile['ram_gb']}GB, "
        f"Hz {profile['refresh_hz'] or 'auto'}, {profile['thread_note']}. "
        f"Launch: {profile['launch_options']}"
    )
    return " | ".join([summary] + results)


def _find_cs2_exe_path():
    steam = _get_steam_install_path()
    if not steam:
        return None
    subpath = os.path.join("steamapps", "common", "Counter-Strike Global Offensive", "game", "bin", "win64", "cs2.exe")
    for root in _steam_library_roots(steam):
        candidate = os.path.join(root, subpath)
        if os.path.isfile(candidate):
            return candidate
    return None


def disable_fullscreen_optimization_for_cs2():
    """Disable Fullscreen Optimization using AppCompat Flags for cs2.exe."""
    exe_path = _find_cs2_exe_path()
    if not exe_path:
        return "⚠️ CS2 executable not found. Fullscreen optimization tweak skipped."
    try:
        key = winreg.CreateKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers",
        )
        winreg.SetValueEx(key, exe_path, 0, winreg.REG_SZ, "~ DISABLEDXMAXIMIZEDWINDOWEDMODE")
        winreg.CloseKey(key)
        _broadcast_system_change()
        return "[ZERNIX] Direct Flip enabled for CS2."
    except Exception as e:
        return f"❌ Fullscreen optimization tweak failed: {e}"


def optimize_network_throttling():
    """Set multimedia scheduler network throttle for gaming latency."""
    blocked = _safeguard_blocks_tweaks()
    if blocked:
        return blocked
    if not is_admin():
        return "❌ Network Throttling optimization requires admin rights."
    try:
        with winreg.CreateKey(
            winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"
        ) as key:
            winreg.SetValueEx(key, "NetworkThrottlingIndex", 0, winreg.REG_DWORD, 10)
            winreg.SetValueEx(key, "SystemResponsiveness", 0, winreg.REG_DWORD, 20)
        _broadcast_system_change()
        return "[ZERNIX] Network Throttling eased (NetworkThrottlingIndex=10, SystemResponsiveness=20)."
    except Exception as e:
        return f"❌ Network Throttling optimization failed: {e}"


def _has_nvidia_gpu() -> bool:
    try:
        controllers = wmi.WMI().Win32_VideoController()
        for ctrl in controllers:
            name = str(getattr(ctrl, "Name", "") or "").lower()
            if "nvidia" in name or "geforce" in name:
                return True
    except Exception:
        pass
    return False


def set_nvidia_shader_cache_unlimited():
    """
    Try to enforce large/unlimited shader cache hint for NVIDIA profile.
    Note: exact keys can vary by driver; failure is handled safely.
    """
    if not is_admin():
        return "❌ NVIDIA shader cache tweak requires admin rights."
    if not _has_nvidia_gpu():
        return "ℹ️ NVIDIA GPU not detected. Shader cache tweak skipped."

    possible_keys = [
        r"SOFTWARE\NVIDIA Corporation\Global\NGXCore",
        r"SOFTWARE\NVIDIA Corporation\Global\NvBackend",
        r"SOFTWARE\NVIDIA Corporation\Global\NVTweak",
        r"SOFTWARE\NVIDIA Corporation\Global\DriverSettings",
    ]
    writes = 0
    for sub in possible_keys:
        try:
            key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, sub)
            winreg.SetValueEx(key, "ShaderCacheSizeMB", 0, winreg.REG_DWORD, 10240)
            winreg.SetValueEx(key, "ShaderCacheSize", 0, winreg.REG_SZ, "Unlimited")
            winreg.CloseKey(key)
            writes += 1
        except Exception:
            continue
    if writes:
        _broadcast_system_change()
    if writes:
        return "[ZERNIX] NVIDIA shader cache configured (10GB/Unlimited)."
    return "⚠️ NVIDIA shader cache tweak skipped (key/permission not available)."


def apply_source2_pro_optimization():
    """Apply Source 2 pro optimization modules requested for gaming profiles."""
    steps = [
        disable_fullscreen_optimization_for_cs2,
        apply_smart_priority_control,
        apply_zernix_network_registry,
        optimize_network_throttling,
        lambda: apply_cs2_network_presets("auto"),
        apply_cs2_competitive_2026_cfg,
        apply_zernix_audio_pro,
        set_nvidia_shader_cache_unlimited,
    ]
    results = []
    for fn in steps:
        try:
            results.append(fn())
        except Exception as e:
            results.append(f"❌ {getattr(fn, '__name__', 'step')} failed: {e}")
    return " | ".join(results)


def apply_extreme_mode():
    """Apply extreme competitive profile (risky)."""
    steps = [
        disable_vbs_integrity,
        disable_dynamic_tick,
        apply_smart_priority_control,
        apply_realtime_priority_mode,
    ]
    results = []
    for fn in steps:
        try:
            results.append(fn())
        except Exception as e:
            results.append(f"❌ {getattr(fn, '__name__', 'step')} failed: {e}")
    return " | ".join(results)


def _load_backup_payload():
    try:
        if not os.path.isfile(BACKUP_FILE):
            return {}
        with open(BACKUP_FILE, "r", encoding="utf-8") as file_obj:
            data = json.load(file_obj)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _restore_reg_value_from_backup_or_default(root, path: str, name: str, default_value, default_type):
    payload = _load_backup_payload()
    root_tag = _REG_ROOT_TAG.get(root)
    backup_key = f"{root_tag}|{path}|{name}" if root_tag else ""
    try:
        with winreg.CreateKey(root, path) as key:
            if backup_key and backup_key in payload:
                item = payload.get(backup_key) or {}
                value = item.get("value", default_value)
                reg_type = int(item.get("type", default_type))
                winreg.SetValueEx(key, name, 0, reg_type, value)
                return True, f"restored from backup ({name})"
            winreg.SetValueEx(key, name, 0, default_type, default_value)
            return True, f"restored to default ({name})"
    except Exception as e:
        return False, f"restore failed ({name}): {e}"


def _delete_reg_value_if_exists(root, path: str, name: str):
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_SET_VALUE) as key:
            try:
                winreg.DeleteValue(key, name)
                return True, f"deleted ({name})"
            except FileNotFoundError:
                return True, f"already absent ({name})"
    except Exception as e:
        return False, f"delete failed ({name}): {e}"


def rollback_extreme_mode():
    """Rollback only Extreme Mode changes (VBS, Dynamic Tick, scheduler priorities)."""
    if not is_admin():
        return "❌ Extreme Rollback requires admin rights."
    messages = []
    try:
        ok_vbs, msg_vbs = _restore_reg_value_from_backup_or_default(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\DeviceGuard",
            "EnableVirtualizationBasedSecurity",
            1,
            winreg.REG_DWORD,
        )
        messages.append(msg_vbs if ok_vbs else f"❌ {msg_vbs}")

        games_task = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games"
        with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, games_task) as key:
            winreg.SetValueEx(key, "GPU Priority", 0, winreg.REG_DWORD, 8)
            winreg.SetValueEx(key, "Priority", 0, winreg.REG_DWORD, 6)
            winreg.SetValueEx(key, "Scheduling Category", 0, winreg.REG_SZ, "High")
        messages.append("MMCSS Games priority restored")

        dyn = _run_cmd("bcdedit /deletevalue disabledynamictick")
        if dyn.returncode == 0:
            messages.append("Dynamic Tick restored to default")
        else:
            details = (dyn.stderr or dyn.stdout or "").strip()
            messages.append(f"Dynamic Tick reset info: {details or 'already default'}")

        _broadcast_system_change()
        return "[ZERNIX] Extreme Rollback completed: " + ", ".join(messages) + "."
    except Exception as e:
        return f"❌ Extreme Rollback failed: {e}"


def set_windows_high_performance_plan():
    """Activate High Performance power plan."""
    if not is_admin():
        return "❌ High Performance plan requires admin rights."
    try:
        res = _run_cmd("powercfg -setactive SCHEME_MIN")
        if res.returncode == 0:
            return "⚡ Power plan set to High Performance."
        return "⚠️ Failed to activate High Performance plan."
    except Exception as e:
        return f"❌ High Performance plan error: {e}"


def clear_directx_shader_cache_2026():
    """Clear DirectX shader cache via file deletion with cleanmgr fallback."""
    local = os.environ.get("LOCALAPPDATA", "")
    cache_dir = os.path.join(local, "D3DSCache") if local else ""
    deleted = 0
    try:
        if cache_dir and os.path.isdir(cache_dir):
            for name in os.listdir(cache_dir):
                target = os.path.join(cache_dir, name)
                try:
                    if os.path.isdir(target):
                        shutil.rmtree(target, ignore_errors=True)
                    else:
                        os.remove(target)
                    deleted += 1
                except Exception:
                    continue
        if deleted > 0:
            return f"🧩 DirectX shader cache cleared ({deleted} items)."
        _run_cmd("cleanmgr /AUTOCLEAN")
        return "🧩 DirectX shader cache cleanup attempted via cleanmgr."
    except Exception as e:
        return f"❌ DirectX shader cache cleanup failed: {e}"


def clear_steam_shader_precache():
    """Clear Steam shader pre-caching folders in all Steam libraries."""
    steam = _get_steam_install_path()
    if not steam:
        return "⚠️ Steam not found. Shader pre-cache cleanup skipped."
    removed = 0
    for root in _steam_library_roots(steam):
        shadercache = os.path.join(root, "steamapps", "shadercache")
        if not os.path.isdir(shadercache):
            continue
        for item in os.listdir(shadercache):
            target = os.path.join(shadercache, item)
            try:
                if os.path.isdir(target):
                    shutil.rmtree(target, ignore_errors=True)
                else:
                    os.remove(target)
                removed += 1
            except Exception:
                continue
    return f"🧹 Steam shader pre-cache cleared ({removed} items)."

def _ensure_autoexec_sources_zernix(cfg_dir: str) -> str:
    """Ensure autoexec.cfg loads the current ZERNIX NEXUS configuration."""
    autoexec_path = os.path.join(cfg_dir, "autoexec.cfg")
    line = "exec zernix_nexus"
    try:
        body = ""
        if os.path.isfile(autoexec_path):
            with open(autoexec_path, "r", encoding="utf-8", errors="ignore") as f:
                body = f.read()
        legacy_line_present = bool(
            re.search(r"^\s*exec\s+novaboost\s*$", body, flags=re.MULTILINE | re.IGNORECASE)
        )
        body = re.sub(
            r"^\s*exec\s+novaboost\s*$",
            line,
            body,
            flags=re.MULTILINE | re.IGNORECASE,
        )
        if not legacy_line_present and re.search(
            rf"^\s*{re.escape(line)}\s*$",
            body,
            flags=re.MULTILINE | re.IGNORECASE,
        ):
            return "[ZERNIX] autoexec.cfg loads zernix_nexus.cfg."
        if not legacy_line_present:
            if body and not body.endswith("\n"):
                body += "\n"
            body += line + "\n"
        with open(autoexec_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        return "[ZERNIX] autoexec.cfg updated: exec zernix_nexus"
    except OSError as exc:
        return f"⚠️ autoexec exec line skipped: {exc}"


def install_cs2_pro_config():
    cfg_dir = find_cs2_cfg_directory()
    if not cfg_dir:
        return "❌ CS2 Pro Config: папка игры не найдена."
    path = os.path.join(cfg_dir, "zernix_nexus.cfg")
    try:
        body = "\n".join(
            [
                "// ZERNIX NEXUS CS2 Pro Config",
                "rate 786432",
                "cl_interp_ratio 1",
                "cl_interp 0",
                "cl_net_buffer_ticks 0",
                "r_low_latency 2",
                "r_player_visibility_mode 1",
                "setting.csm_quality_level 3",
                "cl_rack_physics_mode 0",
                "fps_max 0",
                "r_drawparticles 0",
                "r_drawtracers_firstperson 0",
                "engine_low_latency_sleep_after_client_tick true",
                "engine_no_focus_sleep 0",
                "cl_hud_telemetry_frametime_show 2",
                "setting.buffering_to_smooth_packet_loss 0",
                'echo "ZERNIX NEXUS Pro Config loaded"',
            ]
        )
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        results = [
            "🎮 Pro Config installed: zernix_nexus.cfg",
            _ensure_autoexec_sources_zernix(cfg_dir),
            apply_cs2_competitive_2026_cfg(),
            disable_fullscreen_optimization_for_cs2(),
            set_nvidia_shader_cache_unlimited(),
            set_windows_high_performance_plan(),
        ]
        return " | ".join(results)
    except OSError as e:
        return f"❌ Ошибка записи: {e}"


def set_cs2_frametime_telemetry(enabled=True):
    """Toggle frame-time telemetry line in CS2 autoexec."""
    cfg_dir = find_cs2_cfg_directory()
    if not cfg_dir:
        return "❌ CS2 telemetry: game cfg folder not found."
    path = os.path.join(cfg_dir, "zernix_nexus.cfg")
    legacy_path = os.path.join(cfg_dir, "novaboost.cfg")
    value = "2" if enabled else "0"
    line = f"cl_hud_telemetry_frametime_show {value}"
    try:
        body = ""
        source_path = path if os.path.isfile(path) else legacy_path
        if os.path.isfile(source_path):
            with open(source_path, "r", encoding="utf-8", errors="ignore") as f:
                body = f.read()
        if "cl_hud_telemetry_frametime_show" in body:
            body = re.sub(r"cl_hud_telemetry_frametime_show\s+\d+", line, body)
        else:
            if body and not body.endswith("\n"):
                body += "\n"
            body += line + "\n"
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        return "📊 CS2 Frame Time telemetry enabled." if enabled else "📊 CS2 Frame Time telemetry disabled."
    except Exception as e:
        return f"❌ CS2 telemetry tweak failed: {e}"


def disable_cfg_for_cs2():
    """Disable CFG mitigation for cs2.exe through process mitigation policy (registry-backed)."""
    if not is_admin():
        return "❌ CS2 CFG tweak requires admin rights."
    cmd = (
        "powershell -NoProfile -ExecutionPolicy Bypass "
        "-Command \"Set-ProcessMitigation -Name 'cs2.exe' -Disable CFG\""
    )
    res = _run_cmd(cmd)
    if res.returncode == 0:
        return "🎮 CS2 CFG mitigation disabled."
    err = (res.stderr or res.stdout or "").strip()
    return f"❌ Failed to disable CS2 CFG: {err or 'unknown error'}"

def apply_input_latency_tweaks():
    """
    Faceit-safe OS-environment tweaks (registry / documented MMCSS paths only).

    Applies MMCSS responsiveness caps, Games multimedia scheduling profile, desktop menu snap,
    reduced DVR/App Capture contention, Windows desktop mouse acceleration off (CS2 raw input unchanged),
    and CPU Dynamic Power Throttling off for steadier foreground scheduling.

    Does not patch system binaries; does not alter driver signing or integrity-check BCD flags; does not hook cs2.exe.
    Rollback: restore_registry_defaults() restores every path touched here.
    """
    blocked = _safeguard_blocks_tweaks()
    if blocked:
        return blocked
    if not is_admin():
        return "❌ Нужен Админ."
    try:
        ok, rp = _ensure_restore_point_before_registry_changes()
        if not ok:
            return rp

        mp = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"
        k = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, mp)
        winreg.SetValueEx(k, "NetworkThrottlingIndex", 0, winreg.REG_DWORD, 10)
        winreg.SetValueEx(k, "SystemResponsiveness", 0, winreg.REG_DWORD, 20)
        winreg.CloseKey(k)

        games = mp + r"\Tasks\Games"
        with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, games) as gt:
            winreg.SetValueEx(gt, "GPU Priority", 0, winreg.REG_DWORD, 8)
            winreg.SetValueEx(gt, "Priority", 0, winreg.REG_DWORD, 8)
            winreg.SetValueEx(gt, "Scheduling Category", 0, winreg.REG_SZ, "High")
            winreg.SetValueEx(gt, "SFIO Priority", 0, winreg.REG_SZ, "High")

        with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Power\PowerThrottling") as pt:
            winreg.SetValueEx(pt, "PowerThrottlingOff", 0, winreg.REG_DWORD, 1)

        # Reduce background capture / DVR contention (HwSchMode left to System Stability).
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"System\GameConfigStore") as gcfg:
            winreg.SetValueEx(gcfg, "GameDVR_Enabled", 0, winreg.REG_DWORD, 0)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\GameDVR") as gdvr:
            winreg.SetValueEx(gdvr, "AppCaptureEnabled", 0, winreg.REG_DWORD, 0)

        # Desktop composition mouse acceleration off (“Enhance pointer precision”).
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Mouse") as mouse_key:
            winreg.SetValueEx(mouse_key, "MouseSpeed", 0, winreg.REG_SZ, "0")
            winreg.SetValueEx(mouse_key, "MouseThreshold1", 0, winreg.REG_SZ, "0")
            winreg.SetValueEx(mouse_key, "MouseThreshold2", 0, winreg.REG_SZ, "0")

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop") as desk:
            winreg.SetValueEx(desk, "MenuShowDelay", 0, winreg.REG_SZ, "0")

        _broadcast_system_change()
        return (
            "⚡ Input latency tweaks applied "
            "(MMCSS + Games profile, power throttling off, DVR capture off, mouse accel off, menu delay min). "
            f"| {rp}"
        )
    except Exception as e:
        return f"❌ Ошибка: {e}"

def clean_ram():
    """Сброс рабочих наборов процессов"""
    if not _EmptyWorkingSet:
        return "❌ Ошибка: функция очистки RAM не поддерживается вашей системой."
    
    opened = 0
    trimmed = 0
    access = _PROCESS_QUERY_LIMITED_INFORMATION | _PROCESS_SET_QUOTA
    for proc in psutil.process_iter(["pid"]):
        try:
            pid = proc.info.get("pid")
            if pid is None or pid <= 0: continue
            hproc = _OpenProcess(access, False, int(pid))
            if not hproc: continue
            opened += 1
            if _EmptyWorkingSet(hproc):
                trimmed += 1
            _CloseHandle(hproc)
        except Exception:
            continue
    return f"🧠 RAM: Очищено для {trimmed}/{opened} процессов."


def clear_shader_cache():
    local = os.environ.get("LOCALAPPDATA", "")
    if not local:
        return "⚠️ Shader Cache: LOCALAPPDATA не найден."
    cache_dir = os.path.join(local, "D3DSCache")
    if not os.path.isdir(cache_dir):
        return "ℹ️ Shader Cache: папка D3DSCache не найдена."
    deleted = 0
    for name in os.listdir(cache_dir):
        target = os.path.join(cache_dir, name)
        try:
            if os.path.isdir(target):
                shutil.rmtree(target, ignore_errors=True)
            else:
                os.remove(target)
            deleted += 1
        except OSError:
            continue
    return f"🧩 Shader Cache очищен ({deleted} элементов)."


def cleanup_dns_and_shader_cache():
    shader_res = clear_shader_cache()
    dns_res = _run_cmd("ipconfig /flushdns")
    if dns_res.returncode == 0:
        return f"{shader_res} | 🌐 DNS cache flushed."
    return f"{shader_res} | ⚠️ DNS flush failed."


def clean_system_temp():
    temp_dir = os.environ.get("TEMP", "")
    removed = 0
    if temp_dir and os.path.isdir(temp_dir):
        for name in os.listdir(temp_dir):
            target = os.path.join(temp_dir, name)
            try:
                if os.path.isdir(target):
                    shutil.rmtree(target, ignore_errors=True)
                else:
                    os.remove(target)
                removed += 1
            except OSError:
                continue
    _run_cmd("ipconfig /flushdns")
    return f"🧹 TEMP очищен ({removed} элементов), DNS flushed."


def clear_system_cache():
    """
    Smart RAM cleaner:
    - clear Standby List (best effort)
    - flush DNS
    - clean TEMP and Prefetch folders
    """
    standby_message = "⚠️ Standby List cleanup skipped (EmptyStandbyList.exe not found)."
    try:
        lookup = _run_cmd("where EmptyStandbyList.exe")
        exe_path = (lookup.stdout or "").strip().splitlines()
        if exe_path:
            run = _run_cmd(f'"{exe_path[0]}" standbylist')
            if run.returncode == 0:
                standby_message = "🧠 Standby List очищен."
            else:
                standby_message = "⚠️ Standby List cleanup failed."
    except Exception:
        standby_message = "⚠️ Standby List cleanup failed."

    dns = _run_cmd("ipconfig /flushdns")
    dns_message = "🌐 DNS cache flushed." if dns.returncode == 0 else "⚠️ DNS flush failed."

    cleaned = 0
    targets = []
    temp_dir = os.environ.get("TEMP", "")
    if temp_dir:
        targets.append(temp_dir)
    targets.append(os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Prefetch"))

    for folder in targets:
        if not folder or not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            path = os.path.join(folder, name)
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    os.remove(path)
                cleaned += 1
            except Exception:
                continue

    return f"{standby_message} | {dns_message} | 🧹 TEMP/Prefetch cleaned ({cleaned} items)."


def run_turbo_mode_steps():
    steps = [
        clear_system_cache,
        clean_ram,
        cleanup_dns_and_shader_cache,
        optimize_services,
        enable_ultimate_performance,
        set_max_performance_visuals,
    ]
    results = []
    for fn in steps:
        try:
            results.append(fn())
        except Exception as e:
            results.append(f"❌ {fn.__name__}: {e}")
    return results


def optimize_services():
    """Disable unneeded services based on Siempre Fuerte 2026 profile."""
    if not is_admin():
        return "❌ Service optimization requires admin rights."
    is_safe, thermal_msg = check_cpu_thermal_safety()
    if not is_safe:
        return thermal_msg
    services = [
        "vmicvss",
        "vmicshutdown",
        "vmicexchange",
        "vmicheartbeat",
        "vmicrdv",
        "vmictimesync",
        "SensorService",
        "SensrSvc",
        "SensorDataService",
        "Spooler",
        "XblAuthManager",
        "XblGameSave",
        "XboxGipSvc",
        "XboxNetApiSvc",
        "DiagTrack",
    ]
    preserve_virt = preserve_virtualization_enabled()
    changed = 0
    skipped = []
    never_disable_lower = {name.lower() for name in NETWORK_CRITICAL_SERVICE_NAMES}
    for svc in services:
        service_name = svc.lower()
        if svc in NETWORK_CRITICAL_SERVICE_NAMES or service_name in never_disable_lower:
            skipped.append(f"ZERNIX SafeGuard: служба {svc} пропущена (сеть/WMI/VPN)")
            continue
        if preserve_virt and service_name.startswith("vmic"):
            skipped.append(f"ZERNIX SafeGuard: служба {svc} пропущена (режим разработчика / Hyper-V)")
            continue
        if any(token in service_name for token in CRITICAL_SERVICE_EXCLUSIONS):
            skipped.append(f"ZERNIX SafeGuard: служба {svc} пропущена")
            continue
        if any(token in service_name for token in ANTICHEAT_SERVICE_EXCLUSIONS):
            skipped.append(f"ZERNIX Anti-Cheat Guard: service {svc} skipped")
            continue
        _run_cmd(f"sc stop {svc}")
        res = _run_cmd(f"sc config {svc} start= disabled")
        if res.returncode == 0:
            changed += 1
    message = f"🛠️ Services optimized ({changed}/{len(services)} disabled)."
    if skipped:
        message += " | " + " | ".join(skipped)
    return message


def restore_network_connectivity():
    """Best-effort restore of core networking + WMI after aggressive tuning or broken stacks."""
    if not is_admin():
        return "❌ Network/VPN restore requires Administrator rights."
    hints = []
    for cmd in (
        "netsh int tcp set global autotuninglevel=normal",
        "netsh int tcp set global rss=enabled",
    ):
        res = _run_cmd(cmd)
        if res.returncode != 0:
            hints.append((cmd.split(" ")[-2:]))

    service_plan = [
        ("Winmgmt", "auto"),
        ("WinHttpAutoProxySvc", "demand"),
        ("IKEEXT", "demand"),
        ("iphlpsvc", "auto"),
        ("Dnscache", "auto"),
        ("Dhcp", "auto"),
        ("NlaSvc", "auto"),
        ("netprofm", "demand"),
        ("Wcmsvc", "auto"),
        ("BFE", "auto"),
        ("PolicyAgent", "demand"),
        ("RasMan", "auto"),
    ]
    restored = 0
    for name, start in service_plan:
        _run_cmd(f"sc config {name} start= {start}")
        st = _run_cmd(f"sc start {name}")
        if st.returncode == 0:
            restored += 1

    dns = _run_cmd("ipconfig /flushdns")
    _broadcast_system_change()
    dns_ok = dns.returncode == 0
    extra = " Предупреждение: часть netsh-команд не применилась." if hints else ""
    return (
        f"🌐 Восстановление сети/VPN/WMI: TCP профиль сброшен, DNS flush {'OK' if dns_ok else 'частично'}, "
        f"службы перезапущены (~{restored}).{extra}"
    )


def optimize_pagefile():
    """Configure pagefile size based on installed RAM."""
    if not is_admin():
        return "❌ Pagefile optimization requires admin rights."
    try:
        ram_gb = max(4, round(psutil.virtual_memory().total / (1024**3)))
        initial_mb = min(32768, ram_gb * 1024)
        maximum_mb = min(65536, int(initial_mb * 1.5))
        _run_cmd("wmic computersystem where name=\"%computername%\" set AutomaticManagedPagefile=False")
        _run_cmd("wmic pagefileset where name=\"C:\\\\pagefile.sys\" delete")
        create_res = _run_cmd("wmic pagefileset create name=\"C:\\\\pagefile.sys\"")
        _run_cmd(
            f"wmic pagefileset where name=\"C:\\\\pagefile.sys\" set InitialSize={initial_mb},MaximumSize={maximum_mb}"
        )
        if create_res.returncode == 0:
            return f"💾 Pagefile optimized: {initial_mb}MB / {maximum_mb}MB."
        return "⚠️ Pagefile tuning partially applied."
    except Exception as e:
        return f"❌ Pagefile optimization failed: {e}"


def apply_cpu_turbo():
    """Force aggressive CPU performance and disable core parking."""
    if not is_admin():
        return "❌ CPU Turbo requires admin rights."
    is_safe, thermal_msg = check_cpu_thermal_safety()
    if not is_safe:
        return thermal_msg
    if _is_high_end_or_hybrid_cpu() or _is_windows_11():
        return "⏭️ CPU Turbo skipped: aggressive scheduler/Core Parking tweaks are disabled on high-end or hybrid CPUs."

    commands = [
        "powercfg -setacvalueindex scheme_current sub_processor PROCTHROTTLEMIN 100",
        "powercfg -setacvalueindex scheme_current sub_processor PROCTHROTTLEMAX 100",
        f"powercfg -setacvalueindex scheme_current sub_processor {CPU_PARKING_MIN_CORES} 100",
        f"powercfg -setacvalueindex scheme_current sub_processor {CPU_PARKING_MAX_CORES} 100",
        "powercfg -setactive scheme_current",
    ]
    ok = 0
    for cmd in commands:
        if _run_cmd(cmd).returncode == 0:
            ok += 1
    if ok == len(commands):
        return "⚙️ CPU Turbo applied (100% performance, core parking off)."
    return "⚠️ CPU Turbo partially applied."

def apply_extra_performance_tweaks():
    if not is_admin():
        return "❌ Нужен Админ."
    try:
        # NTFS, IRQ, DiagTrack
        k = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem")
        winreg.SetValueEx(k, "NtfsDisableLastAccessUpdate", 0, winreg.REG_DWORD, 3)
        winreg.CloseKey(k)
        return "✨ PRO-твики применены!"
    except Exception as e:
        return f"❌ Ошибка: {e}"

def restore_registry_defaults():
    """Restore registry values managed by ZERNIX NEXUS to safer defaults."""
    if not is_admin():
        return "❌ Restore defaults requires admin rights."
    try:
        restore_items = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Policies\Microsoft\Windows\DataCollection", "AllowTelemetry", 1, winreg.REG_DWORD),
            (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Power\PowerThrottling", "PowerThrottlingOff", 0, winreg.REG_DWORD),
            (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\PriorityControl", "Win32PrioritySeparation", 2, winreg.REG_DWORD),
            (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\DeviceGuard", "EnableVirtualizationBasedSecurity", 1, winreg.REG_DWORD),
            (winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", "MenuShowDelay", "400", winreg.REG_SZ),
            (winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", "ForegroundLockTimeout", 200000, winreg.REG_DWORD),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile", "NetworkThrottlingIndex", 10, winreg.REG_DWORD),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile", "SystemResponsiveness", 20, winreg.REG_DWORD),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games", "GPU Priority", 8, winreg.REG_DWORD),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games", "Priority", 6, winreg.REG_DWORD),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games", "Scheduling Category", "High", winreg.REG_SZ),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games", "SFIO Priority", "High", winreg.REG_SZ),
            (winreg.HKEY_CURRENT_USER, r"System\GameConfigStore", "GameDVR_Enabled", 1, winreg.REG_DWORD),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled", 1, winreg.REG_DWORD),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\GameBar", "AllowAutoGameMode", 1, winreg.REG_DWORD),
            (winreg.HKEY_CURRENT_USER, r"Control Panel\Mouse", "MouseSpeed", "1", winreg.REG_SZ),
            (winreg.HKEY_CURRENT_USER, r"Control Panel\Mouse", "MouseThreshold1", "6", winreg.REG_SZ),
            (winreg.HKEY_CURRENT_USER, r"Control Panel\Mouse", "MouseThreshold2", "10", winreg.REG_SZ),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\Dwm", "OverlayTestMode", 0, winreg.REG_DWORD),
            (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode", 1, winreg.REG_DWORD),
            (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem", "NtfsDisableLastAccessUpdate", 2, winreg.REG_DWORD),
            (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem", "LongPathsEnabled", 0, winreg.REG_DWORD),
            (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management", "DisablePagingExecutive", 0, winreg.REG_DWORD),
            (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management", "LargeSystemCache", 0, winreg.REG_DWORD),
            (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\DiagTrack", "Start", 2, winreg.REG_DWORD),
        ]
        ok_count = 0
        details = []
        for item in restore_items:
            ok, msg = _restore_reg_value_from_backup_or_default(*item)
            ok_count += 1 if ok else 0
            if not ok:
                details.append(msg)

        delete_items = [
            (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\PriorityControl", "IRQPriority"),
            (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\USB\USBFlags", "DisableSelectiveSuspend"),
        ]
        for item in delete_items:
            ok, msg = _delete_reg_value_if_exists(*item)
            ok_count += 1 if ok else 0
            if not ok:
                details.append(msg)

        _broadcast_system_change()
        message = f"✅ Registry defaults restored ({ok_count}/{len(restore_items) + len(delete_items)} values)."
        if details:
            message += " Warnings: " + "; ".join(details[:4])
        return message
    except Exception as e:
        return f"❌ Failed to restore defaults: {e}"


def restore_system_defaults():
    """
    Full rollback entry point:
    - restore known registry values touched by app tweaks
    - reset boot settings (bcdedit values) to Windows defaults
    - restore default power schemes and activate Balanced
    """
    if not is_admin():
        return "❌ Restore System Defaults requires admin rights."

    messages = [restore_registry_defaults()]

    bcd_reset_cmds = [
        "bcdedit /deletevalue useplatformclock",
        "bcdedit /deletevalue useplatformtick",
        "bcdedit /deletevalue disabledynamictick",
        "bcdedit /deletevalue tscsyncpolicy",
        "bcdedit /deletevalue nx",
        "bcdedit /set bootmenupolicy Standard",
    ]
    bcd_ok = 0
    for cmd in bcd_reset_cmds:
        if _run_cmd(cmd).returncode == 0:
            bcd_ok += 1

    power_msgs = []
    if _run_cmd("powercfg -restoredefaultschemes").returncode == 0:
        power_msgs.append("power schemes restored")
    if _run_cmd("powercfg /setactive SCHEME_BALANCED").returncode == 0:
        power_msgs.append("balanced plan active")

    messages.append(f"🧰 BCDEdit defaults restored ({bcd_ok}/{len(bcd_reset_cmds)} commands).")
    if power_msgs:
        messages.append("⚡ " + ", ".join(power_msgs) + ".")
    else:
        messages.append("⚠️ Power plan reset partially applied.")

    service_defaults = {
        "Spooler": "demand",
        "WSearch": "delayed-auto",
        "XblAuthManager": "demand",
        "XblGameSave": "demand",
        "XboxGipSvc": "demand",
        "XboxNetApiSvc": "demand",
        "DiagTrack": "auto",
        "SensorService": "demand",
        "SensrSvc": "demand",
        "SensorDataService": "demand",
        "vmicvss": "demand",
        "vmicshutdown": "demand",
        "vmicexchange": "demand",
        "vmicheartbeat": "demand",
        "vmicrdv": "demand",
        "vmictimesync": "demand",
        "Winmgmt": "auto",
        "WinHttpAutoProxySvc": "demand",
        "IKEEXT": "demand",
        "iphlpsvc": "auto",
        "Dnscache": "auto",
        "Dhcp": "auto",
        "NlaSvc": "auto",
        "netprofm": "demand",
        "Wcmsvc": "auto",
        "BFE": "auto",
        "PolicyAgent": "demand",
        "RasMan": "auto",
    }
    services_ok = 0
    for service, startup in service_defaults.items():
        if _run_cmd(f"sc config {service} start= {startup}").returncode == 0:
            services_ok += 1
    messages.append(f"🛠️ Services restored ({services_ok}/{len(service_defaults)}).")

    pagefile_msgs = []
    if _run_cmd('wmic computersystem where name="%computername%" set AutomaticManagedPagefile=True').returncode == 0:
        pagefile_msgs.append("automatic pagefile enabled")
    _run_cmd('wmic pagefileset where name="C:\\\\pagefile.sys" delete')
    messages.append("💾 " + (", ".join(pagefile_msgs) if pagefile_msgs else "pagefile auto restore attempted") + ".")

    cpu_power_cmds = [
        "powercfg -setacvalueindex scheme_current sub_processor PROCTHROTTLEMIN 5",
        "powercfg -setacvalueindex scheme_current sub_processor PROCTHROTTLEMAX 100",
        f"powercfg -deletevalue scheme_current sub_processor {CPU_PARKING_MIN_CORES}",
        f"powercfg -deletevalue scheme_current sub_processor {CPU_PARKING_MAX_CORES}",
        "powercfg -setactive scheme_current",
    ]
    cpu_power_ok = sum(1 for cmd in cpu_power_cmds if _run_cmd(cmd).returncode == 0)
    messages.append(f"⚙️ CPU power defaults restored ({cpu_power_ok}/{len(cpu_power_cmds)}).")

    cs2_cleanup = []
    exe_path = _find_cs2_exe_path()
    if exe_path:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers",
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                try:
                    winreg.DeleteValue(key, exe_path)
                    cs2_cleanup.append("fullscreen optimization flag removed")
                except FileNotFoundError:
                    cs2_cleanup.append("fullscreen optimization flag already clean")
        except Exception:
            cs2_cleanup.append("fullscreen optimization flag cleanup skipped")
    mitigation = _run_cmd(
        "powershell -NoProfile -ExecutionPolicy Bypass "
        "-Command \"Set-ProcessMitigation -Name 'cs2.exe' -Enable CFG\""
    )
    if mitigation.returncode == 0:
        cs2_cleanup.append("CS2 CFG mitigation restored")
    else:
        cs2_cleanup.append("CS2 CFG mitigation restore attempted")
    messages.append("🎮 " + ", ".join(cs2_cleanup) + ".")

    messages.append("🔄 Reboot recommended.")
    return " | ".join(messages)

def _read_reg_dword(root, path, name, default=None):
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, name)
        return value
    except Exception:
        return default


def _read_service_start_type(service_name: str):
    try:
        service = psutil.win_service_get(service_name)
        config = service.as_dict()
        return str(config.get("start_type") or "").lower()
    except Exception:
        return ""


def _evaluate_service_optimization():
    target_services = ("DiagTrack", "XblAuthManager", "XblGameSave", "XboxGipSvc", "XboxNetApiSvc")
    start_types = [_read_service_start_type(name) for name in target_services]
    known = [stype for stype in start_types if stype]
    if not known:
        return "Unknown"
    disabled_count = sum(1 for stype in known if "disabled" in stype)
    if disabled_count >= max(1, len(known) - 1):
        return "Optimized"
    if disabled_count > 0:
        return "Partially optimized"
    return "Default"


def _detect_power_plan():
    """
    Detect active power plan robustly across localized Windows.
    Returns one of: Ultimate Performance, High Performance, Standard.
    """
    try:
        res = _run_cmd("powercfg /GETACTIVESCHEME")
        text = f"{res.stdout}\n{res.stderr}".lower()
        guid_match = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", text)
        guid = guid_match.group(1) if guid_match else ""
        if guid == "e9a42b02-d5df-448d-aa00-03f14749eb61":
            return "Ultimate Performance"
        if guid == "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c":
            return "High Performance"
        if guid == "381b4222-f694-41f0-9685-ff5bb260df2e":
            return "Standard"
        # Fallback by text for non-standard outputs.
        if "ultimate performance" in text:
            return "Ultimate Performance"
        if "high performance" in text:
            return "High Performance"
    except Exception:
        pass
    return "Standard"

def check_system_status():
    """
    Return current optimization status snapshot for dashboard.
    """
    mpo_value = _read_reg_dword(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\Dwm", "OverlayTestMode", 0)
    hags_value = _read_reg_dword(
        winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode", 1
    )
    game_mode = _read_reg_dword(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\GameBar", "AllowAutoGameMode", 1)
    now = time.time()
    secure_boot_cached, secure_boot_ts = _STATUS_CACHE.get("secure_boot", (None, 0.0))
    if secure_boot_cached is None or (now - secure_boot_ts) > 30.0:
        secure_boot_cached = get_secure_boot_status()
        _STATUS_CACHE["secure_boot"] = (secure_boot_cached, now)
    secure_boot_enabled, secure_boot_message = secure_boot_cached

    kb_cached, kb_ts = _STATUS_CACHE.get("kb5077181", (None, 0.0))
    if kb_cached is None or (now - kb_ts) > 120.0:
        kb_cached = detect_problematic_kb5077181()
        _STATUS_CACHE["kb5077181"] = (kb_cached, now)
    kb_detected, kb_status = kb_cached

    vbs_enabled, vbs_message = check_vbs_status()
    services_status = _evaluate_service_optimization()

    plan_name = _detect_power_plan()

    # Profile mapping aligned with actual app presets:
    # - CS2 profile: cybersport/extreme signs (VBS off or advanced low-latency stack)
    # - Gaming profile: performance profile without extreme security rollback
    # - Standard profile: rollback/daily mode
    cs2_signs = 0
    if bool(vbs_enabled) is False:
        cs2_signs += 1
    if mpo_value == 5:
        cs2_signs += 1
    if hags_value == 2:
        cs2_signs += 1
    if plan_name in ("High Performance", "Ultimate Performance"):
        cs2_signs += 1

    gaming_signs = 0
    if plan_name in ("High Performance", "Ultimate Performance"):
        gaming_signs += 1
    if services_status in ("Optimized", "Partially optimized"):
        gaming_signs += 1
    if game_mode == 1:
        gaming_signs += 1

    if cs2_signs >= 3:
        profile = "CS2"
    elif gaming_signs >= 2:
        profile = "Gaming"
    else:
        profile = "Standard"

    mode = "CS2 boost" if profile in ("CS2", "Gaming") else "Windows default"

    return {
        "mpo_value": mpo_value,
        "mpo_status": "Optimized" if mpo_value == 5 else "Critical Latency",
        "hags_value": hags_value,
        "hags_status": "Enabled" if hags_value == 2 else "Disabled",
        "power_plan": plan_name,
        "services_status": services_status,
        "profile": profile,
        "mode": mode,
        "game_mode_value": game_mode,
        "game_mode_status": "On" if game_mode == 1 else "Off",
        "secure_boot_enabled": secure_boot_enabled,
        "secure_boot_message": secure_boot_message,
        "vbs_enabled": vbs_enabled,
        "vbs_message": vbs_message,
        "kb5077181_detected": kb_detected,
        "kb5077181_status": kb_status,
    }

def enable_game_mode():
    if not is_admin():
        return "❌ Game Mode change requires admin rights."
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\GameBar") as key:
            winreg.SetValueEx(key, "AllowAutoGameMode", 0, winreg.REG_DWORD, 1)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"System\GameConfigStore") as key:
            winreg.SetValueEx(key, "GameDVR_Enabled", 0, winreg.REG_DWORD, 0)
        return "✅ Game Mode enabled (background DVR capture off)."
    except Exception as e:
        return f"❌ Failed to enable Game Mode: {e}"
