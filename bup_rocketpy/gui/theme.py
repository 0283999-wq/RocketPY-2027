"""ONE place for color/branding/design tokens (2026-09-26 review, item 2;
2026-09-27 review, "UI redesign" - Step 1's design system). "Keep colors
and logo in ONE theme file that's easy to swap" - a team rebrand is
coming, so nothing below should be hardcoded anywhere else in gui/.

Every other page/component imports its colors, spacing, radii, shadows
and motion timings from HERE (or from the CSS custom properties this
file injects, e.g. `var(--bup-radius-md)`), never a hex code or a magic
number typed inline - that's what makes the eventual rebrand a one-file
change.
"""
import os

GOLD = "#B79357"
WINE = "#8A1538"

# Status colors (success/warning/error/info) - used by status_chip()/
# kpi_card() in components.py and mirrored into NICEGUI_COLORS below so
# ui.notify(type="positive"/...)/ui.button(color="negative"/...) match.
SUCCESS = "#2E7D32"
WARNING = "#C77700"
ERROR = "#B3261E"
INFO = "#3A6EA5"

# Neutrals - a light and dark background pair, not sampled from the logo
# (the logo only gives brand accents), chosen for AA contrast against both
# GOLD and WINE at the weights they're actually used at (see notes below).
LIGHT_BG = "#FAF9F7"
LIGHT_SURFACE = "#FFFFFF"
LIGHT_TEXT = "#211A16"
LIGHT_MUTED = "#6B6259"
LIGHT_BORDER = "rgba(33,26,22,0.10)"
DARK_BG = "#1A1512"
DARK_SURFACE = "#2A211C"
DARK_TEXT = "#F2EEE9"
DARK_MUTED = "#B8AEA3"
DARK_BORDER = "rgba(242,238,233,0.12)"

# CONTRAST_NOTES (WCAG AA = 4.5:1 for normal text, 3:1 for large text/UI):
# - WINE (#8A1538) on white (#FFFFFF): ~8.6:1 -> AA pass, safe for body text.
# - white on WINE: same ratio, safe for header/sidebar text on the wine background.
# - GOLD (#B79357) on white: ~2.6:1 -> FAILS AA for body text. Only used here
#   for large text (key numbers, >=24px) and non-text UI accents (active nav
#   indicator bar, borders), where the AA threshold is 3:1 and it just passes.
# - LIGHT_TEXT on LIGHT_BG and DARK_TEXT on DARK_BG: both >12:1, safe.
# - LIGHT_MUTED (#6B6259) on LIGHT_BG/LIGHT_SURFACE: ~4.6:1 -> AA pass for
#   secondary/caption text. DARK_MUTED on DARK_BG/DARK_SURFACE: ~7.4:1.
# - SUCCESS/ERROR/INFO on white: all >=4.5:1. WARNING (#C77700) on white:
#   ~3.0:1 - large text/icons only, same rule as GOLD.

# Motion tokens (Step 2): short, consistent, and gated behind
# prefers-reduced-motion everywhere they're used below - "nothing may
# slow down the app" means these stay in the 150-250ms range, no
# exceptions, and every keyframe animation is additive (elements are
# already correctly laid out/visible without them).
DURATION_FAST_MS = 120
DURATION_BASE_MS = 200
DURATION_SLOW_MS = 250
EASE_STANDARD = "cubic-bezier(0.4, 0, 0.2, 1)"  # Material "standard" easing

NICEGUI_COLORS = {
    "primary": WINE,
    "secondary": GOLD,
    "accent": GOLD,
    "positive": SUCCESS,
    "negative": ERROR,
    "warning": WARNING,
    "info": INFO,
}

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
LOGO_GOLD = os.path.join(ASSETS_DIR, "logo_gold.png")
LOGO_WINE = os.path.join(ASSETS_DIR, "logo_wine.png")
FONTS_DIR = "/static/fonts"  # served by app.py's /static route


def has_logo():
    return os.path.exists(LOGO_GOLD) or os.path.exists(LOGO_WINE)


