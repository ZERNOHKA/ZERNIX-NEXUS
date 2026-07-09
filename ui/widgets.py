import tkinter as tk

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFilter, ImageTk

from ui.styles import Theme


def bind_license_entry_hotkeys(entry: ctk.CTkEntry) -> None:
    """
    Горячие клавиши поля лицензионного ключа:
    Ctrl+A — выделить всю строку (удобно удалить ключ целиком и вставить заново).
    """

    def _select_all(_event=None):
        try:
            entry.select_range(0, "end")
            entry.icursor("end")
        except tk.TclError:
            pass
        return "break"

    entry.bind("<Control-a>", _select_all)
    entry.bind("<Control-A>", _select_all)


class SparklineWidget(ctk.CTkFrame):
    def __init__(self, master, title: str, top_label: str, width: int = 244, height: int = 68):
        super().__init__(
            master,
            width=width,
            height=height,
            fg_color=Theme.COLORS["card_bg"],
            corner_radius=Theme.RADII["soft"],
        )
        self.grid_propagate(False)
        self.values = [0.0 for _ in range(24)]
        self.title = ctk.CTkLabel(
            self,
            text=title,
            font=("Segoe UI", 16, "normal"),
            text_color="#202020",
        )
        self.title.grid(row=0, column=0, sticky="w", padx=16, pady=(9, 1))
        self.top = ctk.CTkLabel(self, text=top_label, font=("Segoe UI", 11), text_color="#5D6068")
        self.top.grid(row=0, column=1, sticky="e", padx=16, pady=(9, 1))
        self.canvas = tk.Canvas(self, width=200, height=26, bg="#FFFFFF", highlightthickness=0)
        self.canvas.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 8))
        self.columnconfigure(0, weight=1)
        self._border_item = None
        self._line_item = None
        self._draw_sparkline()

    def tick(self):
        return

    def set_labels(self, title: str, top_label: str):
        self.title.configure(text=title)
        self.top.configure(text=top_label)

    def set_top_label(self, top_label: str):
        self.top.configure(text=top_label)

    def set_latest_value(self, normalized_value: float):
        value = max(0.0, min(1.0, float(normalized_value)))
        self.values = self.values[1:] + [value]
        self._draw_sparkline()

    def _draw_sparkline(self):
        w = int(self.canvas.cget("width"))
        h = int(self.canvas.cget("height"))
        if self._border_item is None:
            self._border_item = self.canvas.create_rectangle(1, 1, w - 1, h - 1, outline="#E7EAEE", width=1)
        points = []
        count = len(self.values)
        for idx, value in enumerate(self.values):
            x = 10 + idx * ((w - 20) / max(1, count - 1))
            y = h - 7 - value * (h - 16)
            points.extend((x, y))
        if self._line_item is None:
            self._line_item = self.canvas.create_line(points, fill=Theme.COLORS["accent"], width=2.5, smooth=True)
        else:
            self.canvas.coords(self._line_item, *points)


