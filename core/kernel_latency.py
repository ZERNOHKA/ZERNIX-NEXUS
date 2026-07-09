import ctypes
import ctypes.wintypes as wt
from dataclasses import dataclass
from typing import Dict, Optional

import psutil

from core.security import is_admin

PROCESS_SET_INFORMATION = 0x0200
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PROCESS_ALL_FOR_TUNING = PROCESS_SET_INFORMATION | PROCESS_QUERY_INFORMATION | PROCESS_VM_READ

THREAD_SET_INFORMATION = 0x0020
THREAD_QUERY_INFORMATION = 0x0040
THREAD_ALL_FOR_TUNING = THREAD_SET_INFORMATION | THREAD_QUERY_INFORMATION

TH32CS_SNAPTHREAD = 0x00000004

TOKEN_ADJUST_PRIVILEGES = 0x0020
TOKEN_QUERY = 0x0008
SE_PRIVILEGE_ENABLED = 0x00000002

HIGH_PRIORITY_CLASS = 0x00000080
THREAD_PRIORITY_ABOVE_NORMAL = 1

ProcessPowerThrottling = 4
PROCESS_POWER_THROTTLING_CURRENT_VERSION = 1
PROCESS_POWER_THROTTLING_EXECUTION_SPEED = 0x1
PROCESS_POWER_THROTTLING_IGNORE_TIMER_RESOLUTION = 0x4

POWER_REQUEST_CONTEXT_VERSION = 0
POWER_REQUEST_CONTEXT_SIMPLE_STRING = 0x1
PowerRequestExecutionRequired = 0
PowerRequestAwayModeRequired = 2
PowerRequestSystemRequired = 3

TIMER_RESOLUTION_500US = 5000  # 100ns units
INVALID_HANDLE_VALUE = wt.HANDLE(-1).value


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", wt.DWORD), ("HighPart", wt.LONG)]


class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Luid", LUID), ("Attributes", wt.DWORD)]


class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [("PrivilegeCount", wt.DWORD), ("Privileges", LUID_AND_ATTRIBUTES * 1)]


class PROCESS_POWER_THROTTLING_STATE(ctypes.Structure):
    _fields_ = [("Version", wt.DWORD), ("ControlMask", wt.DWORD), ("StateMask", wt.DWORD)]


class REASON_CONTEXT_DUMMYUNION(ctypes.Union):
    _fields_ = [("SimpleReasonString", wt.LPWSTR)]


class REASON_CONTEXT(ctypes.Structure):
    _anonymous_ = ("Reason",)
    _fields_ = [("Version", wt.ULONG), ("Flags", wt.DWORD), ("Reason", REASON_CONTEXT_DUMMYUNION)]


class THREADENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD),
        ("cntUsage", wt.DWORD),
        ("th32ThreadID", wt.DWORD),
        ("th32OwnerProcessID", wt.DWORD),
        ("tpBasePri", wt.LONG),
        ("tpDeltaPri", wt.LONG),
        ("dwFlags", wt.DWORD),
    ]


@dataclass
class LatencyResult:
    ok: bool
    details: Dict[str, str]


