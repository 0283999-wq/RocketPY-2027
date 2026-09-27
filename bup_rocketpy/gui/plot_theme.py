"""Shared matplotlib styling (2026-09-27 UI redesign, Step 3: "restyle
every matplotlib figure to the theme"). Every plot-producing function in
the app calls `apply()` on its axes before saving, so a rebrand only
touches here, not a dozen scattered `ax.set_xlabel(..., color=...)` calls.

PNGs are static raster images - they can't repaint themselves after a
live client-side dark-mode toggle the way the surrounding NiceGUI/CSS
can. The compromise: a TRANSPARENT figure/axes background (the plot
blends into whichever card it's placed in, light or dark) plus a
neutral medium-contrast color for axis text/ticks/gridlines/spines that
stays legible against BOTH theme.py's LIGHT_SURFACE and DARK_SURFACE,
rather than rendering two separate PNGs per plot. Brand WINE/GOLD stay
as the data-line colors (unchanged - both already read fine on a
transparent background in either mode).
"""
WINE = "#8A1538"
GOLD = "#B79357"
AXIS = "#8C8375"  # neutral warm gray - ~4:1 contrast against both theme.py surfaces


def apply(ax, fig=None):
    """Call after building the plot, before fig.tight_layout()/savefig()."""
    if fig is not None:
        fig.patch.set_alpha(0)
    ax.patch.set_alpha(0)
    ax.tick_params(colors=AXIS, labelsize=8)
    ax.xaxis.label.set_color(AXIS)
    ax.yaxis.label.set_color(AXIS)
    if ax.title.get_text():
        ax.title.set_color(AXIS)
    for spine in ax.spines.values():
        spine.set_color(AXIS)
        spine.set_alpha(0.6)
    ax.grid(True, alpha=0.25, color=AXIS)
    legend = ax.get_legend()
    if legend is not None:
        legend.get_frame().set_alpha(0)
        for text in legend.get_texts():
            text.set_color(AXIS)


def savefig(fig, path, **kwargs):
    """Transparent-background save - the ONE place this flag is set, so
    it can never be forgotten at a given call site."""
    fig.savefig(path, transparent=True, **kwargs)
