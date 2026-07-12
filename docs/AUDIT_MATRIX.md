# Матрица системных действий

Документ связывает команды интерфейса с функциями приложения и показывает, какие изменения требуют прав администратора, перезагрузки или отдельного отката.

Основные файлы: `main.py`, `app/actions.py`, `core/logic.py`, `core/tweaks.py` и `ui/screens/`.

## Главный экран

| Действие | Реализация | Администратор | CS2 | Перезагрузка | Откат |
| --- | --- | --- | --- | --- | --- |
| CS2 Session Boost | `_run_optimization_flow` | Да | Необязательно | Иногда | Work / Restore и Reset to Default |
| Session Rollback | `run_work_restore_preset` | Да | Нет | Иногда | Освобождает latency-профиль и возвращает системные настройки |

Session Boost последовательно создает точку восстановления, применяет адаптивный профиль CS2, системные и сетевые настройки, очищает кэши и при запущенной игре включает latency-профиль.

## Система

| Ключ действия | Функция | Администратор | Перезагрузка | Откат |
| --- | --- | --- | --- | --- |
| `create_restore_point` | `create_backup` | Да | Нет | Создает точку восстановления |
| `restore_system` | `restore_backup` | Нет | По сценарию | Открывает Windows System Restore |
| `reset_to_default` | `restore_system_defaults` | Да | Часто | Основной путь возврата настроек |
| `global_boost` | `optimize_system_all` | Да | Нет | Work / Restore или Reset to Default |
| `input_lag` | `apply_input_latency_tweaks` | Да | Нет | Возврат значений реестра |
| `usb_latency` | `apply_usb_latency_tweaks` | Да | Нет | Возврат значений реестра |
| `visual_tweaks` | `apply_visual_tweaks` | Нет | Нет | Возврат значений реестра |
| `system_stability` | `apply_system_stability_tweaks` | Да | Часто | Возврат значений реестра |
| `privacy` | `disable_telemetry_all` | Да | Нет | Частично через Restore Defaults |
| `network_fix` | `optimize_network` | Да | Нет | Автоматический откат неполный |
| `network_stack_restore` | `restore_network_connectivity` | Да | Иногда | Восстанавливает сеть, VPN и WMI |
| `clean_junk` | `run_deep_clean` | Зависит от каталогов | Нет | Не требуется |
| `clean_ram` | `clean_ram` | Нет | Нет | Не требуется |
| `disable_search_indexer` | `disable_search_indexer` | Да | Нет | Work / Restore |
| `clear_event_logs` | `clear_event_logs` | Да | Нет | Не применяется |
| `optimize_ntfs` | `optimize_ntfs` | Да | Иногда | Частично через Restore Defaults |
| `disable_printer_spooler` | `disable_printer_spooler` | Да | Нет | Work / Restore |
| `optimize_services` | `optimize_services` | Да | Нет | Work / Restore |
| `max_performance` | `run_max_performance_profile` | Да | Иногда | Work / Restore |
| `optimize_pagefile` | `optimize_pagefile` | Да | Часто | Work / Restore |
| `apply_cpu_turbo` | `apply_cpu_turbo` | Да | Нет | Work / Restore |
| `extreme_rollback` | `run_extreme_rollback` | Да | Иногда | Специализированный откат Extreme Mode |

## CS2 и игры

| Ключ действия | Функция | Администратор | Требования | Откат |
| --- | --- | --- | --- | --- |
| `gaming_install_cs2` | `install_cs2_config_with_clipboard` | Нет | Каталог CFG | Ручное восстановление конфига |
| `gaming_smart_launch` | `copy_cs2_smart_launch` | Нет | Нет | Не требуется |
| `gaming_pro_telemetry` | `apply_pro_telemetry` | Нет | Каталог CFG | Ручное восстановление конфига |
| `gaming_network_registry` | `apply_zernix_network_registry` | Да | Сетевой адаптер | Частичный откат реестра |
| `gaming_audio_pro` | `apply_zernix_audio_pro` | Нет | Каталог CFG | Ручное восстановление конфига |
| `gaming_kernel_latency_on` | `apply_kernel_latency_boost` | Рекомендуется | `cs2.exe` | `gaming_kernel_latency_off` |
| `gaming_kernel_latency_off` | `release_kernel_latency_boost` | Нет | Нет | Освобождает активные блокировки |
| `gaming_disable_cfg` | `disable_cfg_for_cs2` | Да | Windows mitigation API | Ручная проверка политики процесса |
| `gaming_frametime` | `set_cs2_frametime_telemetry(True)` | Нет | Каталог CFG | Ручное восстановление конфига |
| `gaming_network_diagnostic` | `_run_network_diagnostic` | Нет | Сеть | Не требуется |
| `gaming_dx_cache` | `clear_directx_shader_cache_2026` | Нет | Нет | Кэш создается заново |
| `gaming_steam_cache` | `clear_steam_shader_precache` | Нет | Steam | Кэш создается заново |
| `gaming_turbo_mode` | `run_gaming_turbo_mode` | Да | Нет | Work / Restore |

## Пресеты

| Пресет | Функция | Администратор | Откат |
| --- | --- | --- | --- |
| CyberSport | `run_cybersport_preset` | Да | Work / Restore или Extreme Rollback |
| Gaming Turbo | `run_gaming_turbo_preset` | Да | Work / Restore |
| Work / Restore | `run_work_restore_preset` | Да | Основной сценарий возврата настроек |

## Известные ограничения

- Изменения `autoexec.cfg` не восстанавливаются полностью автоматически.
- Политику `Set-ProcessMitigation` для `cs2.exe` после отката следует проверить вручную.
- Глобальные TCP-настройки `netsh` покрыты откатом не полностью.
- Настройки NVIDIA и полноэкранной оптимизации стоит проверять после Work / Restore отдельно.