class KernelLatencyBooster:
    """
    Aggressive user-mode latency profile:
    - token privileges for process/thread tuning
    - per-process throttling off
    - high scheduler pressure
    - timer resolution + power requests
    """

    def __init__(self, reason: str = "ZERNIX low-latency session"):
        self.k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        self.powrprof = ctypes.WinDLL("PowrProf", use_last_error=True)
        self.ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
        self.reason = reason
        self._power_handle = wt.HANDLE(0)
        self._timer_locked = False
        self._active_pid: Optional[int] = None

    def _raise_last_error(self, where: str):
        code = ctypes.get_last_error()
        raise OSError(code, f"{where} failed")

    def _open_process(self, pid: int) -> wt.HANDLE:
        handle = self.k32.OpenProcess(PROCESS_ALL_FOR_TUNING, False, int(pid))
        if not handle:
            self._raise_last_error("OpenProcess")
        return handle

    def _pid_by_name(self, process_name: str) -> Optional[int]:
        target = str(process_name or "").strip().lower()
        if not target:
            return None
        for proc in psutil.process_iter(["pid", "name"]):
            name = str((proc.info or {}).get("name") or "").lower()
            if name == target:
                return int((proc.info or {}).get("pid") or 0) or None
        return None

    def enable_privileges(self) -> LatencyResult:
        token = wt.HANDLE(0)
        details: Dict[str, str] = {}
        try:
            if not self.advapi32.OpenProcessToken(
                self.k32.GetCurrentProcess(),
                TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
                ctypes.byref(token),
            ):
                code = ctypes.get_last_error()
                return LatencyResult(
                    False,
                    {
                        "OpenProcessToken": f"failed (winerror={code}) — run ZERNIX as Administrator "
                        "and ensure the app is not sandboxed."
                    },
                )
            for privilege_name in ("SeDebugPrivilege", "SeIncreaseBasePriorityPrivilege"):
                luid = LUID()
                if not self.advapi32.LookupPrivilegeValueW(None, privilege_name, ctypes.byref(luid)):
                    code = ctypes.get_last_error()
                    return LatencyResult(
                        False,
                        {f"LookupPrivilegeValueW({privilege_name})": f"winerror={code}"},
                    )
                token_privileges = TOKEN_PRIVILEGES()
                token_privileges.PrivilegeCount = 1
                token_privileges.Privileges[0].Luid = luid
                token_privileges.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED
                if not self.advapi32.AdjustTokenPrivileges(
                    token, False, ctypes.byref(token_privileges), 0, None, None
                ):
                    code = ctypes.get_last_error()
                    return LatencyResult(
                        False,
                        {
                            f"AdjustTokenPrivileges({privilege_name})": f"winerror={code} — "
                            "Administrator session usually required."
                        },
                    )
                details[privilege_name] = "enabled"
            return LatencyResult(True, details)
        finally:
            if int(token.value or 0):
                self.k32.CloseHandle(token)

    def disable_process_throttling(self, pid: int) -> LatencyResult:
        try:
            handle = self._open_process(pid)
        except OSError as exc:
            return LatencyResult(
                False,
                {"OpenProcess": f"{exc} — run as Administrator or the target may be protected."},
            )
        try:
            state = PROCESS_POWER_THROTTLING_STATE(
                Version=PROCESS_POWER_THROTTLING_CURRENT_VERSION,
                ControlMask=(
                    PROCESS_POWER_THROTTLING_EXECUTION_SPEED | PROCESS_POWER_THROTTLING_IGNORE_TIMER_RESOLUTION
                ),
                StateMask=0,
            )
            ok = self.k32.SetProcessInformation(
                handle, ProcessPowerThrottling, ctypes.byref(state), ctypes.sizeof(state)
            )
            if not ok:
                self._raise_last_error("SetProcessInformation(ProcessPowerThrottling)")
            return LatencyResult(True, {"power_throttling": "disabled"})
        finally:
            self.k32.CloseHandle(handle)

    def apply_scheduler_profile(self, pid: int) -> LatencyResult:
        details = {}
        try:
            handle = self._open_process(pid)
        except OSError as exc:
            return LatencyResult(
                False,
                {"OpenProcess": f"{exc} — run as Administrator or the target may be protected."},
            )
        try:
            if not self.k32.SetPriorityClass(handle, HIGH_PRIORITY_CLASS):
                self._raise_last_error("SetPriorityClass")
            details["priority_class"] = "HIGH"
            # Keep dynamic priority boosting enabled to avoid starving driver/audio threads.
            if not self.k32.SetProcessPriorityBoost(handle, False):
                self._raise_last_error("SetProcessPriorityBoost")
            details["priority_boost"] = "enabled"
        finally:
            self.k32.CloseHandle(handle)

        snapshot = self.k32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
        if snapshot == INVALID_HANDLE_VALUE:
            self._raise_last_error("CreateToolhelp32Snapshot")
        tuned_threads = 0
        try:
            item = THREADENTRY32()
            item.dwSize = ctypes.sizeof(THREADENTRY32)
            has_item = bool(self.k32.Thread32First(snapshot, ctypes.byref(item)))
            while has_item:
                if int(item.th32OwnerProcessID) == int(pid):
                    thread_handle = self.k32.OpenThread(THREAD_ALL_FOR_TUNING, False, item.th32ThreadID)
                    if thread_handle:
                        try:
                            # Conservative per-thread uplift; do not hard-pin to CPU0
                            # because pinning can increase contention and drop FPS.
                            self.k32.SetThreadPriority(thread_handle, THREAD_PRIORITY_ABOVE_NORMAL)
                            tuned_threads += 1
                        finally:
                            self.k32.CloseHandle(thread_handle)
                has_item = bool(self.k32.Thread32Next(snapshot, ctypes.byref(item)))
        finally:
            self.k32.CloseHandle(snapshot)
        details["threads_tuned"] = str(tuned_threads)
        return LatencyResult(True, details)

    def lock_system_latency(self) -> LatencyResult:
        details = {}
        current = wt.ULONG()
        status = self.ntdll.NtSetTimerResolution(
            wt.ULONG(TIMER_RESOLUTION_500US), wt.BOOLEAN(True), ctypes.byref(current)
        )
        if status == 0:
            self._timer_locked = True
            details["timer_resolution"] = f"locked_100ns={int(current.value)}"
        else:
            details["timer_resolution"] = f"ntstatus={int(status)}"

        reason_buf = ctypes.create_unicode_buffer(self.reason)
        reason_context = REASON_CONTEXT()
        reason_context.Version = POWER_REQUEST_CONTEXT_VERSION
        reason_context.Flags = POWER_REQUEST_CONTEXT_SIMPLE_STRING
        reason_context.SimpleReasonString = ctypes.cast(reason_buf, wt.LPWSTR)
        power_handle = self.powrprof.PowerCreateRequest(ctypes.byref(reason_context))
        if not power_handle:
            self._raise_last_error("PowerCreateRequest")
        self._power_handle = power_handle
        for request_type in (PowerRequestExecutionRequired, PowerRequestSystemRequired, PowerRequestAwayModeRequired):
            if not self.powrprof.PowerSetRequest(self._power_handle, request_type):
                self._raise_last_error(f"PowerSetRequest({request_type})")
        details["power_requests"] = "execution+system+away active"
        return LatencyResult(True, details)

    def apply_profile(self, process_name: str = "cs2.exe") -> LatencyResult:
        if not is_admin():
            return LatencyResult(
                False,
                {
                    "error": "Kernel Latency Lock needs Administrator rights "
                    "(token privileges + process handle access).",
                },
            )
        pid = self._pid_by_name(process_name)
        if not pid:
            return LatencyResult(False, {"error": f"{process_name} not found"})
        details: Dict[str, str] = {"pid": str(pid)}
        priv = self.enable_privileges()
        if not priv.ok:
            details.update(priv.details)
            return LatencyResult(False, details)
        details.update(priv.details)
        th = self.disable_process_throttling(pid)
        if not th.ok:
            details.update(th.details)
            return LatencyResult(False, details)
        details.update(th.details)
        sched = self.apply_scheduler_profile(pid)
        if not sched.ok:
            details.update(sched.details)
            return LatencyResult(False, details)
        details.update(sched.details)
        details.update(self.lock_system_latency().details)
        self._active_pid = pid
        return LatencyResult(True, details)

    def release_profile(self) -> LatencyResult:
        details: Dict[str, str] = {}
        if self._power_handle:
            for request_type in (PowerRequestExecutionRequired, PowerRequestSystemRequired, PowerRequestAwayModeRequired):
                self.powrprof.PowerClearRequest(self._power_handle, request_type)
            self.k32.CloseHandle(self._power_handle)
            self._power_handle = wt.HANDLE(0)
            details["power_requests"] = "cleared"

        if self._timer_locked:
            current = wt.ULONG()
            self.ntdll.NtSetTimerResolution(wt.ULONG(TIMER_RESOLUTION_500US), wt.BOOLEAN(False), ctypes.byref(current))
            self._timer_locked = False
            details["timer_resolution"] = "released"
        self._active_pid = None
        return LatencyResult(True, details)

