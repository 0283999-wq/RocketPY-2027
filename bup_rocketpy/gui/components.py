"""Design system components (2026-09-27 UI redesign, Step 1): every page
builds its UI from THESE, not one-off `ui.card()`/`ui.label()` calls with
inline Tailwind classes scattered per page - that's what keeps the whole
app looking like one product instead of ten different pages someone
skinned separately. Colors/spacing/radii/shadows/motion all come from
theme.py's CSS custom properties (`var(--bup-...)`), never a hex code or
a hardcoded pixel value here.

After inserting cards with `.bup-stagger` or KPI values with
`data-bup-countup` from a background task/click handler (i.e., NOT the
initial page render, which motion.js already handles on
DOMContentLoaded), call `finish_motion()` once to trigger the stagger/
count-up JS for the newly-added elements.
"""
import contextlib

from nicegui import ui

STATUS_COLORS = {
    "neutral": "var(--bup-border)",
    "good": "var(--bup-success)",
    "warn": "var(--bup-warning)",
    "bad": "var(--bup-error)",
    "info": "var(--bup-info)",
}
CHIP_KIND_STYLE = {
    "neutral": "background-color: var(--bup-surface); border-color: var(--bup-border); color: var(--bup-text);",
    "success": "background-color: rgba(46,125,50,0.12); border-color: var(--bup-success); color: var(--bup-success);",
    "warning": "background-color: rgba(199,119,0,0.12); border-color: var(--bup-warning); color: var(--bup-warning);",
    "error": "background-color: rgba(179,38,30,0.12); border-color: var(--bup-error); color: var(--bup-error);",
    "info": "background-color: rgba(58,110,165,0.12); border-color: var(--bup-info); color: var(--bup-info);",
}
BUTTON_PROPS = {
    "primary": "color=primary text-color=white unelevated",
    "secondary": "color=primary outline",
    "ghost": "flat color=primary",
    "danger": "color=negative unelevated",
}


def finish_motion():
    """Call after inserting cards/KPI values OUTSIDE the initial page
    render (e.g. inside a button click handler or a background-task
    completion callback) - re-runs the stagger/count-up JS for whatever
    is new. A no-op-looking call, but see motion.js's own docstring for
    why DOMContentLoaded alone doesn't cover this."""
    ui.run_javascript("if (window.BUP) { BUP.stagger('.bup-stagger', document); BUP.countUp(document); }")


def page_header(title, description=None, action_label=None, action_icon=None, on_action=None):
    """Title + one-line description + an optional single primary action -
    the same header shape on every page, per the redesign brief."""
    with ui.row().classes("w-full items-start justify-between gap-4 bup-page-enter"):
        with ui.column().classes("gap-0"):
            ui.label(title).classes("text-2xl font-bold")
            if description:
                ui.label(description).classes("text-sm").style("color: var(--bup-muted)")
        if action_label:
            button(action_label, kind="primary", icon=action_icon, on_click=on_action)


def button(label, kind="primary", icon=None, on_click=None):
    b = ui.button(label, icon=icon, on_click=on_click).classes("bup-btn-primary").props(BUTTON_PROPS.get(kind, BUTTON_PROPS["primary"]))
    return b


@contextlib.contextmanager
def card(classes="", interactive=False, stagger_index=None):
    """A themed container - use instead of a bare ui.card() everywhere.
    stagger_index=i adds a staggered fade/slide-in entrance (see
    theme.py's .bup-stagger); leave it None for a card that renders
    outside a list/grid (e.g. a single results panel)."""
    extra = " bup-card-interactive" if interactive else ""
    stagger = " bup-stagger" if stagger_index is not None else ""
    c = ui.card().classes(f"bup-card{extra}{stagger} p-4 gap-2 {classes}")
    if stagger_index is not None:
        c.style(f"--bup-i: {stagger_index}")
    with c:
        yield c


def kpi_card(label, value, unit="", caption=None, status="neutral", countup_target=None, decimals=1, stagger_index=None):
    """label/value/unit/caption + a colored top border for at-a-glance
    status (good/warn/bad/neutral/info) - the ONE KPI shape every page
    uses (Home, Simulate results, Monte Carlo, Validation, RCSM...).
    countup_target: if given, the value text animates from 0 on
    render/finish_motion() instead of appearing instantly."""
    stagger = " bup-stagger" if stagger_index is not None else ""
    c = ui.element("div").classes(f"bup-kpi-card{stagger} p-3 flex flex-col gap-1").props(f'data-status="{status}"')
    if stagger_index is not None:
        c.style(f"--bup-i: {stagger_index}")
    with c:
        ui.label(label).classes("bup-kpi-label text-xs")
        with ui.row().classes("items-baseline gap-1"):
            if countup_target is not None:
                ui.html(
                    f'<span class="bup-kpi-value text-xl font-bold" data-bup-countup data-bup-target="{countup_target}" '
                    f'data-bup-decimals="{decimals}" data-bup-suffix=" {unit}">0 {unit}</span>'
                )
            else:
                ui.label(f"{value} {unit}".strip()).classes("bup-kpi-value text-xl font-bold")
        if caption:
            ui.label(caption).classes("text-xs").style("color: var(--bup-muted)")
    return c


