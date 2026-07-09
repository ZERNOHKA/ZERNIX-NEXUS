import tkinter.font as tkfont

import customtkinter as ctk

from ui.styles import Theme
from ui.widgets import GradientActionButton


class DashboardFrame(ctk.CTkFrame):
    """Главный экран: крупные action-кнопки, быстрые статусы и мониторинг системы."""

    # --- Размеры главной страницы (правьте здесь) ---
    # Высота кнопок буст/откат; горизонтальный запас к тексту; минимальная ширина кнопки;
    # высота рамки «Система». Метры CPU/GPU/RAM: ui/widgets.py → HardwareMeter(..., compact=True).
    _BTN_HEIGHT = 66
    _BTN_GAP_VISUAL = 16
    _BTN_TEXT_PAD = 72
    _MIN_BTN_W = 250

    def __init__(self, master, tr, optimize_command, rollback_command):
        super().__init__(
            master,
            fg_color=Theme.COLORS["page_bg"],
            corner_radius=16,
            border_width=1,
            border_color=Theme.COLORS["border_dark"],
        )
        self.tr = tr
        self._btn_font_metric = tkfont.Font(self, family="Segoe UI", size=17, weight="bold")

        self.grid_columnconfigure(0, weight=1)

        hero = ctk.CTkFrame(self, fg_color="transparent")
        hero.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 6))
        hero.grid_columnconfigure(0, weight=1)
        self.hero_title = ctk.CTkLabel(
            hero,
            text=self.tr("hero_title"),
            font=("Segoe UI", 17, "bold"),
            text_color="#0B0D10",
            anchor="w",
        )
        self.hero_title.grid(row=0, column=0, sticky="w")
        self.hero_subtitle = ctk.CTkLabel(
            hero,
            text=self.tr("hero_subtitle"),
            font=Theme.FONTS["body"],
            text_color="#5A6370",
            anchor="w",
            justify="left",
            wraplength=620,
        )
        self.hero_subtitle.grid(row=1, column=0, sticky="w", pady=(6, 0))

        self.btn_row = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_row.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 6))
        self.btn_row.grid_columnconfigure(0, weight=1)
        self.btn_row.grid_columnconfigure(1, weight=1)

        init_w = self._natural_button_width(self.tr("btn_session_boost"))
        self.boost_button = GradientActionButton(
            self.btn_row,
            f"🚀  {self.tr('btn_session_boost')}",
            optimize_command,
            width=init_w,
            height=self._BTN_HEIGHT,
            blue_primary=True,
        )
        self.boost_button.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.rollback_button = GradientActionButton(
            self.btn_row,
            f"⟳  {self.tr('btn_session_rollback')}",
            rollback_command,
            width=self._natural_button_width(self.tr("btn_session_rollback")),
            height=self._BTN_HEIGHT,
            blue_primary=False,
        )
        self.rollback_button.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        self._btn_layout_job = None
        self.btn_row.bind("<Configure>", self._schedule_action_button_layout)
        for delay in (16, 80, 200, 450):
            self.after(delay, self._layout_action_buttons)

        quick_status = ctk.CTkFrame(self, fg_color="transparent")
        quick_status.grid(row=2, column=0, sticky="ew", padx=14, pady=(4, 10))
        for col in range(4):
            quick_status.grid_columnconfigure(col, weight=1)

        status_specs = (
            ("◉", "quick_mode_title", "quick_mode_value"),
            ("⚙", "quick_profile_title", "quick_profile_value"),
            ("🧩", "quick_services_title", "quick_services_value"),
            ("⚡", "quick_power_title", "quick_power_value"),
        )
        self.quick_status_cards = []
        for idx, (icon, title, value) in enumerate(status_specs):
            status_card = ctk.CTkFrame(
                quick_status,
                fg_color="#F3F6FA",
                corner_radius=14,
                border_width=1,
                border_color="#E4EAF1",
            )
            status_card.grid(row=0, column=idx, sticky="ew", padx=(0 if idx == 0 else 6, 0 if idx == 3 else 6))

            ctk.CTkLabel(
                status_card,
                text=icon,
                font=("Segoe UI Symbol", 17),
                text_color="#35C6D4",
            ).pack(anchor="w", padx=10, pady=(8, 2))
            title_label = ctk.CTkLabel(
                status_card,
                text=self.tr(title),
                font=("Segoe UI", 11, "bold"),
                text_color="#5B6573",
            )
            title_label.pack(anchor="w", padx=10)
            value_label = ctk.CTkLabel(
                status_card,
                text=self.tr(value),
                font=("Segoe UI", 12, "bold"),
                text_color="#0F172A",
                anchor="w",
                justify="left",
                wraplength=170,
            )
            value_label.pack(anchor="w", padx=10, pady=(1, 9))
            self.quick_status_cards.append((title, value, title_label, value_label))

        monitor_shell = ctk.CTkFrame(
            self,
            fg_color="#FFFFFF",
            corner_radius=14,
            border_width=1,
            border_color=Theme.COLORS["border_dark"],
        )
        monitor_shell.grid(row=3, column=0, sticky="ew", padx=14, pady=(2, 8))
        self.dashboard_system_title = ctk.CTkLabel(
            monitor_shell,
            text=self.tr("monitoring_title"),
            font=Theme.FONTS["section"],
            text_color="#16181B",
        )
        self.dashboard_system_title.pack(anchor="w", padx=14, pady=(10, 8))

        meter_row = ctk.CTkFrame(monitor_shell, fg_color="transparent")
        meter_row.pack(fill="x", padx=10, pady=(0, 10))
        for col in range(3):
            meter_row.grid_columnconfigure(col, weight=1)

        self.monitor_cards = {}
        self.monitor_cards["cpu"] = self._create_monitor_card(meter_row, 0, "🧠", "CPU", "0%", self.tr("temperature_na"))
        self.monitor_cards["gpu"] = self._create_monitor_card(meter_row, 1, "🎮", "GPU", "0%", self.tr("temperature_na"))
        self.monitor_cards["ram"] = self._create_monitor_card(meter_row, 2, "💾", "RAM", "0%", "-- / -- GB")

    def _create_monitor_card(self, parent, column, icon, title, value_text, sub_text):
        card = ctk.CTkFrame(
            parent,
            fg_color="#F4F7FA",
            corner_radius=14,
            border_width=1,
            border_color="#E4EAF1",
        )
        card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 6, 0 if column == 2 else 6))
        ctk.CTkLabel(
            card,
            text=icon,
            font=("Segoe UI Symbol", 20),
            text_color="#54C7D6",
        ).pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(
            card,
            text=title,
            font=("Segoe UI", 12, "bold"),
            text_color="#4B5563",
        ).pack(anchor="w", padx=12)
        value_label = ctk.CTkLabel(
            card,
            text=value_text,
            font=("Segoe UI", 28, "bold"),
            text_color="#111827",
        )
        value_label.pack(anchor="w", padx=12, pady=(2, 4))
        progress = ctk.CTkProgressBar(
            card,
            width=170,
            height=11,
            corner_radius=9,
            progress_color="#39C8D8",
            fg_color="#DFE6EE",
        )
        progress.set(0)
        progress.pack(anchor="w", padx=12, pady=(2, 5))
        sub_label = ctk.CTkLabel(
            card,
            text=sub_text,
            font=("Segoe UI", 11),
            text_color="#64748B",
            anchor="w",
        )
        sub_label.pack(anchor="w", padx=12, pady=(0, 11))
        return {"value": value_label, "progress": progress, "sub": sub_label}

    def _natural_button_width(self, label: str) -> int:
        try:
            tw = int(self._btn_font_metric.measure(label))
        except Exception:
            tw = len(label) * 10
        tw = int(tw * 1.06) + 6
        return max(self._MIN_BTN_W, tw + self._BTN_TEXT_PAD)

    def refresh_status_cards(self, snapshot, language):
        is_ru = str(language or "").lower().startswith("ru")
        mode_raw = str(snapshot.get("mode") or "")
        profile_raw = str(snapshot.get("profile") or "")
        services_raw = str(snapshot.get("services_status") or "")
        power_raw = str(snapshot.get("power_plan") or "")

        if is_ru:
            mode_map = {
                "CS2 boost": "CS2 BOOST",
                "Windows default": "Стандарт Windows",
            }
            profile_map = {
                "CS2": "Профиль CS2",
                "Gaming": "Игровой",
                "Standard": "Стандарт",
                "Optimal": "Оптимальный",
                "Extreme": "Экстремальный",
                "Balanced": "Сбалансированный",
            }
            services_map = {
                "Optimized": "Оптимизированы",
                "Partially optimized": "Частично оптимизированы",
                "Default": "По умолчанию",
                "Unknown": "Неизвестно",
            }
            power_map = {
                "Ultimate Performance": "Максимальная производительность",
                "High Performance": "Высокая производительность",
                "Standard": "Сбалансированный",
            }
        else:
            mode_map = {
                "CS2 boost": "CS2 BOOST",
                "Windows default": "Windows Default",
            }
            profile_map = {
                "CS2": "CS2 Profile",
                "Gaming": "Gaming",
                "Standard": "Standard",
                "Optimal": "Optimal",
                "Extreme": "Extreme",
                "Balanced": "Balanced",
            }
            services_map = {
                "Optimized": "Optimized",
                "Partially optimized": "Partially optimized",
                "Default": "Default",
                "Unknown": "Unknown",
            }
            power_map = {
                "Ultimate Performance": "Ultimate Performance",
                "High Performance": "High Performance",
                "Standard": "Balanced",
            }

        dynamic_values = {
            "quick_mode_value": mode_map.get(mode_raw, mode_raw or self.tr("quick_mode_value")),
            "quick_profile_value": profile_map.get(profile_raw, profile_raw or self.tr("quick_profile_value")),
            "quick_services_value": services_map.get(services_raw, services_raw or self.tr("quick_services_value")),
            "quick_power_value": power_map.get(power_raw, power_raw or self.tr("quick_power_value")),
        }

        for _title_key, value_key, _title_label, value_label in self.quick_status_cards:
            value_label.configure(text=dynamic_values.get(value_key, self.tr(value_key)))
        return

    def update_hardware_snapshot(self, snapshot):
        cpu_value = float(snapshot.get("cpu", 0.0) or 0.0)
        gpu_available = bool(snapshot.get("gpu_available", True))
        gpu_value = snapshot.get("gpu")
        ram_value = float(snapshot.get("ram", 0.0) or 0.0)

        self.monitor_cards["cpu"]["value"].configure(text=f"{int(round(max(0.0, min(100.0, cpu_value))))}%")
        self.monitor_cards["cpu"]["progress"].set(max(0.0, min(1.0, cpu_value / 100.0)))
        cpu_temp = snapshot.get("cpu_temp")
        self.monitor_cards["cpu"]["sub"].configure(
            text=self.tr("temperature_value").format(value=int(cpu_temp)) if cpu_temp is not None else self.tr("temperature_na")
        )

        if gpu_available and gpu_value is not None:
            gpu_value = float(gpu_value)
            self.monitor_cards["gpu"]["value"].configure(text=f"{int(round(max(0.0, min(100.0, gpu_value))))}%")
            self.monitor_cards["gpu"]["progress"].set(max(0.0, min(1.0, gpu_value / 100.0)))
        else:
            self.monitor_cards["gpu"]["value"].configure(text="—")
            self.monitor_cards["gpu"]["progress"].set(0.0)
        gpu_temp = snapshot.get("gpu_temp")
        self.monitor_cards["gpu"]["sub"].configure(
            text=self.tr("temperature_value").format(value=int(gpu_temp)) if gpu_temp is not None else self.tr("temperature_na")
        )

        self.monitor_cards["ram"]["value"].configure(text=f"{int(round(max(0.0, min(100.0, ram_value))))}%")
        self.monitor_cards["ram"]["progress"].set(max(0.0, min(1.0, ram_value / 100.0)))
        ram_used = snapshot.get("ram_used_gb")
        ram_total = snapshot.get("ram_total_gb")
        if ram_used is not None and ram_total:
            self.monitor_cards["ram"]["sub"].configure(text=f"{ram_used:.1f} / {ram_total:.0f} GB")
        else:
            self.monitor_cards["ram"]["sub"].configure(text="-- / -- GB")

    def animate_sparklines(self):
        return

    def _schedule_action_button_layout(self, event=None):
        if event is not None and getattr(event, "widget", None) is not self.btn_row:
            return
        if self._btn_layout_job is not None:
            try:
                self.after_cancel(self._btn_layout_job)
            except Exception:
                pass
        self._btn_layout_job = self.after(40, self._layout_action_buttons)

    def _layout_action_buttons(self):
        self._btn_layout_job = None
        try:
            row_w = int(self.btn_row.winfo_width())
        except Exception:
            return
        if row_w < 100:
            return

        boost_label = self.tr("btn_session_boost")
        rollback_label = self.tr("btn_session_rollback")
        need_b = self._natural_button_width(boost_label)
        need_r = self._natural_button_width(rollback_label)

        gap = self._BTN_GAP_VISUAL
        budget = max(0, row_w - gap)
        h = self._BTN_HEIGHT

        if need_b + need_r <= budget:
            bw, rw = need_b, need_r
        else:
            total = float(need_b + need_r)
            if total <= 0:
                bw = rw = max(self._MIN_BTN_W, budget // 2)
            else:
                bw = int(budget * need_b / total)
                rw = budget - bw
                bw = max(self._MIN_BTN_W, bw)
                rw = max(self._MIN_BTN_W, rw)
                guard = 0
                while bw + rw > budget and guard < 800:
                    guard += 1
                    if bw >= rw and bw > self._MIN_BTN_W:
                        bw -= 1
                    elif rw > self._MIN_BTN_W:
                        rw -= 1
                    else:
                        break

        try:
            self.boost_button.resize_to(bw, h)
            self.rollback_button.resize_to(rw, h)
        except Exception:
            pass

    def apply_language(self, tr):
        self.tr = tr
        self._btn_font_metric = tkfont.Font(self, family="Segoe UI", size=17, weight="bold")
        self.hero_title.configure(text=self.tr("hero_title"))
        self.hero_subtitle.configure(text=self.tr("hero_subtitle"))
        self.boost_button.set_text(f"🚀  {self.tr('btn_session_boost')}")
        self.rollback_button.set_text(f"⟳  {self.tr('btn_session_rollback')}")
        self.dashboard_system_title.configure(text=self.tr("monitoring_title"))
        for title_key, value_key, title_label, value_label in self.quick_status_cards:
            title_label.configure(text=self.tr(title_key))
            value_label.configure(text=self.tr(value_key))
        self.after(10, self._layout_action_buttons)
        self.after(120, self._layout_action_buttons)
