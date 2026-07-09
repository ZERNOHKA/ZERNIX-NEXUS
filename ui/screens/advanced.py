import customtkinter as ctk

from ui.styles import Theme
from ui.screens.system import SystemFrame
from ui.screens.gaming import GamingFrame
from ui.screens.presets import PresetsFrame


class AdvancedFrame(ctk.CTkFrame):
    """
    Объединяет System, Gaming и Presets под одной вкладкой «Дополнительно»
    с внутренним переключателем, без дублирования логики строк действий.
    """

    def __init__(self, master, tr, system_rows, gaming_rows, apply_preset_callback):
        super().__init__(
            master,
            fg_color=Theme.COLORS["page_bg"],
            corner_radius=16,
            border_width=1,
            border_color=Theme.COLORS["border_light"],
        )
        self.tr = tr
        self._panel_keys = ("system", "gaming", "presets")
        self.nav_buttons = {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self.title_label = ctk.CTkLabel(
            self,
            text=self.tr("advanced_title"),
            font=Theme.FONTS["title"],
            text_color="#111315",
        )
        self.title_label.grid(row=0, column=0, sticky="w", padx=18, pady=(16, 4))

        self.subtitle_label = ctk.CTkLabel(
            self,
            text=self.tr("advanced_subtitle"),
            font=Theme.FONTS["body"],
            text_color="#5A6370",
            justify="left",
            wraplength=640,
        )
        self.subtitle_label.grid(row=1, column=0, sticky="w", padx=18, pady=(0, 10))

        nav_bar = ctk.CTkFrame(self, fg_color="transparent")
        nav_bar.grid(row=2, column=0, sticky="w", padx=14, pady=(0, 8))

        for col, panel in enumerate(self._panel_keys):
            btn = ctk.CTkButton(
                nav_bar,
                text=self.tr(f"advanced_{panel}_tab"),
                width=118,
                height=32,
                fg_color=Theme.COLORS["tab_inactive_bg"],
                hover_color="#F8FAFC",
                text_color=Theme.COLORS["text_primary"],
                border_width=1,
                border_color=Theme.COLORS["nav_border"],
                corner_radius=12,
                command=lambda p=panel: self._show_panel(p),
            )
            btn.grid(row=0, column=col, padx=(0, 7))
            self.nav_buttons[panel] = btn

        self.content_host = ctk.CTkFrame(self, fg_color="transparent")
        self.content_host.grid(row=3, column=0, sticky="nsew", padx=4, pady=(0, 8))
        self.content_host.grid_columnconfigure(0, weight=1)
        self.content_host.grid_rowconfigure(0, weight=1)

        self.system_page = SystemFrame(self.content_host, tr, system_rows)
        self.gaming_page = GamingFrame(self.content_host, tr, gaming_rows)
        self.presets_page = PresetsFrame(self.content_host, tr, apply_preset_callback)

        self.system_page.grid(row=0, column=0, sticky="nsew")
        self.gaming_page.grid(row=0, column=0, sticky="nsew")
        self.presets_page.grid(row=0, column=0, sticky="nsew")
        self.gaming_page.grid_remove()
        self.presets_page.grid_remove()
        self._active_panel = "system"
        self._highlight_nav("system")

    def _show_panel(self, panel: str):
        if panel not in self._panel_keys:
            return
        self._active_panel = panel
        self.system_page.grid_remove()
        self.gaming_page.grid_remove()
        self.presets_page.grid_remove()
        if panel == "system":
            self.system_page.grid(row=0, column=0, sticky="nsew")
        elif panel == "gaming":
            self.gaming_page.grid(row=0, column=0, sticky="nsew")
        else:
            self.presets_page.grid(row=0, column=0, sticky="nsew")
        self._highlight_nav(panel)

    def _highlight_nav(self, active: str):
        for panel, button in self.nav_buttons.items():
            selected = panel == active
            button.configure(
                fg_color=Theme.COLORS["tab_active_bg"] if selected else Theme.COLORS["tab_inactive_bg"],
                hover_color=Theme.COLORS["tab_active_bg"] if selected else "#F8FAFC",
                text_color=Theme.COLORS["tab_active_text"] if selected else Theme.COLORS["text_primary"],
                border_color=Theme.COLORS["accent_soft"] if selected else Theme.COLORS["nav_border"],
            )

    def apply_language(self, tr):
        self.tr = tr
        self.title_label.configure(text=self.tr("advanced_title"))
        self.subtitle_label.configure(text=self.tr("advanced_subtitle"))
        for panel in self._panel_keys:
            self.nav_buttons[panel].configure(text=self.tr(f"advanced_{panel}_tab"))
        self.system_page.apply_language(tr)
        self.gaming_page.apply_language(tr)
        self.presets_page.apply_language(tr)
