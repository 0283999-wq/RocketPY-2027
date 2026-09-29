"""HTML + CSS report, printed to PDF by a real browser engine (Playwright
Chromium) - 2026-09-28 review item 4's explicit instruction to stop
fighting reportlab. CSS handles page breaks/typography; Chromium's own
`page.pdf()` API (not CSS Paged Media, which Chromium doesn't implement)
handles the running footer and page numbers via headerTemplate/
footerTemplate. The table of contents gets REAL page numbers via a
two-pass render: pass 1 prints with placeholder numbers, a text search
over the resulting PDF finds which page each heading actually landed on,
then pass 2 re-renders the SAME template with those numbers filled in -
the TOC page's own row count/height never changes between passes (same
fixed list of sections), so every later page number is identical in
both passes.
"""
import base64
import os
import re

import jinja2

from bup_rocketpy import report as report_module  # WINE/GOLD/INK/LIGHT_GREY - the one place these brand colors are pinned

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_templates")
CHROMIUM_PATH = "/opt/pw-browsers/chromium"

# (anchor id, TOC display title, the marker text to search for in the
# rendered PDF's own extracted text to find its real page) - each
# section heading in report.html carries an invisible
# (font-size:1px, color:transparent, still text-extractable)
# "TOCMARK_<anchor id>" span right after its visible title, so the page-
# number lookup below never depends on matching visible prose (fragile:
# HTML entities like &mdash;/&ensp; don't round-trip losslessly through
# PDF text extraction, and words like "Stability" also appear in body
# text) - the marker is unique and unambiguous by construction.
_TOC_SECTIONS = [
    ("sec-1", "1  General information and set-up"),
    ("sec-2", "2  Vehicle configuration and mass properties"),
    ("sec-3", "3  Propulsion"),
    ("sec-4", "4  Trajectory — nominal and ballistic cases"),
    ("sec-5", "5  Aerodynamics"),
    ("sec-6", "6  Stability"),
    ("sec-7", "7  Recovery and landing footprint"),
    ("sec-8", "8  Flight cases (RCSM)"),
    ("sec-9", "9  Monte Carlo dispersion"),
    ("sec-10", "10  Global min-max table"),
    ("sec-11", "11  Discussion and conclusions"),
    ("sec-appA", "Appendix A — Input data"),
]
_TOC_APPENDIX_B = ("sec-appB", "Appendix B — Model validation")
_TOC_APPENDIX_C = ("sec-appC", "Appendix C — RCSM compliance")


def _b64img(path):
    if not path or not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _jinja_env():
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATE_DIR), autoescape=True)
    env.filters["b64img"] = _b64img
    return env


def _fig_number_by_path(data):
    """Walks the figures in the EXACT order the template displays them
    and assigns sequential numbers - the template looks each one up by
    its own file path instead of the template re-deriving the same
    order with fragile index arithmetic."""
    ordered_paths = [
        data["vehicle"]["side_profile_path"],
        data["vehicle"]["mass_plot_path"],
        data["propulsion"]["thrust_plot_path"],
    ]
    ordered_paths += [p for _, _, p in data["trajectory_plots"]]
    ordered_paths.append(data["aero"]["cd_plot_path"])
    ordered_paths += [p for _, _, p in data["aero"]["extra_plots"]]
    margin_path = next((p for k, t, p in data["stability_plots"] if k == "static_margin"), None)
    ordered_paths.append(margin_path)
    ordered_paths += [p for k, t, p in data["stability_plots"] if k != "static_margin"]
    ordered_paths.append(data["recovery"]["descent_plot_path"])
    ordered_paths.append(data["cases"]["altitude_overlay_path"])
    if data["monte_carlo"]:
        ordered_paths.append(data["monte_carlo"]["histogram_path"])
        ordered_paths.append(data["monte_carlo"]["ellipse_path"])

    numbers = {}
    n = 0
    for p in ordered_paths:
        if not p or p in numbers:
            continue
        n += 1
        numbers[p] = n
    return numbers


def _validation_lines(data):
    if not data.get("validation"):
        return []
    return report_module._validation_paragraphs(data["validation"])


def _toc_sections_for(data):
    sections = list(_TOC_SECTIONS)
    if data.get("validation"):
        sections.append(_TOC_APPENDIX_B)
    if data.get("compliance_rows"):
        sections.append(_TOC_APPENDIX_C)
    return sections


