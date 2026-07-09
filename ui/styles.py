class Theme:
    """Palette aligned with ZERNIX light glass / Win11-style dashboard reference."""
    COLORS = {
        "app_bg": "#F0F2F5",
        "sidebar_bg": "#E8EDF4",
        "sidebar_bg_bottom": "#F2F5FA",
        "page_bg": "#FFFFFF",
        "card_bg": "#FFFFFF",
        "border_dark": "#E2E8F0",
        "border_light": "#E2E8F0",
        "text_primary": "#111827",
        "text_secondary": "#6B7280",
        "text_muted": "#9CA3AF",
        "accent": "#4A90E2",
        "accent_hover": "#3B7BC7",
        "accent_soft": "#93C5FD",
        "tab_active_bg": "#E3F2FD",
        "tab_active_text": "#4A90E2",
        "tab_inactive_bg": "#FFFFFF",
        "nav_border": "#E2E8F0",
        "danger": "#EF4444",
        "success_teal": "#2DD4BF",
    }

    FONTS = {
        "brand": ("Segoe UI", 30, "bold"),
        "title": ("Segoe UI", 24, "bold"),
        "section": ("Segoe UI", 18, "bold"),
        "small_bold": ("Segoe UI", 12, "bold"),
        "label": ("Segoe UI", 14, "bold"),
        "body": ("Segoe UI", 11),
        "mono": ("Consolas", 12),
        "mono_small": ("Consolas", 11),
        "button": ("Segoe UI", 14, "bold"),
    }

    RADII = {
        "page": 16,
        "card": 12,
        "soft": 10,
        "button": 12,
    }

    SPACING = {
        "page_pad_x": 20,
        "page_pad_y": 20,
        "inner_pad": 16,
        "card_gap": 14,
        "row_gap": 8,
    }