class GradientActionButton(ctk.CTkFrame):
    def __init__(
        self,
        master,
        text: str,
        command,
        width: int = 470,
        height: int = 78,
        *,
        blue_primary: bool = False,
    ):
        super().__init__(master, width=width, height=height, fg_color="transparent")
        self.grid_propagate(False)
        self.command = command
        self._blue_primary = blue_primary
        self.canvas = tk.Canvas(
            self,
            width=width,
            height=height,
            bg=self._resolve_bg(master),
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self.image = self._build_gradient_image(width, height)
        self._bg_image_item = self.canvas.create_image(0, 0, image=self.image, anchor="nw")
        self.text_item = self.canvas.create_text(
            width / 2,
            height / 2,
            text=text,
            fill="white",
            font=("Segoe UI", 16, "bold"),
            anchor="center",
        )
        for target in (self, self.canvas):
            target.bind("<Button-1>", self._handle_click)
            target.bind("<Enter>", self._handle_hover_in)
            target.bind("<Leave>", self._handle_hover_out)

    def _resolve_bg(self, widget):
        """Tk Canvas does not accept fg_color=\"transparent\"; walk up until a solid color."""
        current = widget
        for _ in range(20):
            try:
                fg = current.cget("fg_color")
                if isinstance(fg, (list, tuple)) and fg:
                    fg = fg[0]
                if fg and str(fg).lower() != "transparent":
                    return fg
            except Exception:
                pass
            try:
                current = current.master
            except Exception:
                break
        return Theme.COLORS["page_bg"]

    def _build_gradient_image(self, width: int, height: int):
        radius = 22
        shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        if self._blue_primary:
            glow = (69, 206, 221, 120)
            left = (62, 212, 221)
            right = (74, 157, 234)
        else:
            glow = (52, 196, 233, 110)
            left = (58, 201, 225)
            right = (69, 146, 224)
        shadow_draw.rounded_rectangle((20, 12, width - 16, height - 8), radius=radius, fill=glow)
        shadow = shadow.filter(ImageFilter.GaussianBlur(10))

        base = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        gradient = Image.new("RGBA", (width - 44, height - 22), (0, 0, 0, 0))
        grad_draw = ImageDraw.Draw(gradient)
        inner_w, inner_h = gradient.size
        for x in range(inner_w):
            t = x / max(1, inner_w - 1)
            r = int(left[0] * (1 - t) + right[0] * t)
            g = int(left[1] * (1 - t) + right[1] * t)
            b = int(left[2] * (1 - t) + right[2] * t)
            grad_draw.line((x, 0, x, inner_h), fill=(r, g, b, 255))

        mask = Image.new("L", gradient.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, inner_w - 1, inner_h - 1), radius=radius, fill=255)
        gradient.putalpha(mask)
        base.alpha_composite(shadow, (0, 0))
        base.alpha_composite(gradient, (22, 8))
        return ImageTk.PhotoImage(base)

    def _handle_click(self, _event):
        self.command()

    def _handle_hover_in(self, _event):
        self.canvas.configure(cursor="hand2")

    def _handle_hover_out(self, _event):
        self.canvas.configure(cursor="")

    def set_text(self, text: str):
        self.canvas.itemconfigure(self.text_item, text=text)

    def resize_to(self, width: int, height: int):
        """Подгонка под ширину контейнера (ретина/DPI и разные окна)."""
        width = max(140, int(width))
        height = max(44, int(height))
        try:
            self.configure(width=width, height=height)
        except Exception:
            pass
        try:
            self.canvas.configure(width=width, height=height)
        except Exception:
            return
        self.canvas.delete(self._bg_image_item)
        self.image = self._build_gradient_image(width, height)
        self._bg_image_item = self.canvas.create_image(0, 0, image=self.image, anchor="nw")
        self.canvas.tag_lower(self._bg_image_item, self.text_item)
        self.canvas.coords(self.text_item, width / 2, height / 2)


class Tooltip:
    def __init__(self, widget, text: str, delay_ms: int = 350):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self._after_id = None
        self._tip = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def set_text(self, text: str):
        self.text = text
        if self._tip is not None:
            self._hide()

    def _schedule(self, _event=None):
        self._cancel()
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _cancel(self):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self):
        self._cancel()
        if not self.text or self._tip is not None:
            return
        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        tip = tk.Toplevel(self.widget)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{x}+{y}")
        frame = ctk.CTkFrame(tip, fg_color="#111827", corner_radius=8, border_width=1, border_color="#2F3A46")
        frame.pack()
        label = ctk.CTkLabel(
            frame,
            text=self.text,
            font=("Segoe UI", 12),
            text_color="#FFFFFF",
            justify="left",
            wraplength=360,
        )
        label.pack(padx=10, pady=8)
        self._tip = tip

    def _hide(self, _event=None):
        self._cancel()
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None