def _render_html(data, toc_pages):
    """toc_pages: {anchor_id: page_number_or_placeholder_string}."""
    env = _jinja_env()
    template = env.get_template("report.html")
    prose = {
        "deliverables": report_module._prose_deliverables(data),
        "vehicle": report_module._prose_vehicle(data, "{fig}"),
        "propulsion": report_module._prose_propulsion(data, "{fig}"),
        "trajectory": report_module._prose_trajectory(data, "{fig}"),
        "aero": report_module._prose_aero(data, "{fig}"),
        "stability": report_module._prose_stability(data, "{fig}"),
        "recovery": report_module._prose_recovery(data, "{fig}"),
        "monte_carlo": report_module._prose_monte_carlo(data),
    }
    fig_number_by_path = _fig_number_by_path(data)
    # The prose functions above cite "Figure {fig}" with a real number at
    # call time normally (PDF/DOCX built their own counters as they went) -
    # here figure numbers are resolved from the SAME fig_number_by_path
    # map the images themselves use, so prose and captions can never disagree.
    for key, lookup_path in [
        ("vehicle", data["vehicle"]["side_profile_path"]),
        ("propulsion", data["propulsion"]["thrust_plot_path"]),
        ("trajectory", data["trajectory_plots"][0][2] if data["trajectory_plots"] else None),
        ("aero", data["aero"]["cd_plot_path"]),
        ("recovery", data["recovery"]["descent_plot_path"]),
    ]:
        n = fig_number_by_path.get(lookup_path, "?")
        prose[key] = prose[key].replace("{fig}", str(n))
    margin_path = next((p for k, t, p in data["stability_plots"] if k == "static_margin"), None)
    prose["stability"] = prose["stability"].replace("{fig}", str(fig_number_by_path.get(margin_path, "?")))

    toc = [(title, toc_pages.get(anchor_id, "...")) for anchor_id, title in _toc_sections_for(data)]

    return template.render(
        data=data,
        prose=prose,
        fig_captions={"vehicle": "Vehicle side profile with center of gravity and center of pressure marked."},
        fig_number_by_path=fig_number_by_path,
        toc=toc,
        validation_lines=_validation_lines(data),
        WINE=report_module.WINE, GOLD=report_module.GOLD, INK=report_module.INK, LIGHT_GREY=report_module.LIGHT_GREY,
        MUTED="#6B6259", BORDER="rgba(33,26,22,0.16)",
        SUCCESS="#2C7730", ERROR="#B3261E", WARNING="#955900",
    )


def _footer_template(data):
    left = f"Beyond UP &middot; Mission {data['mission_id']} &middot; {data['vehicle_name']} &middot; Computational Simulation Report"
    return f"""
    <div style="font-size:7.5pt; width:100%; padding:0 16mm; display:flex; justify-content:space-between; color:#6B6259; font-family: Helvetica, Arial, sans-serif;">
      <span>{left}</span>
      <span><span class="pageNumber"></span> / <span class="totalPages"></span></span>
    </div>
    """


def _print_pdf(html, data, output_path):
    from playwright.sync_api import sync_playwright

    tmp_html_path = output_path + ".tmp.html"
    with open(tmp_html_path, "w", encoding="utf-8") as f:
        f.write(html)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROMIUM_PATH)
            page = browser.new_page()
            page.goto("file://" + os.path.abspath(tmp_html_path), wait_until="networkidle")
            page.pdf(
                path=output_path,
                format="A4",
                print_background=True,
                display_header_footer=True,
                header_template="<div></div>",
                footer_template=_footer_template(data),
                margin={"top": "10mm", "bottom": "14mm", "left": "0mm", "right": "0mm"},
            )
            browser.close()
    finally:
        try:
            os.remove(tmp_html_path)
        except OSError:
            pass


def _find_toc_page_numbers(pdf_path, sections):
    """Reads the just-rendered PDF back and finds which page each
    section's own invisible TOCMARK_<anchor id> span landed on - the
    real mechanism behind the "TOC with page numbers" the mega-prompt
    asked for, since Chromium's print pipeline has no native cross-
    reference/TOC support to hook into."""
    import pypdf

    reader = pypdf.PdfReader(pdf_path)
    pages_text = [page.extract_text() or "" for page in reader.pages]
    result = {}
    for anchor_id, _title in sections:
        marker = f"TOCMARK_{anchor_id}"
        for i, text in enumerate(pages_text):
            if marker in text:
                result[anchor_id] = i + 1  # 1-indexed, human page numbers
                break
    return result


def render_pdf(output_path, data):
    """Two-pass render - see module docstring. Returns output_path."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    sections = _toc_sections_for(data)
    placeholder_pages = {anchor_id: "..." for anchor_id, _ in sections}

    pass1_html = _render_html(data, placeholder_pages)
    pass1_path = output_path + ".pass1.pdf"
    _print_pdf(pass1_html, data, pass1_path)
    try:
        real_pages = _find_toc_page_numbers(pass1_path, sections)
    finally:
        try:
            os.remove(pass1_path)
        except OSError:
            pass

    pass2_html = _render_html(data, real_pages)
    _print_pdf(pass2_html, data, output_path)
    return output_path


def render_html_debug(output_path, data):
    """Saves the rendered HTML (pass 2, with real TOC numbers already
    resolved from a throwaway pass-1 render) to a file for inspection -
    not used by the app itself, only for development/debugging."""
    sections = _toc_sections_for(data)
    placeholder_pages = {anchor_id: "..." for anchor_id, _ in sections}
    pass1_html = _render_html(data, placeholder_pages)
    tmp_pdf = output_path + ".probe.pdf"
    _print_pdf(pass1_html, data, tmp_pdf)
    try:
        real_pages = _find_toc_page_numbers(tmp_pdf, sections)
    finally:
        try:
            os.remove(tmp_pdf)
        except OSError:
            pass
    html = _render_html(data, real_pages)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path
