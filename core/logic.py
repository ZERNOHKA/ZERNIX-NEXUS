import subprocess
import psutil

from core.cleaner import run_deep_clean
from core.kernel_latency import KernelLatencyBooster
from core.security import disable_telemetry_all
from core.tweaks import (
    apply_cs2_competitive_2026_cfg,
    apply_cs2_adaptive_system_profile,
    apply_cpu_turbo,
    apply_extra_performance_tweaks,
    apply_input_latency_tweaks,
    apply_system_stability_tweaks,
    apply_usb_latency_tweaks,
    apply_visual_tweaks,
    apply_zernix_audio_pro,
    apply_zernix_network_registry,
    check_system_status,
    clean_ram,
    clear_directx_shader_cache_2026,
    clear_steam_shader_precache,
    create_full_backup,
    apply_cs2_network_presets,
    apply_pro_telemetry,
    apply_smart_priority_control,
    disable_cfg_for_cs2,
    enable_game_mode,
    enable_ultimate_performance,
    find_cs2_cfg_directory,
    get_cs2_2026_launch_options,
    get_system_info,
    install_cs2_pro_config,
    optimize_network,
    optimize_network_throttling,
    optimize_pagefile,
    optimize_services,
    optimize_system_all,
    apply_source2_pro_optimization,
    apply_realtime_priority_mode,
    rollback_extreme_mode,
    run_turbo_mode_steps,
    restore_system_defaults,
    run_experimental_tweak_safely,
    get_thread_pool_recommendation,
    set_cs2_frametime_telemetry,
    set_max_performance_visuals,
    check_vbs_status,
    disable_vbs_integrity,
    disable_dynamic_tick,
    detect_problematic_kb5077181,
    has_suspicious_debug_tools,
    is_debugger_present,
    verify_exe_integrity,
    restore_network_connectivity,
)

HIDDEN_PROCESS_FLAGS = 0x08000000
_KERNEL_LATENCY = KernelLatencyBooster()


def _run_hidden(command: str):
    return subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        check=False,
        creationflags=HIDDEN_PROCESS_FLAGS,
    )


def create_backup() -> str:
    command = (
        'powershell -NoProfile -ExecutionPolicy Bypass '
        '-Command "Checkpoint-Computer -Description \'ZERNIX_Backup\' -RestorePointType MODIFY_SETTINGS"'
    )
    result = _run_hidden(command)
    if result.returncode == 0:
        return "Restore point created: ZERNIX_Backup."
    details = (result.stderr or result.stdout or "").strip()
    return f"Failed to create restore point. {details}".strip()


def restore_backup() -> str:
    try:
        subprocess.Popen("rstrui.exe", creationflags=HIDDEN_PROCESS_FLAGS)
        return "Windows System Restore wizard opened."
    except Exception as exc:
        return f"Failed to open System Restore wizard: {exc}"


def disable_search_indexer() -> str:
    stop_cmd = _run_hidden("sc stop WSearch")
    disable_cmd = _run_hidden("sc config WSearch start= disabled")
    if disable_cmd.returncode == 0:
        return "Windows Search Indexing disabled."
    details = (disable_cmd.stderr or stop_cmd.stderr or disable_cmd.stdout or "").strip()
    return f"Failed to disable Search Indexing. {details}".strip()


def clear_event_logs() -> str:
    cmd = (
        'powershell -NoProfile -ExecutionPolicy Bypass '
        '-Command "wevtutil el | ForEach-Object { wevtutil cl $_ }"'
    )
    result = _run_hidden(cmd)
    if result.returncode == 0:
        return "Windows Event Logs cleared."
    details = (result.stderr or result.stdout or "").strip()
    return f"Failed to clear Event Logs. {details}".strip()


def optimize_ntfs() -> str:
    commands = [
        "fsutil behavior set disablelastaccess 1",
        "fsutil behavior set memoryusage 2",
    ]
    ok_count = 0
    for cmd in commands:
        if _run_hidden(cmd).returncode == 0:
            ok_count += 1
    if ok_count == len(commands):
        return "NTFS performance optimizations applied."
    return "NTFS optimization partially applied."


