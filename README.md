<p align="center">
  <img src="assets/logo_z.png" alt="ZERNIX NEXUS" width="180">
</p>

# ZERNIX NEXUS

**ZERNIX NEXUS** - desktop-приложение для Windows, которое помогает быстро подготовить систему к игровой сессии в CS2, применить оптимизации, посмотреть состояние ПК и вернуть настройки обратно после игры.

Проект я оформил как полноценную утилиту: с графическим интерфейсом, пресетами, ручными инструментами, системой отката, проверкой лицензии и скриптами сборки в `.exe`.

## Скриншоты

| Главный экран | Пресеты |
| --- | --- |
| ![Главный экран](docs/screenshots/dashboard.png) | ![Пресеты](docs/screenshots/presets.png) |

| Расширенные настройки | Лицензия |
| --- | --- |
| ![Расширенные настройки](docs/screenshots/advanced-system.png) | ![Экран лицензии](docs/screenshots/license.png) |

## Что умеет приложение

- Быстрый **CS2 Session Boost** с последовательным применением игровых оптимизаций.
- **Session Rollback** для возврата системы к более обычному рабочему состоянию.
- Пресеты **CyberSport**, **Gaming Turbo** и **Work / Restore**.
- Ручные инструменты для служб Windows, питания, RAM, NTFS, визуальных эффектов, сетевых настроек и очистки.
- CS2-инструменты: launch options, конфиг, telemetry HUD, shader cache, network profile.
- Мониторинг CPU, GPU и RAM прямо на главном экране.
- Проверка лицензии через внешний license server.
- Demo/portfolio-режим для просмотра интерфейса без подключения к серверу лицензий.
- Скрипты сборки обычной и защищенной версии приложения.

## Стек

- **Python**
- **CustomTkinter**
- **psutil**
- **Pillow**
- **WMI / pywin32**
- **requests**
- **cryptography**
- **PyInstaller**
- **Nuitka / PyArmor**

## Структура проекта

```text
.
├── assets/                 # Логотипы и изображения интерфейса
├── core/                   # Логика оптимизаций, отката, очистки и latency-профиля
├── docs/                   # Документация, QA-чеклист, audit matrix и скриншоты
├── ui/                     # Компоненты интерфейса и отдельные экраны
├── main.py                 # Главная точка входа
├── licensing.py            # Проверка лицензии и HWID
├── check_license.py        # CLI-проверка лицензии
├── build.bat               # Сборка через PyInstaller
├── build_protected.ps1     # Защищенная сборка через PyArmor + Nuitka
├── run_demo.bat            # Запуск без проверки лицензии для скриншотов
└── ZERNIX_v3_Pro.spec      # Конфигурация PyInstaller
```

## Запуск

Установить зависимости:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Обычный запуск:

```powershell
python main.py
```

Запуск для просмотра интерфейса и скриншотов без license server:

```powershell
python main.py --demo
```

или:

```powershell
.\run_demo.bat
```

Большинство системных функций требуют запуск от имени администратора. Без прав администратора интерфейс откроется, но часть изменений реестра, служб, питания и сети может не примениться.

## Лицензирование

В проекте есть проверка лицензии через внешний сервер. Настройки можно передать через переменные окружения:

```powershell
$env:ZERNIX_LICENSE_SERVER_URL = "https://your-domain.example/validate"
$env:ZERNIX_LICENSE_API_KEY = "your-api-key"
```

Для локального просмотра интерфейса используется demo-режим:

```powershell
python main.py --demo
```

Он не удаляет лицензирование из проекта, а только пропускает проверку сервера, чтобы можно было открыть приложение и сделать скриншоты.

## Сборка

Обычная сборка:

```powershell
.\build.bat
```

Защищенная сборка:

```powershell
.\build_protected.ps1 -StrictObfuscation
```

Приватные ключи, реальные API-ключи, файлы лицензий и готовые `.exe` не должны попадать в репозиторий.

## Документация

- [Manual QA Checklist](docs/QA_MANUAL_CHECKLIST.md)
- [Audit Matrix](docs/AUDIT_MATRIX.md)

## Важное замечание

Приложение меняет системные настройки Windows: службы, реестр, сетевой профиль, план питания и конфиги CS2. Перед агрессивными пресетами лучше создать точку восстановления системы.

Проект ориентирован на демонстрацию desktop-разработки, работы с Windows API/утилитами, UI на Python и аккуратной упаковки приложения под Windows.
