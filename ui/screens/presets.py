import customtkinter as ctk

from core.tweaks import preserve_virtualization_enabled, set_preserve_virtualization_enabled
from ui.styles import Theme
from ui.widgets import Tooltip


class PresetsFrame(ctk.CTkFrame):
    def __init__(self, master, tr, apply_preset_callback):
        super().__init__(
            master,
            fg_color=Theme.COLORS["page_bg"],
            corner_radius=16,
            border_width=1,
            border_color=Theme.COLORS["border_light"],
        )
        self.tr = tr
        self.apply_preset_callback = apply_preset_callback
        self.cards = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self.title_label = ctk.CTkLabel(
            self,
            text=self.tr("presets_title"),
            font=Theme.FONTS["title"],
            text_color="#111315",
        )
        self.title_label.grid(row=0, column=0, sticky="w", padx=18, pady=(16, 6))

        self.subtitle_label = ctk.CTkLabel(
            self,
            text=self.tr("presets_subtitle"),
            font=Theme.FONTS["body"],
            text_color="#5A6370",
            justify="left",
            wraplength=620,
        )
        self.subtitle_label.grid(row=1, column=0, sticky="w", padx=18, pady=(0, 8))

        dev_row = ctk.CTkFrame(self, fg_color="transparent")
        dev_row.grid(row=2, column=0, sticky="w", padx=18, pady=(0, 10))
        self._dev_switch = ctk.CTkSwitch(
            dev_row,
            text=self.tr("preset_developer_vm"),
            command=self._on_developer_toggle,
        )
        self._dev_switch.pack(anchor="w")
        if preserve_virtualization_enabled():
            self._dev_switch.select()
        else:
            self._dev_switch.deselect()

        self.content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.content.grid(row=3, column=0, sticky="nsew", padx=14, pady=(0, 12))

        for preset_key in ("cybersport", "gaming_turbo", "work_restore"):
            card = self._build_preset_card(self.content, preset_key)
            card.pack(fill="x", pady=8)

    def _build_preset_card(self, parent, preset_key: str):
        card = ctk.CTkFrame(
            parent,
            fg_color=Theme.COLORS["card_bg"],
            corner_radius=10,
            border_width=1,
            border_color=Theme.COLORS["border_light"],
        )
        card.grid_columnconfigure(0, weight=1)

        title_row = ctk.CTkFrame(card, fg_color="transparent")
        title_row.grid(row=0, column=0, sticky="w", padx=14, pady=(12, 6))

        title = ctk.CTkLabel(
            title_row,
            text=self.tr(f"preset_{preset_key}_title"),
            font=("Segoe UI", 17, "bold"),
            text_color="#1B1F24",
        )
        title.pack(side="left")
        info = ctk.CTkLabel(
            title_row,
            text="i",
            width=18,
            height=18,
            corner_radius=9,
            fg_color="#E7F7FA",
            text_color=Theme.COLORS["accent"],
            font=("Segoe UI", 11, "bold"),
            cursor="question_arrow",
        )
        info.pack(side="left", padx=(8, 0))
        tooltip = Tooltip(
            info,
            f"{self.tr('preset_safe_block')}\n{self.tr(f'preset_{preset_key}_safe_actions')}\n\n"
            f"{self.tr('preset_caution_block')}\n{self.tr(f'preset_{preset_key}_caution_actions')}",
        )

        apply_button = ctk.CTkButton(
            card,
            text=self.tr("preset_apply_button"),
            width=220,
            height=34,
            fg_color="#12CFC0" if preset_key == "cybersport" else Theme.COLORS["accent"],
            hover_color="#0AA99D" if preset_key == "cybersport" else Theme.COLORS["accent_hover"],
            text_color="#FFFFFF",
            command=lambda key=preset_key: self.apply_preset_callback(key),
        )
        apply_button.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 12))

        self.cards[preset_key] = {
            "title": title,
            "tooltip": tooltip,
            "button": apply_button,
        }
        return card

    def _on_developer_toggle(self):
        set_preserve_virtualization_enabled(bool(self._dev_switch.get()))

    def apply_language(self, tr):
        self.tr = tr
        self.title_label.configure(text=self.tr("presets_title"))
        self.subtitle_label.configure(text=self.tr("presets_subtitle"))
        self._dev_switch.configure(text=self.tr("preset_developer_vm"))
        for preset_key, meta in self.cards.items():
            meta["title"].configure(text=self.tr(f"preset_{preset_key}_title"))
            meta["tooltip"].set_text(
                f"{self.tr('preset_safe_block')}\n{self.tr(f'preset_{preset_key}_safe_actions')}\n\n"
                f"{self.tr('preset_caution_block')}\n{self.tr(f'preset_{preset_key}_caution_actions')}"
            )
            meta["button"].configure(text=self.tr("preset_apply_button"))
