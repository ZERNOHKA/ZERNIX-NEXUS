import ctypes
import subprocess
import threading
import time
import webbrowser
import winreg
import tkinter as tk
from tkinter import messagebox
import os
import re
import sys
from typing import Optional
import customtkinter as ctk
import psutil

from licensing import (
    DEMO_MODE_RESULT,
    LICENSE_FILE as SERVER_LICENSE_PATH,
    OFFLINE_ROLLBACK_RESULT,
    check_license,
    ensure_license_or_exit,
    get_hwid as get_server_hwid,
    read_saved_license_key,
    save_license_key,
)

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

# Replace with your public Telegram channel invite link.
ZERNIX_TELEGRAM_URL = "https://t.me/zernix_soft"

from core.logic import (
    apply_cs2_competitive_2026_cfg,
    apply_cs2_adaptive_system_profile,
    apply_cpu_turbo,
    apply_cs2_network_presets,
    apply_extra_performance_tweaks,
    apply_input_latency_tweaks,
    apply_system_stability_tweaks,
    apply_usb_latency_tweaks,
    apply_visual_tweaks,
    apply_zernix_audio_pro,
    apply_zernix_network_registry,
    check_system_status,
    clear_event_logs,
    clean_ram,
    clear_directx_shader_cache_2026,
    clear_steam_shader_precache,
    copy_cs2_smart_launch,
    create_backup,
    create_full_backup,
    disable_cfg_for_cs2,
    disable_printer_spooler,
    disable_search_indexer,
    disable_telemetry_all,
    enable_game_mode,
    get_system_info,
    install_cs2_config_with_clipboard,
    optimize_network,
    optimize_ntfs,
    optimize_pagefile,
    optimize_services,
    optimize_system_all,
    run_deep_clean,
    restore_backup,
    restore_network_connectivity,
    restore_system_defaults,
    run_experimental_tweak_safely,
    run_gaming_turbo_mode,
    run_gaming_turbo_preset,
    run_cybersport_preset,
    run_work_restore_preset,
    run_extreme_rollback,
    run_max_performance_profile,
    apply_pro_telemetry,
    apply_source2_pro_optimization,
    apply_smart_priority_control,
    apply_kernel_latency_boost,
    apply_kernel_latency_boost_if_running,
    get_thread_pool_recommendation,
    release_kernel_latency_boost,
    set_cs2_frametime_telemetry,
    has_suspicious_debug_tools,
    is_debugger_present,
    verify_exe_integrity,
)
from core.utils import resource_path
from ui.assets import load_ui_assets
from ui.widgets import bind_license_entry_hotkeys
from ui.screens import AdvancedFrame, DashboardFrame, LicenseFrame
from ui.styles import Theme

LICENSE_REG_PATH = r"Software\\NovaBoostPro"
LICENSE_REG_VALUE = "LicenseKey"
LICENSE_REG_BACKUP_REMINDER = "BackupReminderShown"
HIDDEN_PROCESS_FLAGS = 0x08000000
_OFFLINE_ROLLBACK_ALLOWED_ACTIONS = frozenset(
    {
        "rollback_after_gaming",
        "reset_to_default",
        "extreme_rollback",
        "restore_system",
        "network_stack_restore",
        "network_fix",
        "create_restore_point",
        "gaming_kernel_latency_off",
    }
)

FACEIT_RISKY_ACTIONS = {
    "cs2_session_boost",
    "privacy",
    "clear_event_logs",
    "optimize_services",
    "gaming_turbo_mode",
    "gaming_kernel_latency_on",
    "gaming_disable_cfg",
    "cybersport",
    "gaming_turbo",
}


ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


def detect_windows_ui_language() -> str:
    """Use Russian only for Russian Windows UI; default every other locale to English."""
    try:
        lang_id = int(ctypes.windll.kernel32.GetUserDefaultUILanguage())
        primary_lang = lang_id & 0x3FF
        if primary_lang == 0x19:
            return "ru"
    except Exception:
        pass
    return "en"


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