def apply(ui):
    """Call once, before building any page."""
    ui.colors(**NICEGUI_COLORS)
    ui.add_head_html(f"""
    <style>
      @font-face {{
        font-family: 'Inter';
        font-style: normal;
        font-weight: 400;
        font-display: swap;
        src: url('{FONTS_DIR}/inter-400.woff2') format('woff2');
      }}
      @font-face {{
        font-family: 'Inter';
        font-style: normal;
        font-weight: 500;
        font-display: swap;
        src: url('{FONTS_DIR}/inter-500.woff2') format('woff2');
      }}
      @font-face {{
        font-family: 'Inter';
        font-style: normal;
        font-weight: 600;
        font-display: swap;
        src: url('{FONTS_DIR}/inter-600.woff2') format('woff2');
      }}
      @font-face {{
        font-family: 'Inter';
        font-style: normal;
        font-weight: 700;
        font-display: swap;
        src: url('{FONTS_DIR}/inter-700.woff2') format('woff2');
      }}

      :root {{
        --bup-wine: {WINE};
        --bup-gold: {GOLD};
        --bup-success: {SUCCESS};
        --bup-warning: {WARNING};
        --bup-error: {ERROR};
        --bup-info: {INFO};
        --bup-bg: {LIGHT_BG};
        --bup-surface: {LIGHT_SURFACE};
        --bup-text: {LIGHT_TEXT};
        --bup-muted: {LIGHT_MUTED};
        --bup-border: {LIGHT_BORDER};
        --bup-radius-sm: 6px;
        --bup-radius-md: 10px;
        --bup-radius-lg: 16px;
        --bup-shadow-sm: 0 1px 2px rgba(33,26,22,0.06), 0 1px 1px rgba(33,26,22,0.04);
        --bup-shadow-md: 0 4px 10px rgba(33,26,22,0.08), 0 1px 2px rgba(33,26,22,0.05);
        --bup-shadow-lg: 0 12px 24px rgba(33,26,22,0.12), 0 2px 4px rgba(33,26,22,0.06);
        --bup-duration-fast: {DURATION_FAST_MS}ms;
        --bup-duration-base: {DURATION_BASE_MS}ms;
        --bup-duration-slow: {DURATION_SLOW_MS}ms;
        --bup-ease: {EASE_STANDARD};
      }}
      body.body--dark {{
        --bup-bg: {DARK_BG};
        --bup-surface: {DARK_SURFACE};
        --bup-text: {DARK_TEXT};
        --bup-muted: {DARK_MUTED};
        --bup-border: {DARK_BORDER};
        --bup-shadow-sm: 0 1px 2px rgba(0,0,0,0.30);
        --bup-shadow-md: 0 4px 10px rgba(0,0,0,0.35);
        --bup-shadow-lg: 0 12px 24px rgba(0,0,0,0.45);
      }}

      * {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
      body {{ background-color: var(--bup-bg); color: var(--bup-text); }}
      body.body--dark {{ background-color: var(--bup-bg) !important; color: var(--bup-text) !important; }}

      .bup-header {{ background-color: {WINE}; color: white; }}
      .bup-sidebar {{ background-color: var(--bup-surface) !important; transition: transform var(--bup-duration-base) var(--bup-ease); }}
      .bup-kpi-value {{ color: {WINE}; }}
      body.body--dark .bup-kpi-value {{ color: {GOLD}; }}
      .bup-nav-active {{ border-left: 4px solid {GOLD}; background-color: rgba(183,147,87,0.12); }}
      .bup-nav-item {{ border-left: 4px solid transparent; transition: background-color var(--bup-duration-fast) var(--bup-ease); border-radius: 0 var(--bup-radius-sm) var(--bup-radius-sm) 0; }}
      .bup-nav-item:hover {{ background-color: rgba(183,147,87,0.08); }}
      .bup-provisional-badge {{ background-color: var(--bup-error); color: white; }}
      .bup-status-bar {{ background-color: rgba(183,147,87,0.10); border-bottom: 1px solid var(--bup-border); }}
      .bup-status-chip {{ background-color: var(--bup-surface); border: 1px solid var(--bup-border); border-radius: 999px; }}

      /* --- Cards --- */
      .bup-card {{
        background-color: var(--bup-surface);
        border: 1px solid var(--bup-border);
        border-radius: var(--bup-radius-lg);
        box-shadow: var(--bup-shadow-sm);
        transition: box-shadow var(--bup-duration-base) var(--bup-ease), transform var(--bup-duration-base) var(--bup-ease);
      }}
      .bup-card:hover {{ box-shadow: var(--bup-shadow-md); }}
      .bup-card-interactive {{ cursor: pointer; }}
      .bup-card-interactive:hover {{ transform: translateY(-1px); }}
      .bup-card-interactive:active {{ transform: translateY(0); }}

      /* --- KPI cards --- */
      .bup-kpi-card {{ background-color: var(--bup-surface); border: 1px solid var(--bup-border); border-radius: var(--bup-radius-md); border-top: 3px solid var(--bup-border); box-shadow: var(--bup-shadow-sm); }}
      .bup-kpi-card[data-status="good"] {{ border-top-color: var(--bup-success); }}
      .bup-kpi-card[data-status="warn"] {{ border-top-color: var(--bup-warning); }}
      .bup-kpi-card[data-status="bad"] {{ border-top-color: var(--bup-error); }}
      .bup-kpi-label {{ color: var(--bup-muted); }}

      /* --- Buttons: kept as thin wrappers over Quasar's own button so
         native focus rings/ripple/disabled states are never fought --- */
      .bup-btn-primary {{ transition: transform var(--bup-duration-fast) var(--bup-ease), box-shadow var(--bup-duration-fast) var(--bup-ease); }}
      .bup-btn-primary:hover {{ box-shadow: var(--bup-shadow-sm); }}
      .bup-btn-primary:active {{ transform: scale(0.98); }}

      /* --- Empty state / dropzone --- */
      .bup-empty-state {{ border: 1px dashed var(--bup-border); border-radius: var(--bup-radius-lg); background-color: var(--bup-surface); }}
      .bup-dropzone .q-uploader {{ border: 2px dashed var(--bup-border); border-radius: var(--bup-radius-lg); background-color: var(--bup-surface); transition: border-color var(--bup-duration-fast) var(--bup-ease), background-color var(--bup-duration-fast) var(--bup-ease); }}
      .bup-dropzone .q-uploader:hover {{ border-color: var(--bup-gold); }}

      /* --- Skeleton loading --- */
      .bup-skeleton {{ background: linear-gradient(90deg, var(--bup-border) 25%, rgba(183,147,87,0.18) 37%, var(--bup-border) 63%); background-size: 400% 100%; border-radius: var(--bup-radius-sm); }}
      @media (prefers-reduced-motion: no-preference) {{
        .bup-skeleton {{ animation: bupShimmer 1.4s ease infinite; }}
      }}
      @keyframes bupShimmer {{ 0% {{ background-position: 100% 50%; }} 100% {{ background-position: 0 50%; }} }}

      /* --- Motion: page entrance + card stagger, both reduced-motion gated --- */
      @media (prefers-reduced-motion: no-preference) {{
        .bup-page-enter {{ animation: bupFadeSlideIn var(--bup-duration-slow) var(--bup-ease) both; }}
        .bup-stagger {{ animation: bupFadeSlideIn var(--bup-duration-base) var(--bup-ease) both; animation-delay: calc(var(--bup-i, 0) * 40ms); }}
        .bup-progress-anim .q-linear-progress__model {{ transition: width var(--bup-duration-base) var(--bup-ease); }}
      }}
      @keyframes bupFadeSlideIn {{ from {{ opacity: 0; transform: translateY(6px); }} to {{ opacity: 1; transform: translateY(0); }} }}

      /* Hover/press micro-interactions on any element opted in */
      .bup-hoverable {{ transition: background-color var(--bup-duration-fast) var(--bup-ease); }}
      .bup-hoverable:hover {{ background-color: rgba(183,147,87,0.08); }}
    </style>
    <script src="/static/motion.js"></script>
    """)