def hero_stat(label, value, unit="", status="neutral", caption=None):
    """A single big, high-contrast number - for field-friendly displays
    (Launch Day's wind reading, Validation's predicted-vs-flight) meant
    to be read at a glance, not studied like a KPI grid."""
    color = STATUS_COLORS.get(status, "var(--bup-wine)") if status != "neutral" else "var(--bup-wine)"
    with card(classes="items-center text-center") as c:
        ui.label(label).classes("text-sm").style("color: var(--bup-muted)")
        ui.label(f"{value} {unit}".strip()).style(f"font-size: 2.75rem; font-weight: 700; line-height: 1.1; color: {color};")
        if caption:
            ui.label(caption).classes("text-sm mt-1").style("color: var(--bup-muted)")
    return c


def status_chip(text, kind="neutral"):
    return ui.label(text).classes("text-xs px-2 py-1 rounded-full border").style(CHIP_KIND_STYLE.get(kind, CHIP_KIND_STYLE["neutral"]))


def empty_state(icon, text, action_label=None, on_action=None):
    with ui.column().classes("bup-empty-state w-full items-center justify-center gap-3 py-12 px-6"):
        ui.icon(icon).classes("text-5xl").style("color: var(--bup-muted)")
        ui.label(text).classes("text-sm text-center max-w-md").style("color: var(--bup-muted)")
        if action_label:
            button(action_label, kind="primary", on_click=on_action)


def skeleton(height="20px", width="100%"):
    ui.element("div").classes("bup-skeleton").style(f"height: {height}; width: {width};")


def dropzone(label, on_upload, accept=None):
    """A styled wrapper around ui.upload - Quasar's own uploader already
    supports dropping a file onto it, this only makes it LOOK like a
    dropzone (dashed border, centered icon+label) instead of a plain
    upload button."""
    with ui.column().classes("bup-dropzone w-full items-center"):
        u = ui.upload(label=label, on_upload=on_upload, auto_upload=True).classes("w-full")
        if accept:
            u.props(f"accept={accept}")
    return u


def confirm_dialog(message, confirm_label="Delete", cancel_label="Cancel", danger=True):
    """Usage:
        dialog, confirm_btn = confirm_dialog("Delete this run?")
        confirm_btn.on_click(lambda: (do_delete(), dialog.close()))
        ...
        dialog.open()
    Returns (dialog, confirm_button) so the caller wires its own action -
    NOT a context manager: the dialog is built once and opened later, on
    demand, so scoping it to a `with` block at build time doesn't fit.
    """
    with ui.dialog() as dialog, ui.card().classes("bup-card p-4 gap-3"):
        ui.label(message)
        with ui.row().classes("justify-end gap-2 w-full"):
            ui.button(cancel_label, on_click=dialog.close).props(BUTTON_PROPS["ghost"])
            confirm_btn = ui.button(confirm_label).props(BUTTON_PROPS["danger" if danger else "primary"])
    return dialog, confirm_btn


def data_table(columns, rows, classes=""):
    return ui.table(columns=columns, rows=rows).classes(f"w-full bup-card {classes}").props("flat")


def stepper_header(labels, current_index):
    """A visual step rail (Load -> Review -> Simulate -> Results, etc.) -
    NOT Quasar's paginated QStepper: every step's content stays visible
    and reachable on the page below (matches how this app already
    works - free to jump back and re-review before re-simulating), this
    only draws the "where am I" indicator bar above it."""
    with ui.row().classes("items-center w-full gap-0 bup-page-enter"):
        for i, label in enumerate(labels):
            done = i < current_index
            active = i == current_index
            color = "var(--bup-success)" if done else ("var(--bup-wine)" if active else "var(--bup-border)")
            text_color = "var(--bup-text)" if (done or active) else "var(--bup-muted)"
            with ui.row().classes("items-center gap-2"):
                ui.label("✓" if done else str(i + 1)).classes("rounded-full flex items-center justify-center text-xs font-bold").style(
                    f"width:24px; height:24px; background-color:{color}; color:white; text-align:center; line-height:24px; padding:0;"
                )
                ui.label(label).classes("text-sm font-medium").style(f"color:{text_color}")
            if i < len(labels) - 1:
                ui.element("div").classes("flex-1").style(f"height:2px; background-color:{'var(--bup-success)' if done else 'var(--bup-border)'}; margin: 0 8px;")