class NovaBoostApp(ctk.CTk):
    def _apply_window_icon(self):
        try:
            icon_path = resource_path(os.path.join("assets", "logotip.ico"))
            if os.path.isfile(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass
        try:
            png_icon_path = resource_path(os.path.join("assets", "logo_z.png"))
            if os.path.isfile(png_icon_path):
                self._window_icon_image = tk.PhotoImage(file=png_icon_path)
                self.iconphoto(True, self._window_icon_image)
        except Exception:
            pass

    def _safe_get_system_info(self):
        fallback = {"os": "Loading...", "cpu": "Loading...", "gpu": "Loading...", "ram": "Loading..."}
        try:
            info = get_system_info() or {}
            if isinstance(info, dict):
                fallback.update({k: info.get(k, fallback[k]) for k in fallback})
        except Exception:
            pass
        return fallback

    def _get_gpu_stats(self):
        now = time.time()
        if (now - self._gpu_probe_ts) < 1.8:
            return self._cached_gpu_usage, self._cached_gpu_temp
        try:
            result = subprocess.run(
                'nvidia-smi --query-gpu=utilization.gpu,temperature.gpu --format=csv,noheader,nounits',
                shell=True,
                capture_output=True,
                text=True,
                check=False,
                creationflags=HIDDEN_PROCESS_FLAGS,
            )
            raw = (result.stdout or "").strip().splitlines()
            if raw:
                parts = [part.strip() for part in raw[0].split(",")]
                usage = float(parts[0]) if parts and parts[0] else None
                temp = float(parts[1]) if len(parts) > 1 and parts[1] else None
                self._cached_gpu_usage = usage
                self._cached_gpu_temp = temp
                self._gpu_probe_ts = now
                return usage, temp
        except Exception:
            pass
        self._gpu_probe_ts = now
        return self._cached_gpu_usage, self._cached_gpu_temp

    def _get_cpu_temp(self):
        try:
            sensors = psutil.sensors_temperatures(fahrenheit=False) or {}
        except Exception:
            sensors = {}
        if not sensors:
            sensors = {}
        preferred = ("coretemp", "k10temp", "cpu_thermal", "acpitz")
        entries = []
        for key in preferred:
            entries.extend(sensors.get(key, []))
        if not entries:
            for values in sensors.values():
                entries.extend(values or [])
        temps = []
        for item in entries:
            value = getattr(item, "current", None)
            if value is None:
                continue
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue
            if -10.0 <= value <= 130.0:
                temps.append(value)
        if temps:
            return max(temps)
        # Fallback for many Windows systems where psutil sensors are unavailable.
        try:
            result = subprocess.run(
                "wmic /namespace:\\\\root\\wmi PATH MSAcpi_ThermalZoneTemperature get CurrentTemperature /value",
                shell=True,
                capture_output=True,
                text=True,
                check=False,
                creationflags=HIDDEN_PROCESS_FLAGS,
            )
            values = []
            for line in (result.stdout or "").splitlines():
                if "=" not in line:
                    continue
                _, raw = line.split("=", 1)
                raw = raw.strip()
                if not raw.isdigit():
                    continue
                kelvin_x10 = float(raw)
                celsius = (kelvin_x10 / 10.0) - 273.15
                if -10.0 <= celsius <= 130.0:
                    values.append(celsius)
            if values:
                return max(values)
        except Exception:
            pass
        return None

    def _get_hardware_snapshot(self):
        try:
            cpu = psutil.cpu_percent(interval=None)
        except Exception:
            cpu = 0.0
        try:
            vm = psutil.virtual_memory()
            ram = vm.percent
            ram_total_gb = vm.total / (1024 ** 3)
            ram_used_gb = vm.used / (1024 ** 3)
        except Exception:
            ram = 0.0
            ram_total_gb = None
            ram_used_gb = None
        cpu_temp = self._get_cpu_temp()
        gpu, gpu_temp = self._get_gpu_stats()
        if gpu is None:
            gpu = self._last_known_gpu_usage
            gpu_available = self._gpu_source_available
        else:
            self._last_known_gpu_usage = float(gpu)
            self._gpu_source_available = True
            gpu_available = True
        if not gpu_available:
            gpu_temp = None
        return {
            "cpu": cpu,
            "gpu": gpu,
            "ram": ram,
            "gpu_available": gpu_available,
            "cpu_temp": cpu_temp,
            "gpu_temp": gpu_temp,
            "ram_total_gb": ram_total_gb,
            "ram_used_gb": ram_used_gb,
        }

    def _hardware_worker_loop(self):
        while True:
            try:
                snapshot = self._get_hardware_snapshot()
                with self._hardware_lock:
                    self._hardware_snapshot_cache = snapshot
            except Exception:
                pass
            time.sleep(3.0)

    def _get_cached_hardware_snapshot(self):
        with self._hardware_lock:
            snapshot = dict(self._hardware_snapshot_cache)
        return snapshot

    def _refresh_status_cards_worker(self):
        try:
            snapshot = check_system_status()
        except Exception as exc:
            self.after(0, lambda: self._append_log(f"Status refresh failed: {exc}"))
        else:
            self.after(0, lambda data=snapshot: self.dashboard_page.refresh_status_cards(data, self.current_language))
            if snapshot.get("secure_boot_enabled") is False and not self._secure_boot_warned:
                warn = snapshot.get("secure_boot_message") or "Secure Boot OFF: Возможен низкий Trust Factor в VAC Live"
                self.after(0, lambda text=warn: self._append_log(f"⚠️ {text}"))
                self._secure_boot_warned = True
        finally:
            self._status_refresh_in_flight = False

    def _center_window(self, width: int, height: int):
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        pos_x = max(0, (screen_w - width) // 2)
        pos_y = max(0, (screen_h - height) // 2)
        self.geometry(f"{width}x{height}+{pos_x}+{pos_y}")

    def _clipboard_callback(self, text: str):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update_idletasks()

    def _save_registry_license_key(self, key: str):
        token = (key or "").strip()
        if not token:
            return
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, LICENSE_REG_PATH) as reg_key:
                winreg.SetValueEx(reg_key, LICENSE_REG_VALUE, 0, winreg.REG_SZ, token)
        except OSError:
            pass

    def _clear_registry_license_key(self):
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, LICENSE_REG_PATH) as reg_key:
                winreg.DeleteValue(reg_key, LICENSE_REG_VALUE)
        except OSError:
            pass

    def _load_registry_license_key(self) -> str:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, LICENSE_REG_PATH, 0, winreg.KEY_READ) as reg_key:
                value, _ = winreg.QueryValueEx(reg_key, LICENSE_REG_VALUE)
                return str(value).strip()
        except OSError:
            return ""

    def _has_backup_reminder_been_shown(self) -> bool:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, LICENSE_REG_PATH, 0, winreg.KEY_READ) as reg_key:
                value, _ = winreg.QueryValueEx(reg_key, LICENSE_REG_BACKUP_REMINDER)
                return int(value) == 1
        except OSError:
            return False

    def _set_backup_reminder_shown(self):
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, LICENSE_REG_PATH) as reg_key:
                winreg.SetValueEx(reg_key, LICENSE_REG_BACKUP_REMINDER, 0, winreg.REG_DWORD, 1)
        except OSError:
            pass

    def _clear_backup_reminder_flag(self):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, LICENSE_REG_PATH, 0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE) as reg_key:
                winreg.DeleteValue(reg_key, LICENSE_REG_BACKUP_REMINDER)
        except OSError:
            pass

    def _offer_first_activation_backup_if_needed(self):
        if self._has_backup_reminder_been_shown():
            return
        try:
            accept = messagebox.askyesno(self.tr("backup_prompt_title"), self.tr("backup_prompt_message"))
        finally:
            self._set_backup_reminder_shown()
        if accept:
            self._start_async_action(self.tr("create_restore_point"), create_backup)

    def _schedule_first_activation_backup_prompt(self):
        self.after(250, self._offer_first_activation_backup_if_needed)

    def _has_valid_license(self) -> bool:
        return bool(read_saved_license_key())

    def __init__(self, offline_rollback: bool = False, demo_mode: bool = False):
        super().__init__()
        self._offline_rollback = bool(offline_rollback)
        self._demo_mode = bool(demo_mode)
        self.title("ZERNIX NEXUS | CS2 BOOST")
        self._apply_window_icon()
        self._center_window(1080, 780)
        self.minsize(1080, 780)
        self.maxsize(1080, 780)
        self.resizable(False, False)
        self.configure(fg_color=Theme.COLORS["app_bg"])
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        self.current_language = detect_windows_ui_language()
        self.status_log_lines = []
        self._max_console_lines = 400
        self.system_info = self._safe_get_system_info()
        self.nav_buttons = {}
        self.pages = {}
        self.current_page_key = None
        self._max_parallel_actions = 2
        self._active_actions = 0
        self._action_lock = threading.Lock()
        self._hardware_lock = threading.Lock()
        self._hardware_snapshot_cache = {"cpu": 0.0, "gpu": 0.0, "ram": 0.0}
        self._last_known_gpu_usage = 0.0
        self._gpu_source_available = False
        self._cached_gpu_usage = None
        self._cached_gpu_temp = None
        self._gpu_probe_ts = 0.0
        self._status_refresh_in_flight = False
        self.license_overlay = None
        self._secure_boot_warned = False
        self._experimental_functions = {
            apply_input_latency_tweaks,
            optimize_services,
            run_max_performance_profile,
            apply_cpu_turbo,
        }
        self.translations = {
            "en": {
                "tab_home": "Home",
                "tab_advanced": "Advanced",
                "tab_license": "License",
                "language_button": "EN/RU",
                "hero_title": "ZERNIX NEXUS · CS2 BOOST",
                "hero_subtitle": "Boost your PC for Counter-Strike 2, then restore everyday Windows defaults when you are finished. On laptops, plug in AC power for best results from performance power plans.",
                "btn_session_boost": "CS2 SESSION BOOST",
                "btn_session_rollback": "RESTORE SETTINGS",
                "session_boost_hint": "Runs the full optimization pipeline: restore snapshot first, then latency, network, CPU and game-oriented tweaks.",
                "rollback_hint": "Brings services and power profile closer to normal desktop use — use after your session.",
                "monitoring_title": "System Monitoring",
                "quick_mode_title": "Mode",
                "quick_mode_value": "CS2 BOOST",
                "quick_profile_title": "Profile",
                "quick_profile_value": "Optimal",
                "quick_services_title": "Services",
                "quick_services_value": "Optimized",
                "quick_power_title": "Power",
                "quick_power_value": "High performance",
                "temperature_na": "Temperature: --°C",
                "temperature_value": "Temperature: {value}°C",
                "advanced_title": "Advanced tools",
                "advanced_subtitle": "Manual tweaks, CS2 shortcuts, shader cache, and profiles — for users who want fine control.",
                "advanced_system_tab": "System",
                "advanced_gaming_tab": "CS2 & gaming",
                "advanced_presets_tab": "Presets",
                "diagnostics": "Diagnostics",
                "console_header": "Console Output",
                "valve_ping": "Valve Ping (Stockholm): Waiting",
                "dashboard_system": "System",
                "dashboard_gaming": "Gaming",
                "cpu_usage": "CPU Usage",
                "gpu_usage": "GPU Usage",
                "ram_usage": "RAM Usage",
                "latency": "Latency",
                "responsiveness": "Responsiveness",
                "console_ready": "System ready. Waiting for commands...",
                "system_title": "System",
                "gaming_title": "Gaming",
                "license_title": "License",
                "license_status": "Status",
                "license_active": "Activated",
                "license_inactive": "Not activated",
                "license_file": "License file",
                "license_activate": "Activate License",
                "license_remove": "Remove key and re-activate",
                "license_server_hint": "Enter the license key issued by your ZERNIX license server for this HWID.",
                "license_hwid_copied": "HWID copied to clipboard.",
                "license_placeholder": "Enter license key",
                "section_system_optimization": "System optimization",
                "section_gpu": self.system_info.get("gpu", "Loading..."),
                "section_nvidia": "NVIDIA Gaming Settings",
                "section_advanced": "General Advanced Settings",
                "clear_cache": "Clear Cache",
                "dns_flush": "DNS Flush",
                "startup_tune": "Startup Tune",
                "pagefile": "Pagefile",
                "restore_defaults": "Restore Defaults",
                "create_backup": "Create Backup",
                "global_boost": "Global Boost",
                "input_lag": "Input Lag",
                "usb_latency": "USB Latency",
                "visual_tweaks": "Visual Tweaks",
                "system_stability": "System Stability",
                "privacy": "Privacy",
                "network_fix": "Network Fix",
                "clean_junk": "Clean Junk",
                "clean_ram": "Clean RAM",
                "optimize_services": "Optimize Services",
                "max_performance": "Max Performance",
                "optimize_pagefile": "Optimize Pagefile",
                "apply_cpu_turbo": "Apply CPU Turbo",
                "extreme_rollback": "Extreme Rollback",
                "run_action": "Run",
                "run_btn": "Run",
                "backup_action": "Backup",
                "restore_action": "Restore",
                "reset_action": "Reset",
                "optimization_settings": "Optimization Settings",
                "create_restore_point": "Create Restore Point",
                "restore_system": "Restore System",
                "reset_to_default": "Reset to Default",
                "desc_create_restore_point": "Create a system snapshot before applying tweaks.",
                "desc_restore_system": "Roll back your PC to a previous state using Windows Restore.",
                "desc_reset_to_default": "Revert all optimization settings to Windows factory defaults.",
                "disable_search_indexer": "Disable Search Indexer",
                "desc_search": "Disable Windows Search indexing service to reduce background disk usage.",
                "clear_event_logs": "Clear Event Logs",
                "desc_logs": "Clear Windows Event Logs to remove stale diagnostics and reduce log bloat.",
                "optimize_ntfs": "Optimize NTFS",
                "desc_ntfs": "Apply safe NTFS behavior settings for lower file-system overhead.",
                "disable_printer_spooler": "Disable Printer Spooler",
                "desc_spooler": "Disable Print Spooler service on systems that do not use printers.",
                "desc_create_backup": "Create a restore snapshot before applying any aggressive changes.",
                "desc_global_boost": "Apply Smart Priority (Win32PrioritySeparation), Ultimate Performance power plan, and per-interface network registry tuning.",
                "desc_input_lag": "Registry-only (Faceit-safe): MMCSS + Games scheduling, power throttling off, DVR/App Capture off, desktop mouse accel off, menu delay; reset via Reset to defaults.",
                "desc_usb_latency": "Disable USB selective suspend and tighten USB responsiveness.",
                "desc_visual_tweaks": "Reduce transparency and extra visual effects for lower overhead.",
                "desc_system_stability": "Apply MPO and graphics scheduler changes for stability and latency.",
                "desc_privacy": "Disable telemetry and tracking services quietly in the background.",
                "desc_network_fix": "Refresh TCP settings and enable the faster network profile.",
                "desc_clean_junk": "Remove temporary system junk and clean common cache folders.",
                "desc_clean_ram": "Trim working sets and free RAM pressure across processes.",
                "desc_optimize_services": "Disable non-essential background services for gaming focus.",
                "desc_max_performance": "Force the highest visual and power-performance configuration.",
                "desc_optimize_pagefile": "Tune the Windows pagefile size based on installed memory.",
                "desc_apply_cpu_turbo": "Raise minimum CPU performance and disable core parking.",
                "desc_extreme_rollback": "Revert Extreme Mode changes: VBS, Dynamic Tick and realtime priority tuning.",
                "gaming_info": "Optimization Status: Ready | Network Stability: Stable",
                "network_stability": "Network Stability",
                "optimization_status": "Optimization Status",
                "gaming_install_cs2": "Install CS2 Pro Config",
                "gaming_disable_cfg": "Disable CFG for CS2",
                "gaming_frametime": "Frame Time Telemetry",
                "gaming_dx_cache": "DirectX Shader Cache",
                "gaming_steam_cache": "Steam Shader Pre-cache",
                "gaming_turbo_mode": "Turbo Mode",
                "gaming_network_diagnostic": "Network Diagnostic",
                "gaming_network_registry": "Network Registry Pro",
                "gaming_audio_pro": "Audio Pro",
                "gaming_install": "Install",
                "gaming_disable": "Disable",
                "gaming_enable": "Enable",
                "gaming_clear": "Clear",
                "gaming_run": "Run",
                "gaming_install_action": "Install",
                "gaming_disable_action": "Disable",
                "gaming_enable_action": "Enable",
                "gaming_clear_action": "Clear",
                "gaming_run_action": "Run",
                "gaming_smart_launch": "CS2 Smart Launch",
                "gaming_pro_telemetry": "Pro Telemetry",
                "gaming_kernel_latency_on": "Kernel Latency Lock (CS2)",
                "gaming_kernel_latency_off": "Release Kernel Latency Lock",
                "desc_gaming_install_cs2": "Write the tuned CS2 config and apply related fullscreen and shader cache adjustments.",
                "desc_gaming_disable_cfg": "Toggle the mitigation profile used by cs2.exe for reduced overhead where supported.",
                "desc_gaming_frametime": "Enable the frame-time HUD line in CS2 for real-time frametime monitoring.",
                "desc_gaming_dx_cache": "Clear Windows DirectX shader cache to rebuild stale shader data.",
                "desc_gaming_steam_cache": "Purge Steam shader pre-cache folders across detected libraries.",
                "desc_gaming_turbo_mode": "Run the combined quick gaming routine from the existing backend flow.",
                "desc_gaming_network_diagnostic": "Measure ping and route health to DNS and Valve endpoints before applying network tweaks.",
                "desc_gaming_network_registry": "Apply TCP ACK and TCPNoDelay per adapter; gentle NetworkThrottlingIndex (safer for Discord/VPN).",
                "desc_gaming_audio_pro": "Apply Source 2 spatial audio tuning: crisp footsteps, L/R separation, and voice mute bind.",
                "desc_gaming_smart_launch": "Copy the recommended low-latency CS2 launch string directly to the Windows clipboard.",
                "desc_gaming_pro_telemetry": "Enable advanced CS2 telemetry HUD lines for frametime and network diagnostics.",
                "desc_gaming_kernel_latency_on": "Enable aggressive user-mode kernel latency profile for cs2.exe: disable process throttling, raise scheduling pressure, lock timer resolution and power requests.",
                "desc_gaming_kernel_latency_off": "Release kernel latency locks and restore normal timer/power request behavior.",
                "clipboard_cs2": "[ZERNIX] Launch options copied to clipboard!",
                "presets_title": "Smart Presets",
                "presets_subtitle": "CyberSport (CS2), Gaming Turbo, or Work/Restore — same as on the Home screen rollback, but selectable here.",
                "preset_safe_block": "Safe to auto-apply",
                "preset_apply_button": "Apply safe preset",
                "preset_caution_block": "Use with caution (manual)",
                "preset_cybersport_title": "CyberSport (CS2 Focus)",
                "preset_cybersport_safe_actions": "• Source 2 Pro optimization\n• Realtime game priority\n• 1% low and input-lag tuning",
                "preset_cybersport_caution_actions": "• Disables Memory Integrity (VBS) unless Developer toggle is on\n• Runs bcdedit (Dynamic Tick) — separate from virtualization guest services\n• May require reboot\n• Anti-cheat / org policies may object\n• Enable Developer toggle to keep Docker/VM Hyper-V integration services",
                "preset_cybersport_confirm_title": "CyberSport — high-impact steps",
                "preset_cybersport_confirm_text": "This preset disables VBS-related integrity settings and changes boot/timer policy (bcdedit). Continue only if you accept reduced Windows hardening and possible reboot. Continue?",
                "preset_gaming_turbo_title": "Gaming Turbo",
                "preset_gaming_turbo_safe_actions": "• Smart priority (26)\n• Service optimization\n• Ultimate Performance power plan\n• RAM cleanup",
                "preset_gaming_turbo_caution_actions": "• Does not touch VBS or Dynamic Tick\n• Recommended for any modern game",
                "preset_work_restore_title": "Work / Restore",
                "preset_work_restore_safe_actions": "• Extreme rollback\n• Restore service defaults\n• Switch to Balanced power plan",
                "preset_work_restore_caution_actions": "• Does not restore CS2 autoexec.cfg or process mitigations\n• Does not revert netsh TCP globals from Network Fix\n• Returns system closer to stock behavior\n• Recommended before work/study/VM usage",
                "telegram_title": "Stay Updated",
                "telegram_desc": "Updates and tips for ZERNIX NEXUS.",
                "telegram_join": "Join Telegram >",
                "backup_prompt_title": "Create a system backup?",
                "backup_prompt_message": "Before using optimization tools, we recommend creating a Windows restore point. This lets you roll back system changes if something goes wrong.\n\nCreate a restore point now?",
                "experimental_warning_title": "Experimental tweak",
                "experimental_warning_text": "{action} is marked as Experimental. It is not included in auto presets because it can reduce performance on already-optimized systems.\n\nApply manually anyway?",
                "admin_warning": "ZERNIX is running without Administrator rights. The UI will open, but registry changes will not be applied.",
                "faceit_risky_title": "FACEIT compatibility warning",
                "faceit_risky_text": "{action} can change services, boot/security settings, process mitigations, or process priority. FACEIT AC can block the game or flag unsupported system changes.\n\nApply this tweak anyway?",
                "faceit_blocked": "{action}: blocked while FACEIT Anti-Cheat is running. Close FACEIT AC first or use Restore Settings.",
                "offline_rollback_banner": "Offline rollback mode: boosts and presets are limited — use Restore / Network repair below.",
                "offline_action_blocked": "Unavailable in offline rollback mode. Restart ZERNIX normally when online.",
                "network_stack_restore": "Restore Network / VPN / WMI",
                "desc_network_stack_restore": "Re-enable core network and WMI services, reset TCP autotuning, flush DNS — after bad tweaks or broken VPN.",
                "preset_developer_vm": "Developer: keep Hyper-V / virtualization (skip VBS-off + Hyper-V guest services)",
                "kernel_latency_need_admin": "Kernel Latency Lock requires running ZERNIX as Administrator (token + process access).",
                "kernel_latency_warn_title": "Kernel Latency Lock",
            },
            "ru": {
                "tab_home": "Главная",
                "tab_advanced": "Дополнительно",
                "tab_license": "Лицензия",
                "language_button": "RU/EN",
                "hero_title": "ZERNIX NEXUS · CS2 BOOST",
                "hero_subtitle": "Буст ПК для Counter-Strike 2 — затем верните привычные настройки Windows после игры. На ноутбуке подключите питание от сети для лучшего эффекта схем электропитания.",
                "btn_session_boost": "БУСТ CS2",
                "btn_session_rollback": "ОТКАТ ПОСЛЕ ИГРЫ",
                "session_boost_hint": "Запускает полный пайплайн: снимок восстановления, задержки, сеть, CPU и игровые твики.",
                "rollback_hint": "Возвращает службы и план питания ближе к обычной работе — нажмите после сессии.",
                "monitoring_title": "Мониторинг системы",
                "quick_mode_title": "Режим",
                "quick_mode_value": "CS2 BOOST",
                "quick_profile_title": "Профиль",
                "quick_profile_value": "Оптимальный",
                "quick_services_title": "Службы",
                "quick_services_value": "Оптимизированы",
                "quick_power_title": "Питание",
                "quick_power_value": "Высокая производительность",
                "temperature_na": "Температура: --°C",
                "temperature_value": "Температура: {value}°C",
                "advanced_title": "Дополнительные инструменты",
                "advanced_subtitle": "Ручные твики, CS2, кэш шейдеров и профили — для тех, кому нужен полный контроль.",
                "advanced_system_tab": "Система",
                "advanced_gaming_tab": "CS2 и игры",
                "advanced_presets_tab": "Профили",
                "diagnostics": "Диагностика",
                "console_header": "Вывод консоли",
                "valve_ping": "Valve Ping (Стокгольм): Ожидание",
                "dashboard_system": "Система",
                "dashboard_gaming": "Игры / CS2",
                "cpu_usage": "Загрузка CPU",
                "gpu_usage": "Загрузка GPU",
                "ram_usage": "Загрузка RAM",
                "latency": "Задержка",
                "responsiveness": "Отзывчивость",
                "console_ready": "Готово к командам…",
                "system_title": "Система",
                "gaming_title": "CS2 и игры",
                "license_title": "Лицензия",
                "license_status": "Статус",
                "license_active": "Активирована",
                "license_inactive": "Не активирована",
                "license_file": "Файл лицензии",
                "license_activate": "Активировать лицензию",
                "license_remove": "Удалить ключ и активировать заново",
                "license_server_hint": "Введите ключ лицензии, выданный сервером ZERNIX для этого HWID.",
                "license_hwid_copied": "HWID скопирован в буфер обмена.",
                "license_placeholder": "Введите лицензионный ключ",
                "section_system_optimization": "System optimization",
                "section_gpu": self.system_info.get("gpu", "Loading..."),
                "section_nvidia": "NVIDIA Gaming Settings",
                "section_advanced": "General Advanced Settings",
                "clear_cache": "Очистить кэш",
                "dns_flush": "Сброс DNS",
                "startup_tune": "Тюнинг старта",
                "pagefile": "Файл подкачки",
                "restore_defaults": "Сбросить настройки",
                "create_backup": "Создать бэкап",
                "global_boost": "Глобальный буст",
                "input_lag": "Снижение Input Lag",
                "usb_latency": "USB Latency",
                "visual_tweaks": "Визуальные твики",
                "system_stability": "Стабильность системы",
                "privacy": "Приватность",
                "network_fix": "Исправление сети",
                "clean_junk": "Очистка мусора",
                "clean_ram": "Очистка RAM",
                "optimize_services": "Оптимизация служб",
                "max_performance": "Максимальная производительность",
                "optimize_pagefile": "Оптимизация pagefile",
                "apply_cpu_turbo": "CPU Turbo",
                "extreme_rollback": "Extreme Rollback",
                "run_action": "Запуск",
                "run_btn": "Запуск",
                "backup_action": "Бэкап",
                "restore_action": "Восстановить",
                "reset_action": "Сброс",
                "optimization_settings": "Настройки оптимизации",
                "create_restore_point": "Создать точку восстановления",
                "restore_system": "Восстановить систему",
                "reset_to_default": "Сброс к умолчанию",
                "desc_create_restore_point": "Создать снимок системы перед применением твиков.",
                "desc_restore_system": "Откатить ПК к предыдущему состоянию через восстановление Windows.",
                "desc_reset_to_default": "Вернуть все оптимизационные параметры к заводским настройкам Windows.",
                "disable_search_indexer": "Отключить индексатор поиска",
                "desc_search": "Отключить службу индексации Windows Search для снижения фоновой нагрузки на диск.",
                "clear_event_logs": "Очистить журналы событий",
                "desc_logs": "Очистить журналы событий Windows, удалив устаревшие диагностические записи.",
                "optimize_ntfs": "Оптимизация NTFS",
                "desc_ntfs": "Применить безопасные параметры NTFS для снижения накладных расходов ФС.",
                "disable_printer_spooler": "Отключить диспетчер печати",
                "desc_spooler": "Отключить службу Print Spooler на системах без принтера.",
                "desc_create_backup": "Создать точку восстановления перед применением агрессивных изменений.",
                "desc_global_boost": "Smart Priority (Win32PrioritySeparation), схема Ultimate Performance и сетевой реестр по интерфейсам.",
                "desc_input_lag": "Только реестр (Faceit-safe): MMCSS + профиль Games, отключение Dynamic Power Throttling, DVR/App Capture, ускорение мыши Windows и задержки меню; сброс через «Сброс к умолчанию».",
                "desc_usb_latency": "Отключить USB Selective Suspend и улучшить отклик USB.",
                "desc_visual_tweaks": "Снизить нагрузку за счет отключения лишних визуальных эффектов.",
                "desc_system_stability": "Применить MPO и графические твики для стабильности и задержки.",
                "desc_privacy": "Отключить телеметрию и службы слежения в фоновом режиме.",
                "desc_network_fix": "Обновить TCP-параметры и включить быстрый сетевой профиль.",
                "desc_clean_junk": "Очистить временные файлы и распространенные кэш-папки системы.",
                "desc_clean_ram": "Очистить рабочие наборы процессов и снять давление на RAM.",
                "desc_optimize_services": "Отключить лишние фоновые службы для игрового профиля.",
                "desc_max_performance": "Включить максимально производительный режим питания и визуальных настроек.",
                "desc_optimize_pagefile": "Оптимизировать файл подкачки на основе объема установленной памяти.",
                "desc_apply_cpu_turbo": "Повысить минимум производительности CPU и отключить парковку ядер.",
                "desc_extreme_rollback": "Откатить изменения Extreme Mode: VBS, Dynamic Tick и realtime-приоритеты.",
                "gaming_info": "Статус оптимизации: Готово | Стабильность сети: Стабильно",
                "network_stability": "Стабильность сети",
                "optimization_status": "Статус оптимизации",
                "gaming_install_cs2": "Установить CS2 Pro Config",
                "gaming_disable_cfg": "Отключить CFG для CS2",
                "gaming_frametime": "Телеметрия Frametime",
                "gaming_dx_cache": "Кэш шейдеров DirectX",
                "gaming_steam_cache": "Steam shader pre-cache",
                "gaming_turbo_mode": "Турбо-режим",
                "gaming_network_diagnostic": "Диагностика сети",
                "gaming_network_registry": "Network Registry Pro",
                "gaming_audio_pro": "Audio Pro",
                "gaming_install": "Установить",
                "gaming_disable": "Отключить",
                "gaming_enable": "Включить",
                "gaming_clear": "Очистить",
                "gaming_run": "Запуск",
                "gaming_install_action": "Установить",
                "gaming_disable_action": "Отключить",
                "gaming_enable_action": "Включить",
                "gaming_clear_action": "Очистить",
                "gaming_run_action": "Запуск",
                "gaming_smart_launch": "CS2 Smart Launch",
                "gaming_pro_telemetry": "Pro Telemetry",
                "gaming_kernel_latency_on": "Kernel Latency Lock (CS2)",
                "gaming_kernel_latency_off": "Отключить Kernel Latency Lock",
                "desc_gaming_install_cs2": "Записать конфиг CS2 и применить связанные твики полноэкранного режима и шейдерного кэша.",
                "desc_gaming_disable_cfg": "Переключить профиль mitigations для cs2.exe для снижения накладных расходов.",
                "desc_gaming_frametime": "Включить линию frametime в HUD CS2 для мониторинга микрофризов.",
                "desc_gaming_dx_cache": "Очистить кэш шейдеров DirectX для пересборки устаревших данных.",
                "desc_gaming_steam_cache": "Очистить папки shader pre-cache Steam во всех найденных библиотеках.",
                "desc_gaming_turbo_mode": "Запустить объединенный турбо-сценарий из существующего backend-пайплайна.",
                "desc_gaming_network_diagnostic": "Проверить пинг и маршрут до DNS/Valve перед применением сетевых твиков.",
                "desc_gaming_network_registry": "TCP ACK и TCPNoDelay по интерфейсам; мягкий NetworkThrottlingIndex (меньше риска для Discord/VPN).",
                "desc_gaming_audio_pro": "Настроить Source 2 audio: четкие шаги, L/R позиционирование и бинд mute voice.",
                "desc_gaming_smart_launch": "Скопировать рекомендуемую низколатентную строку запуска CS2 прямо в буфер обмена Windows.",
                "desc_gaming_pro_telemetry": "Включить расширенный HUD телеметрии CS2 для frametime и сетевой диагностики.",
                "desc_gaming_kernel_latency_on": "Включить агрессивный kernel latency профиль для cs2.exe: отключение process throttling, усиление планировщика, lock таймера и power requests.",
                "desc_gaming_kernel_latency_off": "Снять kernel latency lock и вернуть обычное поведение timer/power requests.",
                "clipboard_cs2": "[ZERNIX] Launch options copied to clipboard!",
                "presets_title": "Умные пресеты",
                "presets_subtitle": "CyberSport (CS2), Gaming Turbo или Work/Restore — как кнопка «вернуть ПК» на главной, но выбор профиля здесь.",
                "preset_safe_block": "Безопасно применять автоматически",
                "preset_apply_button": "Применить безопасный пресет",
                "preset_caution_block": "С осторожностью (вручную)",
                "preset_cybersport_title": "CyberSport (CS2 Focus)",
                "preset_cybersport_safe_actions": "• Source 2 Pro оптимизация\n• Realtime-приоритет игры\n• Тюнинг 1% low и input-lag",
                "preset_cybersport_caution_actions": "• Отключает VBS, если не включён «Режим разработчика»\n• Запускает bcdedit (Dynamic Tick), не то же самое, что гостевые службы Hyper-V\n• Может потребоваться перезагрузка\n• Для Docker/VM отметьте переключатель разработчика (не трогать vmic* / VBS)",
                "preset_cybersport_confirm_title": "CyberSport — критические шаги",
                "preset_cybersport_confirm_text": "Этот пресет отключает настройки целостности (VBS) и меняет политику загрузки/таймера (bcdedit). Продолжайте только если согласны с ослаблением защиты Windows и возможной перезагрузкой. Продолжить?",
                "preset_gaming_turbo_title": "Gaming Turbo",
                "preset_gaming_turbo_safe_actions": "• Smart priority (26)\n• Оптимизация служб\n• Ultimate Performance\n• Очистка RAM",
                "preset_gaming_turbo_caution_actions": "• Не трогает VBS и Dynamic Tick\n• Универсально для любых игр",
                "preset_work_restore_title": "Work / Restore",
                "preset_work_restore_safe_actions": "• Откат Extreme твиков\n• Возврат служб к стандарту\n• Переход на Balanced план питания",
                "preset_work_restore_caution_actions": "• Не восстанавливает CS2 autoexec.cfg и process mitigations\n• Не откатывает netsh TCP после «Сеть»\n• Возвращает систему ближе к стоку\n• Рекомендуется перед работой/учебой/VM",
                "telegram_title": "Будьте в курсе",
                "telegram_desc": "Обновления и советы по ZERNIX NEXUS CS2 BOOST.",
                "telegram_join": "В Telegram >",
                "backup_prompt_title": "Создать резервную копию системы?",
                "backup_prompt_message": "Перед использованием инструментов оптимизации рекомендуется создать точку восстановления Windows. Так вы сможете откатить изменения, если что-то пойдёт не так.\n\nСоздать точку восстановления сейчас?",
                "experimental_warning_title": "Экспериментальный твик",
                "experimental_warning_text": "{action} помечен как Experimental. Он не включается в авто-пресеты, потому что может снизить производительность на уже оптимизированных системах.\n\nПрименить вручную?",
                "admin_warning": "ZERNIX запущен без прав Администратора. UI откроется, но правки реестра не применятся.",
                "faceit_risky_title": "Предупреждение совместимости FACEIT",
                "faceit_risky_text": "{action} может менять службы, boot/security-настройки, process mitigations или приоритет процесса. FACEIT AC может не пустить в игру или посчитать системные изменения неподдерживаемыми.\n\nПрименить этот твик всё равно?",
                "faceit_blocked": "{action}: заблокировано, пока FACEIT Anti-Cheat запущен. Закройте FACEIT AC или используйте откат настроек.",
                "offline_rollback_banner": "Офлайн-откат: бусты и пресеты ограничены — используйте «Сброс» и «Восстановить сеть».",
                "offline_action_blocked": "Недоступно в режиме офлайн-отката. Запустите ZERNIX обычно, когда будет сеть.",
                "network_stack_restore": "Восстановить сеть / VPN / WMI",
                "desc_network_stack_restore": "Снова включить ключевые сетевые службы и WMI, сбросить TCP autotuning, очистить DNS — если «уронили» интернет или VPN.",
                "preset_developer_vm": "Режим разработчика: не отключать Hyper-V (пропуск отключения VBS и служб vmic*)",
                "kernel_latency_need_admin": "Kernel Latency Lock нужен запуск ZERNIX от имени Администратора (доступ к токену и процессу).",
                "kernel_latency_warn_title": "Kernel Latency Lock",
            },
        }
        self.status_log_lines = [self.tr("console_ready")]

        self.assets = load_ui_assets()
        self._build_sidebar()
        self._build_main_area()
        self._apply_offline_restrictions()
        self._apply_language()
        threading.Thread(target=self._hardware_worker_loop, daemon=True).start()
        self._refresh_status_cards()
        self._animate_graphs()
        self._schedule_status_refresh()
        if not is_admin():
            self._append_log(f"⚠️ {self.tr('admin_warning')}")

        if self._demo_mode:
            self._append_log("Portfolio demo mode: license server check skipped for screenshots.")

        if not self._has_valid_license() and not self._offline_rollback and not self._demo_mode:
            self._build_license_overlay()

    def _open_telegram_channel(self):
        try:
            webbrowser.open(ZERNIX_TELEGRAM_URL, new=2)
        except Exception:
            pass

    def _build_sidebar(self):
        def _truncate_with_ellipsis(text_value: str, max_len: int = 68) -> str:
            text_value = str(text_value or "")
            if len(text_value) <= max_len:
                return text_value
            return text_value[: max_len - 3].rstrip() + "..."

        self.sidebar = ctk.CTkFrame(self, width=320, fg_color=Theme.COLORS["sidebar_bg"], corner_radius=0)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="ns")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_rowconfigure(10, weight=1)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self._sidebar_bg_job = None
        self.sidebar.bind("<Configure>", lambda _e: self._schedule_sidebar_gradient())

        self.logo_label = ctk.CTkLabel(self.sidebar, image=self.assets["logo"], text="")
        self.logo_label.grid(row=0, column=0, padx=20, pady=(24, 6))

        self.brand_label = ctk.CTkLabel(self.sidebar, text="ZERNIX NEXUS", font=Theme.FONTS["brand"], text_color="#050505")
        self.brand_label.grid(row=1, column=0, padx=15)

        self.version_label = ctk.CTkLabel(
            self.sidebar,
            text="CS2 BOOST",
            font=("Segoe UI", 17),
            text_color=Theme.COLORS["text_secondary"],
        )
        self.version_label.grid(row=2, column=0, pady=(0, 28))

        sidebar_info = [
            ("OS", self.system_info.get("os", "Windows 11"), "window"),
            ("CPU", self.system_info.get("cpu", "Unknown CPU"), "chip"),
            ("GPU", self.system_info.get("gpu", "Unknown GPU"), "gpu"),
            ("RAM", self.system_info.get("ram", "Unknown"), "ram"),
        ]
        for idx, (label, value, icon) in enumerate(sidebar_info, start=3):
            row = ctk.CTkFrame(self.sidebar, fg_color="transparent")
            row.grid(row=idx, column=0, sticky="ew", padx=26, pady=8)
            icon_label = ctk.CTkLabel(
                row,
                text=self._sidebar_icon(icon),
                font=("Segoe UI Symbol", 22),
                width=30,
                text_color="#6B7280",
            )
            icon_label.pack(side="left", padx=(0, 12), anchor="n")
            display_value = _truncate_with_ellipsis(value)
            text = ctk.CTkLabel(
                row,
                text=f"{label}: {display_value}",
                font=("Segoe UI", 14),
                anchor="w",
                justify="left",
                wraplength=220,
                text_color="#16181C",
            )
            text.pack(side="left", fill="x", expand=True, anchor="w")

        telegram_outer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        telegram_outer.grid(row=7, column=0, sticky="ew", padx=16, pady=(14, 10))

        telegram_card = ctk.CTkFrame(
            telegram_outer,
            fg_color=Theme.COLORS["card_bg"],
            corner_radius=16,
            border_width=1,
            border_color=Theme.COLORS["border_light"],
        )
        telegram_card.pack(fill="x")

        telegram_card_bottom = ctk.CTkFrame(
            telegram_card,
            fg_color="#E8F4FC",
            height=28,
            corner_radius=0,
        )
        telegram_card_bottom.pack(fill="x", side="bottom")
        telegram_card_bottom.pack_propagate(False)

        telegram_inner = ctk.CTkFrame(telegram_card, fg_color="transparent")
        telegram_inner.pack(fill="both", expand=True, padx=14, pady=(14, 8))

        icon_row = ctk.CTkFrame(telegram_inner, fg_color="transparent")
        icon_row.pack(fill="x")

        telegram_icon_img = self.assets.get("telegram")
        if telegram_icon_img is not None:
            icon_holder = ctk.CTkLabel(icon_row, image=telegram_icon_img, text="")
            icon_holder.pack(side="left", anchor="nw")
        else:
            icon_holder = ctk.CTkLabel(
                icon_row,
                text="●",
                font=("Segoe UI", 28),
                text_color=Theme.COLORS["accent"],
                width=44,
            )
            icon_holder.pack(side="left", anchor="nw")

        text_block = ctk.CTkFrame(icon_row, fg_color="transparent")
        text_block.pack(side="left", fill="both", expand=True, padx=(12, 0))

        self.telegram_title_label = ctk.CTkLabel(
            text_block,
            text=self.tr("telegram_title"),
            font=("Segoe UI", 14, "bold"),
            text_color="#16181C",
            anchor="w",
            justify="left",
        )
        self.telegram_title_label.pack(fill="x", anchor="w")

        self.telegram_desc_label = ctk.CTkLabel(
            text_block,
            text=self.tr("telegram_desc"),
            font=("Segoe UI", 10),
            text_color=Theme.COLORS["text_secondary"],
            anchor="w",
            justify="left",
            wraplength=196,
        )
        self.telegram_desc_label.pack(fill="x", anchor="w", pady=(6, 0))

        btn_row = ctk.CTkFrame(telegram_inner, fg_color="transparent")
        btn_row.pack(fill="x", pady=(12, 0))

        self.telegram_join_button = ctk.CTkButton(
            btn_row,
            text=self.tr("telegram_join"),
            command=self._open_telegram_channel,
            width=148,
            height=34,
            corner_radius=12,
            font=("Segoe UI", 12, "bold"),
            fg_color=Theme.COLORS["accent"],
            hover_color=Theme.COLORS["accent_hover"],
            text_color="#FFFFFF",
        )
        self.telegram_join_button.pack(side="right")

        footer = ctk.CTkLabel(
            self.sidebar,
            text="Developed by ZERNOKHA | 2026",
            font=("Segoe UI", 12),
            text_color=Theme.COLORS["text_muted"],
        )
        footer.grid(row=11, column=0, sticky="sw", padx=18, pady=(0, 10))
        globe = ctk.CTkLabel(self.sidebar, text="◉", font=("Segoe UI Symbol", 18), text_color=Theme.COLORS["accent"])
        globe.place(x=278, y=706)

        self.after(80, self._paint_sidebar_gradient)

    def _schedule_sidebar_gradient(self):
        if Image is None or ImageTk is None:
            return
        if getattr(self, "_sidebar_bg_job", None) is not None:
            try:
                self.after_cancel(self._sidebar_bg_job)
            except Exception:
                pass
        self._sidebar_bg_job = self.after(90, self._paint_sidebar_gradient)

    def _paint_sidebar_gradient(self):
        self._sidebar_bg_job = None
        if Image is None or ImageTk is None:
            return
        try:
            self.sidebar.update_idletasks()
            w = max(self.sidebar.winfo_width(), 320)
            h = max(self.sidebar.winfo_height(), 2)
            strip = Image.new("RGB", (1, h))
            px = strip.load()
            top_rgb = (232, 239, 246)
            bot_rgb = (243, 246, 250)
            for y in range(h):
                t = y / max(h - 1, 1)
                px[0, y] = tuple(int(top_rgb[i] * (1 - t) + bot_rgb[i] * t) for i in range(3))
            img = strip.resize((w, h), Image.Resampling.BILINEAR)
            self._sidebar_gradient_photo_ref = ImageTk.PhotoImage(img)
            if not hasattr(self, "_sidebar_gradient_label"):
                self._sidebar_gradient_label = tk.Label(self.sidebar, bd=0, highlightthickness=0, borderwidth=0)
                self._sidebar_gradient_label.place(x=0, y=0, relwidth=1, relheight=1)
                self._sidebar_gradient_label.lower()
            self._sidebar_gradient_label.configure(image=self._sidebar_gradient_photo_ref)
        except Exception:
            self.sidebar.configure(fg_color=Theme.COLORS["sidebar_bg"])

    def _sidebar_icon(self, icon_name: str) -> str:
        icons = {
            "window": "⊞",
            "chip": "▣",
            "gpu": "▤",
            "ram": "▥",
        }
        return icons.get(icon_name, "•")

    def tr(self, key: str) -> str:
        return self.translations[self.current_language].get(key, key)

    def change_language(self):
        self.current_language = "en" if self.current_language == "ru" else "ru"
        self._apply_language()

    def _apply_language(self):
        for page_key, translation_key in (("dashboard", "tab_home"), ("advanced", "tab_advanced"), ("license", "tab_license")):
            if page_key in self.nav_buttons:
                self.nav_buttons[page_key].configure(text=self.tr(translation_key))
        self.lang_button.configure(text=self.tr("language_button"))
        self.log_header.configure(text=self.tr("console_header"))
        self.telegram_title_label.configure(text=self.tr("telegram_title"))
        self.telegram_desc_label.configure(text=self.tr("telegram_desc"))
        self.telegram_join_button.configure(text=self.tr("telegram_join"))
        self.dashboard_page.apply_language(self.tr)
        self.advanced_page.apply_language(self.tr)
        self.license_page.apply_language(self.tr, self._has_valid_license())
        self.log_box.configure(state="normal")
        ready_messages = {translations.get("console_ready") for translations in self.translations.values()}
        if len(self.status_log_lines) == 1 and self.status_log_lines[0] in ready_messages:
            self.status_log_lines = [self.tr("console_ready")]
        self.log_box.delete("1.0", "end")
        self.log_box.insert("1.0", "\n".join(self.status_log_lines))
        self.log_box.configure(state="disabled")
        self._refresh_status_cards()

    def _build_main_area(self):
        self.main_panel = ctk.CTkFrame(self, fg_color=Theme.COLORS["app_bg"], corner_radius=0)
        self.main_panel.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.main_panel.grid_columnconfigure(0, weight=1)
        self.main_panel.grid_rowconfigure(1, weight=1)

        self.top_bar = ctk.CTkFrame(self.main_panel, fg_color=Theme.COLORS["app_bg"], corner_radius=0)
        self.top_bar.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 8))
        self.top_bar.grid_columnconfigure(0, weight=1)
        self._build_top_bar()

        self.console_shell = ctk.CTkFrame(
            self,
            fg_color=Theme.COLORS["card_bg"],
            corner_radius=12,
            border_width=1,
            border_color=Theme.COLORS["border_dark"],
            height=188,
        )
        self.console_shell.grid(row=1, column=1, sticky="ew", padx=10, pady=(0, 12))
        self.console_shell.grid_propagate(False)
        self.log_header = ctk.CTkLabel(
            self.console_shell,
            text=self.tr("console_header"),
            font=("Segoe UI", 12, "bold"),
            text_color=Theme.COLORS["text_primary"],
            anchor="w",
        )
        self.log_header.pack(fill="x", padx=12, pady=(10, 6))
        self.log_box = ctk.CTkTextbox(
            self.console_shell,
            height=118,
            fg_color=Theme.COLORS["card_bg"],
            text_color=Theme.COLORS["text_primary"],
            border_width=0,
            font=Theme.FONTS["mono_small"],
            activate_scrollbars=True,
        )
        self.log_box.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.log_box.insert("1.0", self.tr("console_ready"))
        self._bind_console_copy_shortcuts()
        self.log_box.configure(state="disabled")

        self._build_pages()
        self.pages = {
            "dashboard": self.dashboard_page,
            "advanced": self.advanced_page,
            "license": self.license_page,
        }
        self.show_page("dashboard")

    def _build_top_bar(self):
        nav_bar = ctk.CTkFrame(self.top_bar, fg_color="transparent")
        nav_bar.grid(row=0, column=0, sticky="w")
        for column, page_key in enumerate(("dashboard", "advanced", "license")):
            tab_key = "tab_home" if page_key == "dashboard" else f"tab_{page_key}"
            button = ctk.CTkButton(
                nav_bar,
                text=self.tr(tab_key),
                width=122,
                height=34,
                fg_color=Theme.COLORS["tab_inactive_bg"],
                hover_color="#F8FAFC",
                text_color=Theme.COLORS["text_primary"],
                border_width=1,
                border_color=Theme.COLORS["nav_border"],
                corner_radius=12,
                command=lambda key=page_key: self.show_page(key),
            )
            button.grid(row=0, column=column, padx=(0, 7))
            self.nav_buttons[page_key] = button

        self.lang_button = ctk.CTkButton(
            self.top_bar,
            text="RU/EN",
            width=84,
            height=34,
            fg_color=Theme.COLORS["tab_inactive_bg"],
            hover_color="#F8FAFC",
            text_color=Theme.COLORS["text_primary"],
            border_width=1,
            border_color=Theme.COLORS["nav_border"],
            corner_radius=12,
            command=self.change_language,
        )
        self.lang_button.grid(row=0, column=1, sticky="e")

    def _is_faceit_ac_running(self) -> bool:
        try:
            for proc in psutil.process_iter(["name"]):
                name = str((proc.info or {}).get("name") or "").lower()
                if "faceit" in name:
                    return True
        except Exception:
            pass
        try:
            for service in psutil.win_service_iter():
                service_name = str(getattr(service, "name", lambda: "")() or "").lower()
                display_name = str(getattr(service, "display_name", lambda: "")() or "").lower()
                if "faceit" not in f"{service_name} {display_name}":
                    continue
                try:
                    if str(service.status()).lower() == "running":
                        return True
                except Exception:
                    return True
        except Exception:
            pass
        return False

    def _confirm_faceit_sensitive_action(self, label: str, title_key: Optional[str] = None) -> bool:
        if label not in FACEIT_RISKY_ACTIONS:
            return True
        action_name = self.tr(title_key or label)
        if self._is_faceit_ac_running():
            self._append_log(self.tr("faceit_blocked").format(action=action_name))
            return False
        return messagebox.askyesno(
            self.tr("faceit_risky_title"),
            self.tr("faceit_risky_text").format(action=action_name),
        )

    def _select_nav_button(self, active_page_key: str):
        for page_key, button in self.nav_buttons.items():
            selected = page_key == active_page_key
            button.configure(
                fg_color=Theme.COLORS["tab_active_bg"] if selected else Theme.COLORS["tab_inactive_bg"],
                hover_color=Theme.COLORS["tab_active_bg"] if selected else "#F8FAFC",
                text_color=Theme.COLORS["tab_active_text"] if selected else Theme.COLORS["text_primary"],
                border_color=Theme.COLORS["accent_soft"] if selected else Theme.COLORS["nav_border"],
            )

    def show_page(self, page_key: str):
        next_page = self.pages.get(page_key)
        if next_page is None:
            return
        if self.current_page_key:
            current_page = self.pages.get(self.current_page_key)
            if current_page is not None and current_page.winfo_manager() == "grid":
                current_page.grid_forget()
        next_page.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 6))
        next_page.tkraise()
        self.current_page_key = page_key
        self._select_nav_button(page_key)

    def _build_pages(self):
        def _manual_experimental(action_key: str, title_key: str, fn):
            return lambda: self._run_experimental_action(action_key, title_key, fn)

        system_rows = [
            ("create_restore_point", "desc_create_restore_point", "backup_action", lambda: self._start_async_action("create_restore_point", create_backup)),
            ("restore_system", "desc_restore_system", "restore_action", lambda: self._start_async_action("restore_system", restore_backup)),
            ("reset_to_default", "desc_reset_to_default", "reset_action", lambda: self._start_async_action("reset_to_default", restore_system_defaults)),
            ("global_boost", "desc_global_boost", "run_action", lambda: self._start_async_action("global_boost", optimize_system_all)),
            ("input_lag", "desc_input_lag", "run_action", _manual_experimental("input_lag", "input_lag", apply_input_latency_tweaks)),
            ("usb_latency", "desc_usb_latency", "run_action", lambda: self._start_async_action("usb_latency", apply_usb_latency_tweaks)),
            ("visual_tweaks", "desc_visual_tweaks", "run_action", lambda: self._start_async_action("visual_tweaks", apply_visual_tweaks)),
            ("system_stability", "desc_system_stability", "run_action", lambda: self._start_async_action("system_stability", apply_system_stability_tweaks)),
            ("privacy", "desc_privacy", "run_action", lambda: self._start_async_action("privacy", disable_telemetry_all)),
            ("network_fix", "desc_network_fix", "run_action", lambda: self._start_async_action("network_fix", optimize_network)),
            ("network_stack_restore", "desc_network_stack_restore", "run_action", lambda: self._start_async_action("network_stack_restore", restore_network_connectivity)),
            ("clean_junk", "desc_clean_junk", "run_action", lambda: self._start_async_action("clean_junk", run_deep_clean)),
            ("clean_ram", "desc_clean_ram", "run_action", lambda: self._start_async_action("clean_ram", clean_ram)),
            ("disable_search_indexer", "desc_search", "run_btn", lambda: self._start_async_action("disable_search_indexer", disable_search_indexer)),
            ("clear_event_logs", "desc_logs", "run_btn", lambda: self._start_async_action("clear_event_logs", clear_event_logs)),
            ("optimize_ntfs", "desc_ntfs", "run_btn", lambda: self._start_async_action("optimize_ntfs", optimize_ntfs)),
            ("disable_printer_spooler", "desc_spooler", "run_btn", lambda: self._start_async_action("disable_printer_spooler", disable_printer_spooler)),
            ("optimize_services", "desc_optimize_services", "run_action", _manual_experimental("optimize_services", "optimize_services", optimize_services)),
            ("max_performance", "desc_max_performance", "run_action", _manual_experimental("max_performance", "max_performance", run_max_performance_profile)),
            ("optimize_pagefile", "desc_optimize_pagefile", "run_action", lambda: self._start_async_action("optimize_pagefile", optimize_pagefile)),
            ("apply_cpu_turbo", "desc_apply_cpu_turbo", "run_action", _manual_experimental("apply_cpu_turbo", "apply_cpu_turbo", apply_cpu_turbo)),
            ("extreme_rollback", "desc_extreme_rollback", "run_action", lambda: self._start_async_action("extreme_rollback", run_extreme_rollback)),
        ]
        gaming_rows = [
            ("gaming_install_cs2", "desc_gaming_install_cs2", "gaming_install", lambda: self._start_async_action("gaming_install_cs2", lambda: install_cs2_config_with_clipboard(self._clipboard_callback))),
            ("gaming_smart_launch", "desc_gaming_smart_launch", "gaming_install", lambda: self._start_async_action("gaming_smart_launch", lambda: copy_cs2_smart_launch(self._clipboard_callback))),
            ("gaming_pro_telemetry", "desc_gaming_pro_telemetry", "gaming_enable", lambda: self._start_async_action("gaming_pro_telemetry", apply_pro_telemetry)),
            ("gaming_network_registry", "desc_gaming_network_registry", "gaming_run", lambda: self._start_async_action("gaming_network_registry", apply_zernix_network_registry)),
            ("gaming_audio_pro", "desc_gaming_audio_pro", "gaming_enable", lambda: self._start_async_action("gaming_audio_pro", apply_zernix_audio_pro)),
            ("gaming_kernel_latency_on", "desc_gaming_kernel_latency_on", "gaming_enable", lambda: self._start_kernel_latency_boost_action()),
            ("gaming_kernel_latency_off", "desc_gaming_kernel_latency_off", "gaming_disable", lambda: self._start_async_action("gaming_kernel_latency_off", release_kernel_latency_boost)),
            ("gaming_disable_cfg", "desc_gaming_disable_cfg", "gaming_disable", lambda: self._start_async_action("gaming_disable_cfg", disable_cfg_for_cs2)),
            ("gaming_frametime", "desc_gaming_frametime", "gaming_enable", lambda: self._start_async_action("gaming_frametime", lambda: set_cs2_frametime_telemetry(True))),
            ("gaming_network_diagnostic", "desc_gaming_network_diagnostic", "gaming_run", lambda: self._start_async_action("gaming_network_diagnostic", self._run_network_diagnostic)),
            ("gaming_dx_cache", "desc_gaming_dx_cache", "gaming_clear", lambda: self._start_async_action("gaming_dx_cache", clear_directx_shader_cache_2026)),
            ("gaming_steam_cache", "desc_gaming_steam_cache", "gaming_clear", lambda: self._start_async_action("gaming_steam_cache", clear_steam_shader_precache)),
            ("gaming_turbo_mode", "desc_gaming_turbo_mode", "gaming_run", lambda: self._start_async_action("gaming_turbo_mode", run_gaming_turbo_mode)),
        ]
        self.dashboard_page = DashboardFrame(
            self.main_panel,
            self.tr,
            self._start_optimization,
            self._start_session_rollback,
        )
        self.advanced_page = AdvancedFrame(self.main_panel, self.tr, system_rows, gaming_rows, self._apply_preset)
        self.license_page = LicenseFrame(
            self.main_panel,
            self.tr,
            SERVER_LICENSE_PATH,
            get_server_hwid(),
            self._has_valid_license(),
            self._activate_license_from_tab,
            self._deactivate_license_from_tab,
            self._copy_hwid_to_clipboard,
        )

    def _start_kernel_latency_boost_action(self):
        if not is_admin():
            messagebox.showwarning(self.tr("kernel_latency_warn_title"), self.tr("kernel_latency_need_admin"))
            return
        self._start_async_action("gaming_kernel_latency_on", lambda: apply_kernel_latency_boost("cs2.exe"))

    def _apply_offline_restrictions(self):
        if not getattr(self, "_offline_rollback", False):
            return
        self._append_log(self.tr("offline_rollback_banner"))
        try:
            self.dashboard_page.boost_button.configure(state="disabled")
        except Exception:
            pass

    def _start_async_action(self, label: str, func):
        if self._offline_rollback and label not in _OFFLINE_ROLLBACK_ALLOWED_ACTIONS:
            self._append_log(self.tr("offline_action_blocked"))
            return
        if not self._confirm_faceit_sensitive_action(label):
            return
        with self._action_lock:
            if self._active_actions >= self._max_parallel_actions:
                self._append_log(f"{label}: queue busy, try again in a moment.")
                return
            self._active_actions += 1
        worker = threading.Thread(target=self._run_task_guarded, args=(label, func), daemon=True)
        worker.start()

    def _run_experimental_action(self, label: str, action_title_key: str, func):
        warning_text = self.tr("experimental_warning_text").format(action=self.tr(action_title_key))
        if not messagebox.askyesno(self.tr("experimental_warning_title"), warning_text):
            self._append_log(f"{label}: skipped by user.")
            return
        self._start_async_action(label, lambda f=func: run_experimental_tweak_safely(f, self.tr(action_title_key)))

    def _apply_preset(self, preset_key: str):
        if self._offline_rollback and preset_key != "work_restore":
            self._append_log(self.tr("offline_action_blocked"))
            return
        preset_title_keys = {
            "cybersport": "preset_cybersport_title",
            "gaming_turbo": "preset_gaming_turbo_title",
            "work_restore": "preset_work_restore_title",
        }
        if not self._confirm_faceit_sensitive_action(preset_key, preset_title_keys.get(preset_key)):
            return
        if preset_key == "cybersport":
            if not messagebox.askyesno(
                self.tr("preset_cybersport_confirm_title"),
                self.tr("preset_cybersport_confirm_text"),
            ):
                self._append_log("CyberSport preset: skipped after confirmation.")
                return
        with self._action_lock:
            if self._active_actions >= self._max_parallel_actions:
                self._append_log("Preset queue busy, try again in a moment.")
                return
            self._active_actions += 1
        worker = threading.Thread(target=self._run_preset_flow_guarded, args=(preset_key,), daemon=True)
        worker.start()

    def _run_preset_flow_guarded(self, preset_key: str):
        try:
            self._run_preset_flow(preset_key)
        finally:
            with self._action_lock:
                self._active_actions = max(0, self._active_actions - 1)

    def _run_preset_flow(self, preset_key: str):
        preset_jobs = {
            # Presets never create a restore point automatically — use System → Create Restore Point if needed.
            "cybersport": [("CyberSport (CS2 Focus)", run_cybersport_preset)],
            "gaming_turbo": [("Gaming Turbo", run_gaming_turbo_preset)],
            "work_restore": [("Work / Restore", run_work_restore_preset)],
        }
        jobs = preset_jobs.get(preset_key)
        if not jobs:
            self.after(0, lambda: self._append_log(f"Unknown preset: {preset_key}"))
            return
        self.after(0, lambda: self._append_log(f"Preset '{preset_key}' started..."))
        for label, func in jobs:
            self._run_task(label, func)
        self.after(0, lambda: self._append_log(f"Preset '{preset_key}' completed."))
        self.after(0, self._refresh_status_cards)

    def _activate_license_from_tab(self):
        key = self.license_page.entry.get().strip()
        ok, msg = check_license(key)
        if ok:
            try:
                save_license_key(key)
            except OSError as exc:
                messagebox.showerror("License", f"License is valid but could not be saved: {exc}")
                return
            self._append_log("License activated successfully.")
            self.license_page.update_status(True)
            self._apply_language()
            messagebox.showinfo("License", f"License activated. Expiry: {msg}")
            self._schedule_first_activation_backup_prompt()
        else:
            messagebox.showerror("License", msg)

    def _deactivate_license_from_tab(self):
        confirmed = messagebox.askyesno(
            "License",
            "Удалить текущий ключ и вернуться к экрану активации?",
        )
        if not confirmed:
            return
        self._clear_registry_license_key()
        try:
            if os.path.exists(SERVER_LICENSE_PATH):
                os.remove(SERVER_LICENSE_PATH)
        except OSError as exc:
            self._append_log(f"License remove warning: {exc}")
        self._append_log("License key removed. Re-activation required.")
        self._clear_backup_reminder_flag()
        self.license_page.entry.delete(0, "end")
        self.license_page.update_status(False)
        self.show_page("license")
        self._build_license_overlay()

    def _copy_hwid_to_clipboard(self):
        hwid = get_server_hwid()
        self._clipboard_callback(hwid)
        self._append_log(self.tr("license_hwid_copied"))
        messagebox.showinfo("HWID", self.tr("license_hwid_copied"))

    def _refresh_status_cards(self):
        if self._status_refresh_in_flight:
            return
        self._status_refresh_in_flight = True
        threading.Thread(target=self._refresh_status_cards_worker, daemon=True).start()

    def _schedule_status_refresh(self):
        self._refresh_status_cards()
        # Faster loop so quick-status cards feel live.
        self.after(2500, self._schedule_status_refresh)

    def _ping_host_summary(self, label: str, host: str) -> str:
        try:
            result = subprocess.run(
                f"ping -n 4 -w 1200 {host}",
                shell=True,
                capture_output=True,
                text=True,
                check=False,
                timeout=8,
                creationflags=HIDDEN_PROCESS_FLAGS,
            )
            text = f"{result.stdout}\n{result.stderr}"
            loss_match = re.search(r"(\d+)%\s*(?:loss|потер)", text, flags=re.IGNORECASE)
            avg_match = re.search(r"(?:Average|Среднее)\s*=\s*(\d+)\s*ms", text, flags=re.IGNORECASE)
            if not avg_match:
                times = [int(value) for value in re.findall(r"(?:time|время)[=<]\s*(\d+)\s*ms", text, flags=re.IGNORECASE)]
                avg = round(sum(times) / len(times)) if times else None
            else:
                avg = int(avg_match.group(1))
            loss = int(loss_match.group(1)) if loss_match else 0
            if avg is None:
                return f"{label}: no reply"
            quality = "OK" if avg < 60 and loss == 0 else "WARN" if avg < 100 and loss <= 25 else "BAD"
            return f"{label}: {avg}ms, loss {loss}% [{quality}]"
        except Exception as exc:
            return f"{label}: failed ({exc})"

    def _run_network_diagnostic(self):
        endpoints = [
            ("Cloudflare DNS", "1.1.1.1"),
            ("Google DNS", "8.8.8.8"),
            ("Valve EU", "155.133.252.34"),
            ("Valve EU 2", "162.254.197.36"),
        ]
        results = ["[ZERNIX] Network Diagnostic:"]
        results.extend(self._ping_host_summary(label, host) for label, host in endpoints)
        try:
            route = subprocess.run(
                "tracert -d -h 8 -w 900 155.133.252.34",
                shell=True,
                capture_output=True,
                text=True,
                check=False,
                timeout=12,
                creationflags=HIDDEN_PROCESS_FLAGS,
            )
            hop_lines = [
                line.strip()
                for line in (route.stdout or "").splitlines()
                if re.match(r"^\s*\d+\s+", line)
            ][:8]
            if hop_lines:
                results.append("Route sample: " + " / ".join(hop_lines[-3:]))
        except Exception as exc:
            results.append(f"Route sample failed: {exc}")
        return " | ".join(results)

    def _animate_graphs(self):
        snapshot = self._get_cached_hardware_snapshot()
        self.dashboard_page.update_hardware_snapshot(snapshot)
        self.after(900, self._animate_graphs)

    def _append_log(self, message: str):
        text_message = str(message)
        self.status_log_lines.append(text_message)
        self.status_log_lines = self.status_log_lines[-self._max_console_lines:]
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"{text_message}\n")
        while True:
            line_count = int(float(self.log_box.index("end-1c").split(".")[0]))
            if line_count <= self._max_console_lines:
                break
            self.log_box.delete("1.0", "2.0")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _bind_console_copy_shortcuts(self):
        def _copy_selection(_event=None):
            try:
                selected_text = self.log_box.get("sel.first", "sel.last")
            except Exception:
                return "break"
            if selected_text:
                self.clipboard_clear()
                self.clipboard_append(selected_text)
                self.update_idletasks()
            return "break"

        for sequence in ("<Control-c>", "<Control-C>", "<Control-Insert>"):
            self.log_box.bind(sequence, _copy_selection)

    def _run_task_guarded(self, label: str, func):
        try:
            self._run_task(label, func)
        finally:
            with self._action_lock:
                self._active_actions = max(0, self._active_actions - 1)

    def _run_task(self, label: str, func, *args):
        self.after(0, lambda: self._append_log(f"{label}..."))
        try:
            result = func(*args)
        except Exception as exc:
            result = f"{label} failed: {exc}"

        def finish():
            self._append_log(str(result))
            if label == "gaming_kernel_latency_on":
                text = str(result).lower()
                if "failed" in text or "administrator" in text or "not found" in text:
                    messagebox.showwarning(self.tr("kernel_latency_warn_title"), str(result))

        self.after(0, finish)
        # Re-check quick statuses right after each action completes.
        self.after(0, self._refresh_status_cards)

    def _start_session_rollback(self):
        self._start_async_action("rollback_after_gaming", run_work_restore_preset)

    def _start_optimization(self):
        if self._offline_rollback:
            self._append_log(self.tr("offline_action_blocked"))
            return
        if not self._confirm_faceit_sensitive_action("cs2_session_boost", "btn_session_boost"):
            return
        with self._action_lock:
            if self._active_actions >= self._max_parallel_actions:
                self._append_log("cs2_session_boost: queue busy, try again in a moment.")
                return
            self._active_actions += 1
        worker = threading.Thread(target=self._run_optimization_flow_guarded, daemon=True)
        worker.start()

    def _run_optimization_flow_guarded(self):
        try:
            self._run_optimization_flow()
        finally:
            with self._action_lock:
                self._active_actions = max(0, self._active_actions - 1)

    def _run_optimization_flow(self):
        jobs = [
            ("Creating backup", create_full_backup),
            ("Applying adaptive CS2 system profile", apply_cs2_adaptive_system_profile),
            ("Applying base optimization", optimize_system_all),
            ("Applying Smart Priority Control", apply_smart_priority_control),
            ("Applying stability tweaks", apply_system_stability_tweaks),
            ("Optimizing network", optimize_network),
            ("Applying Network Registry Pro", apply_zernix_network_registry),
            ("Applying CS2 network presets", lambda: apply_cs2_network_presets("auto")),
            ("Applying CS2 competitive 2026 cfg", apply_cs2_competitive_2026_cfg),
            ("Applying Audio Pro", apply_zernix_audio_pro),
            ("Thread pool recommendation", get_thread_pool_recommendation),
            ("Applying USB tweaks", apply_usb_latency_tweaks),
            ("Applying visual tweaks", apply_visual_tweaks),
            ("Applying input latency tweaks", apply_input_latency_tweaks),
            ("Applying extra performance tweaks", apply_extra_performance_tweaks),
            ("Enabling Game Mode", enable_game_mode),
            ("Optimizing services", optimize_services),
            ("Applying CPU turbo", apply_cpu_turbo),
            ("Applying Kernel Latency Profile", lambda: apply_kernel_latency_boost_if_running("cs2.exe")),
        ]
        for label, func in jobs:
            self._run_task(label, func)
        self.after(0, self._refresh_status_cards)

    def _build_license_overlay(self):
        if self.license_overlay is not None and self.license_overlay.winfo_exists():
            self.license_overlay.lift()
            return
        overlay = ctk.CTkFrame(self, fg_color="#0E1117")
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.license_overlay = overlay

        box = ctk.CTkFrame(overlay, width=480, height=300, fg_color="#161B22", corner_radius=18)
        box.place(relx=0.5, rely=0.5, anchor="center")
        box.pack_propagate(False)

        ctk.CTkLabel(box, text="ACTIVATE LICENSE", font=("Segoe UI", 28, "bold"), text_color="white").pack(
            pady=(28, 10)
        )
        hwid_label = ctk.CTkLabel(
            box,
            text=f"HWID: {get_server_hwid()}",
            font=("Consolas", 14),
            text_color="#9AA4B2",
            cursor="hand2",
        )
        hwid_label.pack(pady=(0, 18))
        hwid_label.bind("<Button-1>", lambda _event: self._copy_hwid_to_clipboard())
        hwid_label.bind("<Enter>", lambda _event: hwid_label.configure(text_color="#64C7D8"))
        hwid_label.bind("<Leave>", lambda _event: hwid_label.configure(text_color="#9AA4B2"))

        try:
            logo_key_path = resource_path(os.path.join("assets", "logo_key.png"))
            if os.path.isfile(logo_key_path):
                self._license_logo_image = tk.PhotoImage(file=logo_key_path)
                max_dim = max(self._license_logo_image.width(), self._license_logo_image.height())
                if max_dim > 430:
                    scale = max(1, int(max_dim / 430))
                    self._license_logo_image = self._license_logo_image.subsample(scale)
                self._license_logo_label = ctk.CTkLabel(overlay, text="", image=self._license_logo_image)
                self._license_logo_label.place(relx=0.992, rely=0.05, anchor="ne")
                self._license_logo_label.lower(box)
        except Exception:
            pass
        entry = ctk.CTkEntry(box, width=360, height=42, corner_radius=10, placeholder_text="Enter license key")
        entry.pack(pady=(0, 12))
        def paste_license_key(_event=None):
            try:
                pasted = self.clipboard_get()
            except Exception:
                return "break"
            entry.delete(0, "end")
            entry.insert(0, str(pasted).strip())
            return "break"
        entry.bind("<Control-KeyPress-v>", paste_license_key)
        entry.bind("<Control-KeyPress-V>", paste_license_key)
        entry.bind("<Shift-Insert>", paste_license_key)
        entry.bind("<Button-3>", paste_license_key)
        bind_license_entry_hotkeys(entry)

        def activate():
            key = entry.get().strip()
            ok, msg = check_license(key)
            if ok:
                try:
                    save_license_key(key)
                except OSError as exc:
                    messagebox.showerror("Activation failed", f"License is valid but could not be saved: {exc}")
                    return
                self._append_log("License activated successfully.")
                overlay.destroy()
                self.license_overlay = None
                self.license_page.update_status(True)
                self._apply_language()
                self._schedule_first_activation_backup_prompt()
            else:
                messagebox.showerror("Activation failed", msg)

        ctk.CTkButton(
            box,
            text="ACTIVATE",
            width=160,
            height=42,
            fg_color=Theme.COLORS["accent"],
            hover_color=Theme.COLORS["accent_hover"],
            text_color="#FFFFFF",
            command=activate,
        ).pack(pady=8)


