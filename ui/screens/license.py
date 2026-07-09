import customtkinter as ctk

from ui.styles import Theme
from ui.widgets import bind_license_entry_hotkeys


class LicenseFrame(ctk.CTkFrame):
    def __init__(
        self,
        master,
        tr,
        license_path: str,
        hwid: str,
        is_active: bool,
        activate_command,
        deactivate_command,
        copy_hwid_command,
    ):
        super().__init__(
            master,
            fg_color=Theme.COLORS["page_bg"],
            corner_radius=16,
            border_width=1,
            border_color=Theme.COLORS["border_light"],
        )
        self.tr = tr
        self.license_path = license_path
        self.hwid = hwid
        self.activate_command = activate_command
        self.deactivate_command = deactivate_command
        self.copy_hwid_command = copy_hwid_command

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.title_label = ctk.CTkLabel(self, text=self.tr("license_title"), font=Theme.FONTS["title"], text_color="#111315")
        self.title_label.grid(row=0, column=0, sticky="w", padx=18, pady=(16, 8))

        self.card = ctk.CTkFrame(
            self,
            fg_color=Theme.COLORS["card_bg"],
            corner_radius=12,
            border_width=1,
            border_color=Theme.COLORS["border_light"],
        )
        self.card.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 12))

        self.status_label = ctk.CTkLabel(self.card, text="", font=("Segoe UI", 16, "bold"), text_color="#15181B")
        self.status_label.pack(anchor="w", padx=16, pady=(14, 6))
        self.hwid_label = ctk.CTkLabel(self.card, text=f"HWID: {self.hwid}", font=Theme.FONTS["mono"], text_color="#5A6470")
        self.hwid_label.pack(anchor="w", padx=16, pady=(0, 4))
        self.hwid_label.bind("<Button-1>", lambda _event: self.copy_hwid_command())
        self.hwid_label.bind("<Enter>", lambda _event: self.hwid_label.configure(cursor="hand2", text_color=Theme.COLORS["accent"]))
        self.hwid_label.bind("<Leave>", lambda _event: self.hwid_label.configure(cursor="", text_color="#5A6470"))
        self.server_hint_label = ctk.CTkLabel(
            self.card,
            text=self.tr("license_server_hint"),
            font=Theme.FONTS["body"],
            text_color="#5A6470",
        )
        self.server_hint_label.pack(anchor="w", padx=16, pady=(0, 4))
        self.file_label = ctk.CTkLabel(self.card, text="", font=Theme.FONTS["mono"], text_color="#5A6470")
        self.file_label.pack(anchor="w", padx=16, pady=(0, 12))

        self.entry = ctk.CTkEntry(self.card, width=420, height=38, corner_radius=10, placeholder_text=self.tr("license_placeholder"))
        self.entry.pack(anchor="w", padx=16, pady=(0, 10))
        self.entry.bind("<Control-KeyPress-v>", self._paste_license_key)
        self.entry.bind("<Control-KeyPress-V>", self._paste_license_key)
        self.entry.bind("<Shift-Insert>", self._paste_license_key)
        self.entry.bind("<Button-3>", self._paste_license_key)
        bind_license_entry_hotkeys(self.entry)

        self.activate_button = ctk.CTkButton(
            self.card,
            text=self.tr("license_activate"),
            width=160,
            height=36,
            fg_color=Theme.COLORS["accent"],
            hover_color=Theme.COLORS["accent_hover"],
            text_color="#FFFFFF",
            command=self.activate_command,
        )
        self.activate_button.pack(anchor="w", padx=16, pady=(0, 16))

        self.deactivate_button = ctk.CTkButton(
            self.card,
            text=self.tr("license_remove"),
            width=220,
            height=34,
            fg_color="#B84444",
            hover_color="#9E3737",
            text_color="#FFFFFF",
            command=self.deactivate_command,
        )
        self.deactivate_button.pack(anchor="w", padx=16, pady=(0, 16))

        self.update_status(is_active)

    def update_status(self, is_active: bool):
        status_text = self.tr("license_active") if is_active else self.tr("license_inactive")
        self.status_label.configure(text=f"{self.tr('license_status')}: {status_text}")
        self.file_label.configure(text=f"{self.tr('license_file')}: {self.license_path}")

    def apply_language(self, tr, is_active: bool):
        self.tr = tr
        self.title_label.configure(text=self.tr("license_title"))
        self.entry.configure(placeholder_text=self.tr("license_placeholder"))
        self.activate_button.configure(text=self.tr("license_activate"))
        self.deactivate_button.configure(text=self.tr("license_remove"))
        self.server_hint_label.configure(text=self.tr("license_server_hint"))
        self.update_status(is_active)

    def _paste_license_key(self, _event=None):
        try:
            pasted = self.clipboard_get()
        except Exception:
            return "break"
        self.entry.delete(0, "end")
        self.entry.insert(0, str(pasted).strip())
        return "break"