class ActionRow(ctk.CTkFrame):
    def __init__(self, master, title: str, description: str, action_text: str, command, tooltip_text: str = None):
        super().__init__(
            master,
            fg_color=Theme.COLORS["card_bg"],
            corner_radius=Theme.RADII["soft"],
            border_width=1,
            border_color=Theme.COLORS["border_light"],
        )
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.title_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.title_frame.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 3))
        self.title_label = ctk.CTkLabel(
            self.title_frame,
            text=title,
            font=("Segoe UI", 14, "bold"),
            text_color=Theme.COLORS["text_primary"],
        )
        self.title_label.pack(side="left")
        self.info_label = ctk.CTkLabel(
            self.title_frame,
            text="i",
            width=18,
            height=18,
            corner_radius=9,
            fg_color="#E7F7FA",
            text_color=Theme.COLORS["accent"],
            font=("Segoe UI", 11, "bold"),
            cursor="question_arrow",
        )
        self.info_label.pack(side="left", padx=(8, 0))
        self.tooltip = Tooltip(self.info_label, tooltip_text or description)
        self.action_button = ctk.CTkButton(
            self,
            text=action_text,
            width=120,
            height=32,
            fg_color=Theme.COLORS["accent"],
            hover_color=Theme.COLORS["accent_hover"],
            text_color="#FFFFFF",
            command=command,
        )
        self.action_button.grid(row=0, column=1, sticky="e", padx=12, pady=8)

    def set_texts(self, title: str, description: str, action_text: str, tooltip_text: str = None):
        self.title_label.configure(text=title)
        self.action_button.configure(text=action_text)
        self.tooltip.set_text(tooltip_text or description)


class HardwareMeter(ctk.CTkFrame):
    """
    Карточки CPU/GPU/RAM.
    Размеры по умолчанию и режим compact (главная dashboard) задайте ниже в ветке if compact.
    """

    def __init__(self, master, title: str, width: int = 116, height: int = 146, *, compact: bool = False):
        if compact:
            width = 110
            height = 138
        super().__init__(
            master,
            fg_color=Theme.COLORS["card_bg"],
            corner_radius=Theme.RADII["soft"],
            border_width=1,
            border_color=Theme.COLORS["border_dark"],
            width=width,
            height=height,
        )
        self.grid_propagate(False)
        title_sz = ("Segoe UI", 11, "bold")
        val_sz = ("Segoe UI", 19, "bold") if compact else ("Segoe UI", 22, "bold")
        bar_w = 58 if compact else 60
        self.title_label = ctk.CTkLabel(
            self,
            text=title,
            font=title_sz,
            text_color="#171A1F",
        )
        self.title_label.pack(anchor="center", pady=(9, 4) if compact else (10, 4))
        self.value_label = ctk.CTkLabel(self, text="0%", font=val_sz, text_color=Theme.COLORS["accent"])
        self.value_label.pack(anchor="center", pady=(4, 4) if compact else (4, 4))
        self.progress = ctk.CTkProgressBar(
            self,
            width=bar_w,
            height=12 if compact else 12,
            progress_color=Theme.COLORS["accent"],
            fg_color="#EEF2F6",
            corner_radius=10,
        )
        self.progress.pack(pady=(6, 6) if compact else (6, 6))
        self.progress.set(0)
        self.sub_label = ctk.CTkLabel(self, text="Monitoring...", font=("Segoe UI", 11), text_color="#68727E")
        self.sub_label.pack(anchor="center")

    def set_title(self, title: str):
        self.title_label.configure(text=title)

    def set_value(self, value):
        if value is None:
            self.value_label.configure(text="N/A")
            self.progress.set(0)
            self.sub_label.configure(text="Unavailable")
            return
        clamped = max(0.0, min(100.0, float(value)))
        self.value_label.configure(text=f"{int(round(clamped))}%")
        self.progress.set(clamped / 100.0)
        self.sub_label.configure(text="Stable" if clamped < 70 else "Active" if clamped < 90 else "Boosted")
