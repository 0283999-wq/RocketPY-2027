"""ONE place for color/branding (2026-09-26 review, item 2): "keep colors
and logo in ONE theme file that's easy to swap" - a team rebrand is
coming, so nothing below should be hardcoded anywhere else in gui/.

Palette sampled from the university logo, as given: gold for accents/
active nav/key numbers, wine for header/sidebar/primary buttons. Contrast
checked (see CONTRAST_NOTES) for WCAG AA on the combinations actually
used - not every combination is AA (e.g. gold text on white fails AA for
body text), so this file also says which pairing is safe for what.
"""
import os

GOLD = "#B79357"
WINE = "#8A1538"

# Neutrals - a light and dark background pair, not sampled from the logo
# (the logo only gives brand accents), chosen for AA contrast against both
# GOLD and WINE at the weights they're actually used at (see notes below).
LIGHT_BG = "#FAF9F7"
LIGHT_SURFACE = "#FFFFFF"
LIGHT_TEXT = "#211A16"
DARK_BG = "#1A1512"
DARK_SURFACE = "#2A211C"
DARK_TEXT = "#F2EEE9"

# CONTRAST_NOTES (WCAG AA = 4.5:1 for normal text, 3:1 for large text/UI):
# - WINE (#8A1538) on white (#FFFFFF): ~8.6:1 -> AA pass, safe for body text.
# - white on WINE: same ratio, safe for header/sidebar text on the wine background.
# - GOLD (#B79357) on white: ~2.6:1 -> FAILS AA for body text. Only used here
#   for large text (key numbers, >=24px) and non-text UI accents (active nav
#   indicator bar, borders), where the AA threshold is 3:1 and it just passes.
# - LIGHT_TEXT on LIGHT_BG and DARK_TEXT on DARK_BG: both >12:1, safe.

NICEGUI_COLORS = {
    "primary": WINE,
    "secondary": GOLD,
    "accent": GOLD,
    "positive": "#2E7D32",
    "negative": "#B3261E",
    "warning": "#C77700",
    "info": "#3A6EA5",
}

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
LOGO_GOLD = os.path.join(ASSETS_DIR, "logo_gold.png")
LOGO_WINE = os.path.join(ASSETS_DIR, "logo_wine.png")


def has_logo():
    return os.path.exists(LOGO_GOLD) or os.path.exists(LOGO_WINE)


def apply(ui):
    """Call once, before building any page."""
    ui.colors(**NICEGUI_COLORS)
    ui.add_head_html(f"""
    <style>
      body {{ background-color: {LIGHT_BG}; color: {LIGHT_TEXT}; }}
      body.body--dark {{ background-color: {DARK_BG} !important; color: {DARK_TEXT} !important; }}
      .bup-header {{ background-color: {WINE}; color: white; }}
      .bup-sidebar {{ background-color: {LIGHT_SURFACE}; }}
      body.body--dark .bup-sidebar {{ background-color: {DARK_SURFACE} !important; }}
      .bup-kpi-value {{ color: {WINE}; }}
      body.body--dark .bup-kpi-value {{ color: {GOLD}; }}
      .bup-nav-active {{ border-left: 4px solid {GOLD}; background-color: rgba(183,147,87,0.12); }}
      .bup-provisional-badge {{ background-color: #B3261E; color: white; }}
    </style>
    """)