if __name__ == "__main__":
    if "--demo" in sys.argv or "--portfolio" in sys.argv or "--skip-license" in sys.argv:
        os.environ["ZERNIX_PORTFOLIO_MODE"] = "1"
    if "--safe-rollback" in sys.argv:
        os.environ["ZERNIX_OFFLINE_ROLLBACK"] = "1"
    if not is_admin():
        startup_language = detect_windows_ui_language()
        messagebox.showwarning(
            "Admin recommended",
            (
                "ZERNIX запущен без прав Администратора. UI откроется, но правки реестра не применятся."
                if startup_language == "ru"
                else "ZERNIX is running without Administrator rights. The UI will open, but registry changes will not be applied."
            ),
        )
    if not verify_exe_integrity():
        messagebox.showerror("Security", "Executable integrity check failed. Startup blocked.")
        raise SystemExit(1)
    if is_debugger_present() or has_suspicious_debug_tools():
        messagebox.showerror("Security", "Debugger environment detected. Startup blocked.")
        raise SystemExit(1)

    _license_result = ensure_license_or_exit()
    _offline = _license_result == OFFLINE_ROLLBACK_RESULT
    _demo = _license_result == DEMO_MODE_RESULT
    app = NovaBoostApp(offline_rollback=_offline, demo_mode=_demo)
    
    # 1. Получаем абсолютный путь к папке проекта
    base_path = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(base_path, "assets", "logotip.ico")

    try:
        # 2. Пытаемся установить иконку стандартным методом
        app.iconbitmap(icon_path)
    except Exception as e:
        try:
            # 3. Резервный метод, если первый не сработал
            from PIL import Image, ImageTk
            img = ImageTk.PhotoImage(Image.open(os.path.join(base_path, "assets", "logo_z.png")))
            app.wm_iconphoto(True, img)
        except Exception as e2:
            print(f"Ошибка загрузки иконок: {e} | {e2}")

    app.mainloop()