def disable_printer_spooler() -> str:
    _run_hidden("sc stop Spooler")
    result = _run_hidden("sc config Spooler start= disabled")
    if result.returncode == 0:
        return "Print Spooler disabled."
    details = (result.stderr or result.stdout or "").strip()
    return f"Failed to disable Print Spooler. {details}".strip()


def install_cs2_config_with_clipboard(clipboard_callback) -> str:
    result = install_cs2_pro_config()
    try:
        launch_options = get_cs2_2026_launch_options()
        clipboard_callback(launch_options)
        return f"{result} | [ZERNIX] Launch options copied to clipboard!"
    except Exception as exc:
        return f"{result} | Clipboard copy failed: {exc}"


def copy_cs2_smart_launch(clipboard_callback) -> str:
    try:
        launch_options = get_cs2_2026_launch_options()
        clipboard_callback(launch_options)
        return "[ZERNIX] Launch options copied to clipboard!"
    except Exception as exc:
        return f"Clipboard copy failed: {exc}"


def run_max_performance_profile() -> str:
    return " | ".join(
        [
            enable_ultimate_performance(),
            set_max_performance_visuals(),
            apply_source2_pro_optimization(),
        ]
    )


def run_gaming_turbo_mode() -> str:
    return " | ".join(run_turbo_mode_steps() + [apply_source2_pro_optimization()])


def run_extreme_rollback() -> str:
    return rollback_extreme_mode()


def run_cybersport_preset() -> str:
    """
    CyberSport (CS2 Focus):
    Maximum focus on input-lag and 1% low FPS.
    """
    steps = [
        apply_cs2_adaptive_system_profile,
        disable_vbs_integrity,
        disable_dynamic_tick,
        apply_realtime_priority_mode,
        apply_source2_pro_optimization,
    ]
    return " | ".join(step() for step in steps)


def run_gaming_turbo_preset() -> str:
    """
    Gaming Turbo:
    Lightweight performance preset for any game, without security/timer tweaks.
    """
    steps = [
        lambda: apply_smart_priority_control(26),
        optimize_services,
        enable_ultimate_performance,
        clean_ram,
    ]
    return " | ".join(step() for step in steps)


def run_work_restore_preset() -> str:
    """
    Work / Restore:
    Full rollback to Windows-like defaults after the gaming session.
    """
    steps = [
        _KERNEL_LATENCY.release_profile,
        restore_system_defaults,
    ]
    results = []
    for step in steps:
        result = step()
        results.append(str(result))
    return " | ".join(results)


def apply_kernel_latency_boost(process_name: str = "cs2.exe") -> str:
    result = _KERNEL_LATENCY.apply_profile(process_name)
    if result.ok:
        return "[ZERNIX] Kernel latency profile ON: " + ", ".join(f"{k}={v}" for k, v in result.details.items())
    return "[ZERNIX] Kernel latency profile failed: " + ", ".join(f"{k}={v}" for k, v in result.details.items())


def apply_kernel_latency_boost_if_running(process_name: str = "cs2.exe") -> str:
    target = process_name.lower()
    for proc in psutil.process_iter(["name"]):
        if str((proc.info or {}).get("name") or "").lower() == target:
            return apply_kernel_latency_boost(process_name)
    return f"[ZERNIX] Kernel latency profile skipped: {process_name} is not running."


def release_kernel_latency_boost() -> str:
    result = _KERNEL_LATENCY.release_profile()
    if result.ok:
        if not result.details:
            return "[ZERNIX] Kernel latency profile already released."
        return "[ZERNIX] Kernel latency profile OFF: " + ", ".join(f"{k}={v}" for k, v in result.details.items())
    return "[ZERNIX] Kernel latency release failed."


__all__ = [
    "run_cybersport_preset",
    "run_gaming_turbo_preset",
    "run_work_restore_preset",
    "apply_cs2_adaptive_system_profile",
]
