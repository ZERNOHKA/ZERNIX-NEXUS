import customtkinter as ctk

from ui.styles import Theme
from ui.widgets import ActionRow


class SystemFrame(ctk.CTkFrame):
    def __init__(self, master, tr, rows):
        super().__init__(
            master,
            fg_color=Theme.COLORS["page_bg"],
            corner_radius=16,
            border_width=1,
            border_color=Theme.COLORS["border_light"],
        )
        self.tr = tr
        self.action_rows = {}
        self._pending_rows = list(rows)
        self._pending_row_index = 0

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.title_label = ctk.CTkLabel(self, text=self.tr("system_title"), font=Theme.FONTS["title"], text_color="#111315")
        self.title_label.grid(row=0, column=0, sticky="w", padx=18, pady=(16, 10))

        self.actions = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.actions.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=16, pady=(0, 0))
        self.opt_header = None

        self.after(0, self._build_rows_batch)

    def _build_rows_batch(self, batch_size: int = 6):
        start_idx = self._pending_row_index
        end_idx = min(len(self._pending_rows), start_idx + batch_size)
        for idx in range(start_idx, end_idx):
            key, desc_key, action_key, command = self._pending_rows[idx]
            if idx == 2:
                separator = ctk.CTkFrame(self.actions, height=2, fg_color=Theme.COLORS["border_light"])
                separator.pack(fill="x", padx=30, pady=(20, 15))
                self.opt_header = ctk.CTkLabel(
                    self.actions,
                    text=self.tr("optimization_settings"),
                    font=Theme.FONTS["small_bold"],
                    text_color="#7D8592",
                )
                self.opt_header.pack(anchor="w", padx=30, pady=(0, 8))
            row = ActionRow(
                self.actions,
                self.tr(key),
                self.tr(desc_key),
                self.tr(action_key),
                command,
                self.tr(desc_key),
            )
            row.pack(fill="x", pady=6)
            self.action_rows[key] = {"row": row, "desc_key": desc_key, "action_key": action_key}
        self._pending_row_index = end_idx
        if self._pending_row_index < len(self._pending_rows):
            self.after(16, self._build_rows_batch)

    def apply_language(self, tr):
        self.tr = tr
        self.title_label.configure(text=self.tr("system_title"))
        if self.opt_header is not None:
            self.opt_header.configure(text=self.tr("optimization_settings"))
        for key, meta in self.action_rows.items():
            meta["row"].set_texts(
                self.tr(key),
                self.tr(meta["desc_key"]),
                self.tr(meta["action_key"]),
                self.tr(meta["desc_key"]),
            )
