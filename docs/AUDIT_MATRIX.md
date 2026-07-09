# Audit Matrix

This document maps visible UI actions to backend functions and rollback coverage.

Reference files:

- `main.py`
- `core/tweaks.py`
- `core/logic.py`
- `ui/screens/*.py`

Legend: **Admin** means Administrator rights are recommended or required. **Reboot** means changes may need a Windows restart to fully apply.

## Dashboard

| Action | Backend | Admin | CS2 required | Reboot | Rollback notes |
| --- | --- | --- | --- | --- | --- |
| Session Boost | `_run_optimization_flow` | Yes | Optional | Sometimes | Partial rollback through Work / Restore and Reset to Default |
| Session Rollback | `run_work_restore_preset` | Yes | No | Sometimes | Releases kernel latency profile and runs system default restore |

Session Boost applies layered changes in this order: full backup, adaptive CS2 profile, system boost, network optimization, registry networking profile, CS2 network presets, cache cleanup, and optional kernel latency profile.

## Advanced: System

| Row key | Function | Admin | Reboot | Rollback |
| --- | --- | --- | --- | --- |
| `create_restore_point` | `create_backup` | Yes | No | User-controlled restore point |
| `restore_system` | `restore_backup` | No | User-controlled | Opens Windows System Restore |
| `reset_to_default` | `restore_system_defaults` | Yes | Often | Main rollback path |
| `global_boost` | `optimize_system_all` | Yes | No | Work / Restore or Reset to Default |
| `input_lag` | `apply_input_latency_tweaks` | Yes | No | Registry defaults |
| `usb_latency` | `apply_usb_latency_tweaks` | Yes | No | Registry defaults |
| `visual_tweaks` | `apply_visual_tweaks` | No | No | Registry defaults |
| `system_stability` | `apply_system_stability_tweaks` | Yes | Often | Registry defaults |
| `privacy` | `disable_telemetry_all` | Yes | No | Partial through restore defaults |
| `network_fix` | `optimize_network` | Yes | No | Not fully reverted automatically |
| `clean_junk` | `run_deep_clean` | Varies | No | Not applicable |
| `clean_ram` | `clean_ram` | No | No | Not applicable |
| `disable_search_indexer` | `disable_search_indexer` | Yes | No | Work / Restore |
| `clear_event_logs` | `clear_event_logs` | Yes | No | Not applicable |
| `optimize_ntfs` | `optimize_ntfs` | Yes | Sometimes | Partial through registry restore |
| `disable_printer_spooler` | `disable_printer_spooler` | Yes | No | Work / Restore |
| `optimize_services` | `optimize_services` | Yes | No | Work / Restore |
| `max_performance` | `run_max_performance_profile` | Yes | Sometimes | Work / Restore |
| `optimize_pagefile` | `optimize_pagefile` | Yes | Often | Work / Restore |
| `apply_cpu_turbo` | `apply_cpu_turbo` | Yes | No | Work / Restore |
| `extreme_rollback` | `run_extreme_rollback` | Yes | Sometimes | Dedicated rollback for extreme settings |

## Advanced: CS2 & Gaming

| Row key | Function | Admin | CS2 required | Rollback |
| --- | --- | --- | --- | --- |
| `gaming_install_cs2` | `install_cs2_config_with_clipboard` | No | Config folder | Manual config restore |
| `gaming_smart_launch` | `copy_cs2_smart_launch` | No | No | Not applicable |
| `gaming_pro_telemetry` | `apply_pro_telemetry` | No | Config folder | Manual config restore |
| `gaming_network_registry` | `apply_zernix_network_registry` | Yes | No | Partial registry restore |
| `gaming_audio_pro` | `apply_zernix_audio_pro` | No | Config folder | Manual config restore |
| `gaming_kernel_latency_on` | `apply_kernel_latency_boost` | Recommended | `cs2.exe` | `gaming_kernel_latency_off` |
| `gaming_kernel_latency_off` | `release_kernel_latency_boost` | No | No | Releases active locks |
| `gaming_disable_cfg` | `disable_cfg_for_cs2` | Yes | No | External mitigation policy |
| `gaming_frametime` | `set_cs2_frametime_telemetry(True)` | No | Config folder | Manual config restore |
| `gaming_network_diagnostic` | `_run_network_diagnostic` | No | No | Not applicable |
| `gaming_dx_cache` | `clear_directx_shader_cache_2026` | No | No | Cache regenerates automatically |
| `gaming_steam_cache` | `clear_steam_shader_precache` | No | Steam libraries | Cache regenerates automatically |
| `gaming_turbo_mode` | `run_gaming_turbo_mode` | Yes | No | Work / Restore |

## Presets

| Preset | Function | Admin | Rollback coverage |
| --- | --- | --- | --- |
| CyberSport | `run_cybersport_preset` | Yes | Partial: VBS, Dynamic Tick and priority changes need Work / Restore or Extreme Rollback |
| Gaming Turbo | `run_gaming_turbo_preset` | Yes | Work / Restore |
| Work / Restore | `run_work_restore_preset` | Yes | Main restore path |

## Known Gaps

- CS2 `autoexec.cfg` edits are not fully restored automatically.
- `Set-ProcessMitigation` changes for `cs2.exe` need manual verification.
- `netsh` TCP changes are global and are not completely covered by registry rollback.
- NVIDIA and fullscreen optimization changes should be checked manually after Work / Restore.
