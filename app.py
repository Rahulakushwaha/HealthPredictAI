import streamlit as st
import pandas as pd
from datetime import date
from database import *
from validation import validate_patient
from ai_engine import generate_health_remarks, api_is_configured
import html as _html
import re as _re
from urllib.parse import quote as _quote
import altair as alt
import streamlit.components.v1 as components

st.set_page_config(page_title="HealthPredict AI", page_icon="🩺", layout="wide", initial_sidebar_state="expanded")
init_db()

# =====================================================================
#  Helpers (presentation only — no business logic lives here)
# =====================================================================
PAGES = ["Dashboard", "Add Patient", "Patient Records", "AI Health Remarks", "Test Data & Validation"]
NAV_ICONS = ["grid", "user_plus", "file", "spark", "check"]

_I = {
    "grid": "<rect x='3' y='3' width='7' height='9' rx='1.5'/><rect x='14' y='3' width='7' height='5' rx='1.5'/><rect x='14' y='12' width='7' height='9' rx='1.5'/><rect x='3' y='16' width='7' height='5' rx='1.5'/>",
    "user_plus": "<path d='M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2'/><circle cx='9' cy='7' r='4'/><line x1='19' y1='8' x2='19' y2='14'/><line x1='22' y1='11' x2='16' y2='11'/>",
    "file": "<path d='M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z'/><polyline points='14 2 14 8 20 8'/><line x1='16' y1='13' x2='8' y2='13'/><line x1='16' y1='17' x2='8' y2='17'/>",
    "spark": "<path d='M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z'/><path d='M19 16l.7 1.8L21.5 18.5l-1.8.7L19 21l-.7-1.8-1.8-.7 1.8-.7z'/>",
    "check": "<path d='M22 11.08V12a10 10 0 1 1-5.93-9.14'/><polyline points='22 4 12 14.01 9 11.01'/>",
    "users": "<path d='M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2'/><circle cx='9' cy='7' r='4'/><path d='M23 21v-2a4 4 0 0 0-3-3.87'/><path d='M16 3.13a4 4 0 0 1 0 7.75'/>",
    "alert": "<path d='M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z'/><line x1='12' y1='9' x2='12' y2='13'/><line x1='12' y1='17' x2='12.01' y2='17'/>",
    "cpu": "<rect x='4' y='4' width='16' height='16' rx='2'/><rect x='9' y='9' width='6' height='6'/><path d='M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3'/>",
    "db": "<ellipse cx='12' cy='5' rx='9' ry='3'/><path d='M21 12c0 1.66-4 3-9 3s-9-1.34-9-3'/><path d='M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5'/>",
    "pulse": "<polyline points='22 12 18 12 15 21 9 3 6 12 2 12'/>",
}


def svg_icon(name, size=22, color="currentColor", sw=2):
    return (f"<svg width='{size}' height='{size}' viewBox='0 0 24 24' fill='none' stroke='{color}' "
            f"stroke-width='{sw}' stroke-linecap='round' stroke-linejoin='round'>{_I[name]}</svg>")


def icon_mask(name):
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
           "stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>" + _I[name] + "</svg>")
    return 'url("data:image/svg+xml;charset=utf-8,' + _quote(svg) + '")'


def esc(v):
    return _html.escape("" if v is None else str(v))


def flat(s):
    """Collapse a multi-line HTML template into one line (Markdown treats blank/indented lines as code)."""
    return "".join(line.strip() for line in s.strip().splitlines())


def fmt_num(v):
    try:
        f = float(v)
        return str(int(f)) if f.is_integer() else f"{f:.2f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return esc(v)


def initials(name):
    parts = str(name or "").split()
    if len(parts) > 1:
        return (parts[0][0] + parts[-1][0]).upper()
    return (parts[0][:2].upper() if parts else "•")


def ecg_path(periods):
    """A repeating PQRST heartbeat; every period is 200 units wide and the trace is seamless."""
    d = "M0,44 "
    for i in range(periods):
        o = i * 200
        d += (f"L{o+40},44 C{o+46},44 {o+48},36 {o+54},36 C{o+60},36 {o+62},44 {o+68},44 "
              f"L{o+86},44 L{o+94},50 L{o+104},6 L{o+116},76 L{o+124},44 L{o+140},44 "
              f"C{o+150},44 {o+154},28 {o+168},28 C{o+182},28 {o+186},44 {o+196},44 L{o+200},44 ")
    return d.strip()


def md_to_html(text):
    """Escape AI remarks and render the few Markdown features Gemini commonly uses."""
    out, in_list = [], False
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line:
            if in_list:
                out.append("</ul>")
                in_list = False
            continue
        bullet = _re.match(r"^(?:[-*•]|\d+[.)])\s+(.*)$", line)
        heading = _re.match(r"^#{1,6}\s+(.*)$", line)
        body = bullet.group(1) if bullet else (heading.group(1) if heading else line)
        body = esc(body)
        body = _re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", body)
        body = _re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<em>\1</em>", body)
        if bullet:
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{body}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        out.append(f"<h4>{body}</h4>" if heading else f"<p>{body}</p>")
    if in_list:
        out.append("</ul>")
    return "".join(out)


# =====================================================================
#  Visual system
# =====================================================================
BASE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=DM+Sans:wght@400;500;600;700;800&display=swap');
:root{
  --navy:#172554; --navy2:#1e3a8a; --mint:#F1F6F4; --teal:#0F9D8A; --teal-d:#0b7a6b;
  --blue:#2563EB; --purple:#7C3AED; --ink:#0f172a; --body:#1e293b; --muted:#475569;
  --line:#dfe9e5; --card:#ffffff;
  --shadow:0 12px 32px -14px rgba(23,37,84,.22),0 2px 6px rgba(23,37,84,.05);
  --shadow-h:0 22px 44px -16px rgba(23,37,84,.30),0 4px 10px rgba(23,37,84,.06);
}
html, body, [class*="css"], .stApp { font-family:'Inter','DM Sans',system-ui,-apple-system,'Segoe UI',sans-serif; }
.stApp { background:var(--mint); background-image:radial-gradient(900px 420px at 88% -8%, rgba(15,157,138,.10), transparent 70%), radial-gradient(700px 380px at -5% 105%, rgba(37,99,235,.06), transparent 70%); color:var(--ink); }
.block-container { max-width:1560px; padding-top:1.35rem; padding-bottom:3.5rem; padding-left:2rem; padding-right:2rem; }
[data-testid="stHeader"] { background:transparent; }
footer { visibility:hidden; }
h1,h2,h3,h4 { font-family:'DM Sans','Inter',sans-serif !important; color:var(--ink) !important; letter-spacing:-.4px; }
h1 { font-size:2rem !important; font-weight:800 !important; }
h2 { font-size:1.4rem !important; font-weight:800 !important; }
h3 { font-size:1.12rem !important; font-weight:700 !important; }
h4 { font-size:1.12rem !important; font-weight:800 !important; margin-top:.2rem !important; }
p, li { font-size:15px; line-height:1.65; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color:var(--muted) !important; font-size:14px !important; line-height:1.55 !important; }

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] { background:linear-gradient(185deg,#172554 0%,#13204a 60%,#0f1a3d 100%); border-right:0; box-shadow:6px 0 30px -10px rgba(23,37,84,.45); }
[data-testid="stSidebar"] > div:first-child { padding-top:1.1rem; }
[data-testid="stSidebar"] * { color:#e6edff; }
[data-testid="stSidebarCollapseButton"] button svg, [data-testid="stSidebar"] button svg { color:#ffffff; fill:#ffffff; }
.hp-brand { display:flex; align-items:center; gap:12px; padding:8px 8px 22px; }
.hp-logo { width:46px; height:46px; border-radius:14px; background:linear-gradient(135deg,#14b8a6,#0F9D8A 55%,#0e7490); display:flex; align-items:center; justify-content:center; box-shadow:0 8px 22px rgba(20,184,166,.45), inset 0 1px 0 rgba(255,255,255,.35); }
.hp-brand-title { font-family:'DM Sans',sans-serif; font-weight:800; font-size:19px; color:#ffffff !important; line-height:1.1; letter-spacing:-.3px; }
.hp-brand-sub { font-size:10.5px; letter-spacing:2px; color:#8fe9db !important; font-weight:700; margin-top:5px; }
.hp-side-label { font-size:11px; letter-spacing:1.8px; font-weight:700; color:#9db0dd !important; text-transform:uppercase; padding:6px 10px 8px; }
[data-testid="stSidebar"] div[data-testid="stRadio"] > label { display:none; }
[data-testid="stSidebar"] div[role="radiogroup"] { gap:6px; }
[data-testid="stSidebar"] div[role="radiogroup"] > label { display:flex; align-items:center; gap:13px; padding:13px 14px; border-radius:14px; border:1px solid transparent; background:transparent; cursor:pointer; transition:background .18s ease, transform .18s ease, border-color .18s ease; width:100%; }
[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child { display:none; }
[data-testid="stSidebar"] div[role="radiogroup"] > label::before { content:""; flex:0 0 22px; width:22px; height:22px; background-color:#ffffff; -webkit-mask-repeat:no-repeat; mask-repeat:no-repeat; -webkit-mask-position:center; mask-position:center; -webkit-mask-size:contain; mask-size:contain; opacity:.92; }
[data-testid="stSidebar"] div[role="radiogroup"] > label p { color:#e6edff !important; font-size:16px !important; font-weight:600; margin:0; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:hover { background:rgba(255,255,255,.08); transform:translateX(3px); }
[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) { background:linear-gradient(90deg,rgba(45,212,191,.22),rgba(255,255,255,.07)); border-color:rgba(94,234,212,.35); box-shadow:inset 4px 0 0 #2dd4bf, 0 8px 20px -10px rgba(0,0,0,.5); }
[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) p { color:#ffffff !important; font-weight:700; }
.hp-side-status { background:rgba(255,255,255,.07); border:1px solid rgba(255,255,255,.14); border-radius:16px; padding:15px 16px; font-size:13px; line-height:1.55; color:#d9e4ff; }
.hp-side-status b { color:#ffffff; font-size:14px; }
.hp-dot { display:inline-block; width:9px; height:9px; border-radius:50%; background:#fbbf24; margin-right:8px; box-shadow:0 0 0 0 rgba(251,191,36,.6); animation:hpPing 2s infinite; }
.hp-dot.ok { background:#34d399; box-shadow:0 0 0 0 rgba(52,211,153,.6); }
@keyframes hpPing { 70%{box-shadow:0 0 0 8px rgba(52,211,153,0);} 100%{box-shadow:0 0 0 0 rgba(52,211,153,0);} }

/* ---------- Hero (inner pages) ---------- */
.hp-hero { position:relative; overflow:hidden; background:linear-gradient(115deg,#172554 0%,#123c6e 55%,#0d8579 130%); border-radius:24px; padding:32px 38px; margin:0 0 28px; box-shadow:0 22px 44px -18px rgba(23,37,84,.55); }
.hp-hero::before { content:""; position:absolute; right:-80px; top:-120px; width:420px; height:420px; border-radius:50%; background:radial-gradient(circle,rgba(34,211,238,.32),transparent 65%); }
.hp-hero::after { content:""; position:absolute; inset:0; background-image:linear-gradient(rgba(255,255,255,.04) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.04) 1px,transparent 1px); background-size:28px 28px; -webkit-mask-image:linear-gradient(90deg,transparent,#000 70%); mask-image:linear-gradient(90deg,transparent,#000 70%); pointer-events:none; }
.hp-hero-text { position:relative; z-index:2; max-width:62%; }
.hp-eyebrow { text-transform:uppercase; letter-spacing:2px; font-size:12px; font-weight:700; color:#8fe9db !important; margin-bottom:10px; }
.hp-hero h1 { color:#ffffff !important; margin:0 0 8px; font-size:31px !important; line-height:1.15; }
.hp-hero p { color:#d6e6f7 !important; margin:0; font-size:16px; line-height:1.6; }
.hp-hero-ecg { position:absolute; right:0; bottom:12px; width:44%; height:62px; z-index:1; -webkit-mask-image:linear-gradient(90deg,transparent,#000 22%,#000 82%,transparent); mask-image:linear-gradient(90deg,transparent,#000 22%,#000 82%,transparent); }
.hp-hero-ecg svg { width:200%; height:100%; display:block; animation:hpEcg 8s linear infinite; filter:drop-shadow(0 0 5px rgba(45,212,191,.9)); }
.hp-hero-ecg path { fill:none; stroke:#5eead4; stroke-width:2.4; vector-effect:non-scaling-stroke; stroke-linejoin:round; }
@keyframes hpEcg { from{transform:translateX(0);} to{transform:translateX(-50%);} }
@media (max-width:900px){ .hp-hero-text{max-width:100%;} .hp-hero-ecg{display:none;} }

/* ---------- Section headings ---------- */
.hp-section { display:flex; align-items:flex-end; justify-content:space-between; gap:12px; margin:30px 0 14px; }
.hp-section-title { font-family:'DM Sans',sans-serif; font-weight:800; font-size:20px; color:var(--ink); display:flex; align-items:center; gap:10px; letter-spacing:-.3px; }
.hp-section-title::before { content:""; width:5px; height:22px; border-radius:4px; background:linear-gradient(180deg,#14b8a6,#2563EB); display:inline-block; }
.hp-section-note { color:var(--muted); font-size:13.5px; font-weight:500; }

/* ---------- Cards ---------- */
.hp-card { background:var(--card); border:1px solid var(--line); border-radius:20px; padding:22px 24px; box-shadow:var(--shadow); transition:transform .22s ease, box-shadow .22s ease; color:var(--body); }
.hp-card:hover { box-shadow:var(--shadow-h); }
.hp-card h3 { margin:12px 0 8px; }
.hp-card p { color:var(--body); font-size:15px; line-height:1.7; margin:0; }
.hp-card-label { font-size:12px; color:var(--teal-d); font-weight:800; text-transform:uppercase; letter-spacing:1.4px; }
.hp-note { background:#ffffff; border:1px solid #cfe9e3; border-left:5px solid var(--teal); border-radius:16px; padding:18px 22px; color:var(--body); font-size:15.5px; line-height:1.7; box-shadow:var(--shadow); margin-bottom:18px; }
.hp-note b { color:var(--ink); }

/* KPI cards */
.hp-kpi { position:relative; overflow:hidden; background:var(--card); border:1px solid var(--line); border-radius:22px; padding:22px 24px 20px; box-shadow:var(--shadow); transition:transform .25s ease, box-shadow .25s ease; min-height:176px; }
.hp-kpi::after { content:""; position:absolute; right:-46px; top:-46px; width:150px; height:150px; border-radius:50%; background:radial-gradient(circle,rgba(15,157,138,.13),transparent 68%); }
.hp-kpi:hover { transform:translateY(-5px); box-shadow:var(--shadow-h); }
.hp-kpi .ic { width:52px; height:52px; border-radius:16px; display:flex; align-items:center; justify-content:center; margin-bottom:16px; position:relative; z-index:1; }
.ic.teal { background:linear-gradient(135deg,#2dd4bf,#0F9D8A); box-shadow:0 10px 22px -6px rgba(15,157,138,.6); }
.ic.blue { background:linear-gradient(135deg,#60a5fa,#2563EB); box-shadow:0 10px 22px -6px rgba(37,99,235,.55); }
.ic.purple { background:linear-gradient(135deg,#a78bfa,#7C3AED); box-shadow:0 10px 22px -6px rgba(124,58,237,.55); }
.ic.navy { background:linear-gradient(135deg,#3b5bdb,#172554); box-shadow:0 10px 22px -6px rgba(23,37,84,.6); }
.hp-kpi-label { font-size:13.5px; color:var(--muted); font-weight:700; text-transform:uppercase; letter-spacing:1.1px; position:relative; z-index:1; }
.hp-kpi-value { font-family:'DM Sans',sans-serif; font-size:36px; font-weight:800; color:var(--ink); margin-top:4px; line-height:1.15; letter-spacing:-1px; position:relative; z-index:1; }
.hp-kpi-value.sm { font-size:28px; padding-top:5px; }
.hp-kpi-foot { font-size:14px; color:var(--muted); margin-top:6px; position:relative; z-index:1; }

/* Statistics card */
.hp-stat-row { margin-top:20px; }
.hp-stat-top { display:flex; align-items:center; gap:10px; font-size:15px; color:var(--ink); }
.hp-stat-top b { font-weight:700; }
.hp-stat-top .avg { margin-left:auto; font-family:'DM Sans',sans-serif; font-size:20px; font-weight:800; }
.hp-swatch { width:11px; height:11px; border-radius:4px; display:inline-block; }
.hp-bar { height:9px; border-radius:99px; background:#e8efec; margin:9px 0 7px; overflow:hidden; }
.hp-bar i { display:block; height:100%; border-radius:99px; }
.hp-stat-sub { font-size:13.5px; color:var(--muted); }

/* Recent activity table */
.hp-table-wrap { background:var(--card); border:1px solid var(--line); border-radius:22px; box-shadow:var(--shadow); overflow-x:auto; }
.hp-table { width:100%; border-collapse:collapse; font-size:15px; min-width:760px; }
.hp-table th { background:#f4f9f7; text-align:left; font-size:13px; letter-spacing:1px; text-transform:uppercase; color:var(--muted); font-weight:700; padding:16px 22px; border-bottom:1px solid var(--line); white-space:nowrap; }
.hp-table td { padding:17px 22px; border-bottom:1px solid #edf3f1; color:var(--ink); vertical-align:middle; transition:background .15s ease; }
.hp-table tr:last-child td { border-bottom:0; }
.hp-table tbody tr:hover td { background:#f1faf7; }
.hp-who { display:flex; align-items:center; gap:13px; }
.hp-avatar { width:42px; height:42px; flex:0 0 42px; border-radius:13px; background:linear-gradient(135deg,#0F9D8A,#2563EB); color:#ffffff; font-weight:800; font-size:14px; display:inline-flex; align-items:center; justify-content:center; box-shadow:0 8px 16px -8px rgba(15,157,138,.7); }
.hp-avatar.lg { width:56px; height:56px; flex-basis:56px; border-radius:17px; font-size:18px; }
.hp-who b { display:block; font-weight:700; font-size:15px; color:var(--ink); }
.hp-who span { font-size:12.5px; color:var(--muted); }
.hp-pill { display:inline-block; padding:5px 13px; border-radius:99px; font-weight:700; font-size:13.5px; }
.hp-pill.g { background:#dbe8ff; color:#1e40af; }
.hp-pill.h { background:#d3f4ec; color:#0a5f53; }
.hp-pill.c { background:#eadfff; color:#5b21b6; }
.hp-muted { color:var(--muted); }

/* Patient identity / remarks */
.hp-patient { display:flex; align-items:center; gap:16px; background:var(--card); border:1px solid var(--line); border-radius:20px; padding:18px 22px; box-shadow:var(--shadow); margin:6px 0 18px; }
.hp-patient .nm { font-family:'DM Sans',sans-serif; font-size:21px; font-weight:800; color:var(--ink); }
.hp-patient .sub { font-size:14px; color:var(--muted); margin-top:3px; }
.hp-remarks { background:var(--card); border:1px solid var(--line); border-radius:22px; box-shadow:var(--shadow); overflow:hidden; }
.hp-remarks-head { display:flex; align-items:center; gap:10px; padding:14px 26px; background:linear-gradient(90deg,#e6f6f2,#eef3ff); color:#0b5e53; font-weight:700; font-size:13.5px; letter-spacing:.3px; border-bottom:1px solid var(--line); }
.hp-remarks-body { padding:22px 28px 26px; color:var(--body); font-size:16.5px; line-height:1.85; }
.hp-remarks-body p { margin:0 0 12px; font-size:16.5px; line-height:1.85; }
.hp-remarks-body ul { margin:0 0 12px 4px; padding-left:20px; }
.hp-remarks-body li { margin-bottom:7px; font-size:16.5px; line-height:1.8; }
.hp-remarks-body h4 { margin:14px 0 6px; font-size:17px !important; }

/* ---------- Charts ---------- */
div[data-testid="stVegaLiteChart"], div[data-testid="stArrowVegaLiteChart"], div[data-testid="stAltairChart"] { background:#ffffff; border:1px solid var(--line); border-radius:20px; padding:14px 12px 8px; box-shadow:var(--shadow); overflow:hidden; }

/* ---------- Forms & inputs ---------- */
div[data-testid="stForm"] { background:var(--card); border:1px solid var(--line); border-radius:24px; padding:30px 34px 26px; box-shadow:var(--shadow); }
[data-testid="stWidgetLabel"] p, label[data-testid="stWidgetLabel"] { font-size:14.5px !important; font-weight:600 !important; color:var(--ink) !important; }
div[data-baseweb="input"], div[data-baseweb="base-input"], div[data-baseweb="select"] > div { border-radius:13px !important; background:#fbfdfc !important; border:1.5px solid #cbd8d3 !important; transition:border-color .18s ease, box-shadow .18s ease, background .18s ease; }
div[data-baseweb="input"]:hover, div[data-baseweb="select"] > div:hover { border-color:#8fc9bf !important; }
div[data-baseweb="input"]:focus-within, div[data-baseweb="select"] > div:focus-within { border-color:var(--teal) !important; box-shadow:0 0 0 4px rgba(15,157,138,.16) !important; background:#ffffff !important; }
div[data-baseweb="input"] input { font-size:15.5px !important; color:var(--ink) !important; padding-top:11px !important; padding-bottom:11px !important; background:transparent !important; }
div[data-baseweb="input"] input::placeholder { color:#7a8a99 !important; }
div[data-baseweb="select"] div { font-size:15.5px; color:var(--ink); }
div[data-testid="stForm"] hr { border-color:var(--line); margin:1.2rem 0; }

/* Buttons */
.stButton > button, .stDownloadButton > button, div[data-testid="stFormSubmitButton"] > button { border-radius:13px !important; font-weight:700 !important; font-size:15px !important; padding:.65rem 1.25rem !important; border:1.5px solid #c5d6d0 !important; background:#ffffff !important; color:var(--navy) !important; transition:all .2s ease !important; box-shadow:0 2px 6px rgba(23,37,84,.05); }
.stButton > button p, .stDownloadButton > button p, div[data-testid="stFormSubmitButton"] > button p { color:inherit !important; font-weight:700; font-size:15px; }
.stButton > button:hover, .stDownloadButton > button:hover, div[data-testid="stFormSubmitButton"] > button:hover { transform:translateY(-2px); border-color:var(--teal) !important; color:var(--teal-d) !important; box-shadow:0 12px 22px -10px rgba(15,157,138,.45); }
button[kind="primary"], button[kind="primaryFormSubmit"], button[data-testid="stBaseButton-primary"], button[data-testid="stBaseButton-primaryFormSubmit"] { background:linear-gradient(135deg,#0e9482,#0a7466) !important; color:#ffffff !important; border:0 !important; box-shadow:0 12px 24px -10px rgba(15,157,138,.65) !important; }
button[kind="primary"] p, button[kind="primaryFormSubmit"] p, button[data-testid="stBaseButton-primary"] p, button[data-testid="stBaseButton-primaryFormSubmit"] p { color:#ffffff !important; }
button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover, button[data-testid="stBaseButton-primary"]:hover, button[data-testid="stBaseButton-primaryFormSubmit"]:hover { background:linear-gradient(135deg,#10a591,#0b8272) !important; color:#ffffff !important; box-shadow:0 16px 30px -10px rgba(15,157,138,.8) !important; }
.stButton > button:disabled, .stDownloadButton > button:disabled { opacity:.5; transform:none; box-shadow:none; }

/* Pill-style horizontal radio (main area) */
.stApp section.main div[data-testid="stRadio"] div[role="radiogroup"], [data-testid="stMain"] div[data-testid="stRadio"] div[role="radiogroup"] { gap:8px; flex-wrap:wrap; }
[data-testid="stMain"] div[role="radiogroup"] > label, .stApp section.main div[role="radiogroup"] > label { padding:8px 18px; border-radius:99px; border:1.5px solid #c5d6d0; background:#ffffff; cursor:pointer; transition:all .18s ease; margin:0; }
[data-testid="stMain"] div[role="radiogroup"] > label > div:first-child, .stApp section.main div[role="radiogroup"] > label > div:first-child { display:none; }
[data-testid="stMain"] div[role="radiogroup"] > label p, .stApp section.main div[role="radiogroup"] > label p { font-size:14.5px !important; font-weight:600; color:var(--ink) !important; margin:0; }
[data-testid="stMain"] div[role="radiogroup"] > label:hover, .stApp section.main div[role="radiogroup"] > label:hover { border-color:var(--teal); transform:translateY(-1px); }
[data-testid="stMain"] div[role="radiogroup"] > label:has(input:checked), .stApp section.main div[role="radiogroup"] > label:has(input:checked) { background:linear-gradient(135deg,#0e9482,#0a7466); border-color:transparent; box-shadow:0 10px 20px -10px rgba(15,157,138,.7); }
[data-testid="stMain"] div[role="radiogroup"] > label:has(input:checked) p, .stApp section.main div[role="radiogroup"] > label:has(input:checked) p { color:#ffffff !important; }

/* Checkbox accent */
label[data-baseweb="checkbox"]:has(input:checked) > span:first-child { background-color:var(--teal) !important; border-color:var(--teal) !important; }
label[data-baseweb="checkbox"] p { font-size:15px; color:var(--ink); }

/* Data frames, metrics, alerts, expanders */
div[data-testid="stDataFrame"] { background:#ffffff; border:1px solid var(--line); border-radius:20px; overflow:hidden; box-shadow:var(--shadow); padding:4px; }
[data-testid="stMetric"] { background:var(--card); border:1px solid var(--line); border-left:5px solid var(--teal); border-radius:18px; padding:18px 22px; box-shadow:var(--shadow); transition:transform .22s ease, box-shadow .22s ease; }
[data-testid="stMetric"]:hover { transform:translateY(-3px); box-shadow:var(--shadow-h); }
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] p { color:var(--muted) !important; font-size:12.5px !important; font-weight:700 !important; text-transform:uppercase; letter-spacing:1px; }
[data-testid="stMetricValue"] { color:var(--ink) !important; font-family:'DM Sans',sans-serif; font-weight:800; font-size:32px; }
div[data-testid="stAlert"] { border-radius:16px; font-size:15px; box-shadow:0 6px 16px -10px rgba(23,37,84,.25); }
div[data-testid="stAlert"] p { font-size:15px; }
[data-testid="stExpander"] { background:var(--card); border:1px solid var(--line) !important; border-radius:20px !important; box-shadow:var(--shadow); overflow:hidden; margin-bottom:14px; }
[data-testid="stExpander"] summary { font-weight:700; font-size:15.5px; padding:14px 20px; transition:background .18s ease; }
[data-testid="stExpander"] summary:hover { background:#f1faf7; }
[data-testid="stSpinner"] p { color:var(--ink); font-size:15px; }
hr { border-color:var(--line); }
</style>
"""


def build_css():
    nav = "".join(
        '[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-of-type(%d)::before'
        '{-webkit-mask-image:%s;mask-image:%s;}' % (i + 1, icon_mask(n), icon_mask(n))
        for i, n in enumerate(NAV_ICONS)
    )
    return BASE_CSS.replace("</style>", nav + "</style>")


st.markdown(build_css(), unsafe_allow_html=True)

# =====================================================================
#  Sidebar
# =====================================================================
with st.sidebar:
    st.markdown(flat(f"""
    <div class="hp-brand">
      <div class="hp-logo">{svg_icon('pulse', 26, '#ffffff', 2.4)}</div>
      <div><div class="hp-brand-title">HealthPredict AI</div><div class="hp-brand-sub">CARE INTELLIGENCE</div></div>
    </div>
    <div class="hp-side-label">Workspace</div>
    """), unsafe_allow_html=True)
    page = st.radio("Navigation", PAGES, label_visibility="collapsed")
    st.markdown("<div class='hp-side-label' style='margin-top:26px'>System status</div>", unsafe_allow_html=True)
    if api_is_configured():
        st.markdown("<div class='hp-side-status'><span class='hp-dot ok'></span><b>AI service connected</b><br><span style='padding-left:17px'>Gemini API is configured</span></div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='hp-side-status'><span class='hp-dot'></span><b>AI service not connected</b><br><span style='padding-left:17px'>Add your API key to enable remarks</span></div>", unsafe_allow_html=True)
    st.markdown("<div style='padding:26px 10px;color:#a5b4d4;font-size:11px;letter-spacing:1.2px;font-weight:600'>HEALTHPREDICT AI · ASSESSMENT BUILD</div>", unsafe_allow_html=True)


def hero(kicker, title, subtitle):
    track = ecg_path(10)
    st.markdown(flat(f"""
    <div class="hp-hero">
      <div class="hp-hero-ecg"><svg viewBox="0 0 2000 80" preserveAspectRatio="none"><path d="{track}"/></svg></div>
      <div class="hp-hero-text"><div class="hp-eyebrow">{esc(kicker)}</div><h1>{esc(title)}</h1><p>{esc(subtitle)}</p></div>
    </div>"""), unsafe_allow_html=True)


def section(title, note=""):
    st.markdown(f"""<div class="hp-section"><div class="hp-section-title">{title}</div><div class="hp-section-note">{note}</div></div>""", unsafe_allow_html=True)


def kpi(col, icon, tone, label, value, foot, tip="", small=False):
    cls = "hp-kpi-value sm" if small else "hp-kpi-value"
    col.markdown(flat(f"""
    <div class="hp-kpi" title="{esc(tip)}">
      <div class="ic {tone}">{svg_icon(icon, 26, '#ffffff', 2)}</div>
      <div class="hp-kpi-label">{esc(label)}</div>
      <div class="{cls}">{esc(value)}</div>
      <div class="hp-kpi-foot">{esc(foot)}</div>
    </div>"""), unsafe_allow_html=True)


# =====================================================================
#  Dashboard signature banner: glowing anatomical heart + live ECG
# =====================================================================
_BODY = ("M152 98 C128 104 84 110 66 140 L50 236 Q49 250 62 251 L76 251 Q86 250 88 238 L98 178 L98 340 "
         "L242 340 L242 178 L252 238 Q254 250 264 251 L278 251 Q291 250 290 236 L274 140 "
         "C256 110 212 104 188 98 L188 84 L152 84 Z")

_HERO_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=DM+Sans:wght@700;800&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:transparent;font-family:'Inter','DM Sans',system-ui,sans-serif}
body{padding:2px 2px 18px}
.banner{position:relative;height:352px;border-radius:28px;overflow:hidden;color:#fff;
  background:linear-gradient(115deg,#172554 0%,#10386b 52%,#0b7f7a 105%);
  box-shadow:0 26px 50px -20px rgba(23,37,84,.6)}
.orb{position:absolute;border-radius:50%;pointer-events:none}
.o1{right:-70px;top:-90px;width:480px;height:480px;background:radial-gradient(circle,rgba(34,211,238,.38),transparent 64%)}
.o2{left:-120px;bottom:-170px;width:460px;height:460px;background:radial-gradient(circle,rgba(20,184,166,.32),transparent 66%)}
.grid{position:absolute;inset:0;pointer-events:none;
  background-image:linear-gradient(rgba(255,255,255,.045) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.045) 1px,transparent 1px);
  background-size:30px 30px;-webkit-mask-image:linear-gradient(90deg,transparent 5%,#000 80%);mask-image:linear-gradient(90deg,transparent 5%,#000 80%)}
.left{position:absolute;left:46px;top:36px;width:56%;z-index:4}
.eyebrow{display:inline-flex;align-items:center;gap:10px;font-size:12.5px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#8fe9db;margin-bottom:14px}
h1{font-family:'DM Sans','Inter',sans-serif;font-weight:800;font-size:clamp(27px,3.1vw,39px);line-height:1.13;letter-spacing:-1px;color:#fff;margin-bottom:12px}
h1 span{background:linear-gradient(90deg,#5eead4,#67e8f9);-webkit-background-clip:text;background-clip:text;color:transparent}
p.sub{font-size:16px;line-height:1.6;color:#d6e8f7;max-width:520px}
.chips{margin-top:18px}
.chip{display:inline-flex;align-items:center;gap:9px;padding:8px 15px;border-radius:999px;background:rgba(255,255,255,.13);
  border:1px solid rgba(255,255,255,.3);font-size:13.5px;font-weight:600;color:#fff;margin:0 8px 8px 0;backdrop-filter:blur(6px)}
.chip b{font-size:15px;font-weight:700}
.dot{width:9px;height:9px;border-radius:50%;background:#2dd4bf;animation:ping 1.7s infinite}
.dot.warn{background:#fbbf24;animation:none}
@keyframes ping{0%{box-shadow:0 0 0 0 rgba(45,212,191,.75)}70%{box-shadow:0 0 0 9px rgba(45,212,191,0)}100%{box-shadow:0 0 0 0 rgba(45,212,191,0)}}
.ecg{position:absolute;left:0;bottom:8px;width:66%;height:58px;z-index:3;overflow:hidden;
  -webkit-mask-image:linear-gradient(90deg,transparent,#000 14%,#000 84%,transparent);mask-image:linear-gradient(90deg,transparent,#000 14%,#000 84%,transparent)}
.ecg svg{width:200%;height:100%;display:block;animation:ecgmove 5.8s linear infinite;filter:drop-shadow(0 0 6px rgba(45,212,191,.95)) drop-shadow(0 0 14px rgba(34,211,238,.6))}
.ecg path{fill:none;stroke:#5eead4;stroke-width:2.6;stroke-linejoin:round;stroke-linecap:round;vector-effect:non-scaling-stroke}
@keyframes ecgmove{from{transform:translateX(0)}to{transform:translateX(-50%)}}
.figure{position:absolute;right:18px;top:0;width:356px;height:356px;z-index:2}
.figure svg{width:100%;height:100%;overflow:visible}
.ring{transform-box:fill-box;transform-origin:center;animation:spin 46s linear infinite}
.ring2{animation-duration:70s;animation-direction:reverse}
@keyframes spin{to{transform:rotate(360deg)}}
.bodyg{filter:drop-shadow(0 0 9px rgba(34,211,238,.6))}
.scan{animation:scan 4.6s ease-in-out infinite}
@keyframes scan{0%{transform:translateY(10px);opacity:0}12%{opacity:1}88%{opacity:1}100%{transform:translateY(310px);opacity:0}}
.glow{transform-box:fill-box;transform-origin:center;animation:glowp 1.3s ease-in-out infinite}
@keyframes glowp{0%,100%{opacity:.55;transform:scale(.9)}12%{opacity:1;transform:scale(1.18)}30%{opacity:.7;transform:scale(1)}38%{opacity:.95;transform:scale(1.1)}60%{opacity:.6;transform:scale(.93)}}
.beat{transform-box:fill-box;transform-origin:center;animation:beat 1.3s ease-in-out infinite;filter:drop-shadow(0 0 9px rgba(34,211,238,1)) drop-shadow(0 0 22px rgba(244,63,94,.7))
@keyframes beat{0%,100%{transform:scale(1)}10%{transform:scale(1.13)}22%{transform:scale(1)}34%{transform:scale(1.08)}48%{transform:scale(1)}60%{transform:scale(1)}}
.fl{animation:float 6s ease-in-out infinite}
.fl2{animation-duration:8s;animation-delay:-3s}
@keyframes float{0%,100%{transform:translateY(0);opacity:.35}50%{transform:translateY(-14px);opacity:.95}}
@media (max-width:900px){.figure{display:none}.left{width:calc(100% - 60px)}.ecg{width:100%}} @media (max-width:700px){.block-container{padding-left:1rem;padding-right:1rem;padding-top:1rem}.hp-kpi{padding:18px;min-height:160px}.hp-kpi-value{font-size:30px}.hp-hero{padding:26px 24px}.hp-hero-text{max-width:100%}}
</style></head><body>
<div class="banner">
  <div class="orb o1"></div><div class="orb o2"></div><div class="grid"></div>
  <div class="left">
    <div class="eyebrow"><span class="dot"></span>Welcome to HealthPredict AI</div>
    <h1>Good health starts with <span>better information.</span></h1>
    <p class="sub">A central workspace to manage patient records and review blood-test information.</p>
    <div class="chips">
      <span class="chip"><b>__N__</b> patient records</span>
      <span class="chip"><span class="dot __AIDOT__"></span>AI service: __AI__</span>
      <span class="chip"><span class="dot"></span>Live ECG</span>
    </div>
  </div>
  <div class="ecg"><svg viewBox="0 0 2400 80" preserveAspectRatio="none"><path d="__ECG__"/></svg></div>
  <div class="figure">
    <svg viewBox="0 0 340 340" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="bodyFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#22d3ee" stop-opacity=".34"/><stop offset="1" stop-color="#0F9D8A" stop-opacity=".08"/></linearGradient>
        <linearGradient id="bodyStroke" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#a5f3fc"/><stop offset="1" stop-color="#2dd4bf"/></linearGradient>
        <linearGradient id="fadeG" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff"/><stop offset=".74" stop-color="#fff"/><stop offset="1" stop-color="#000"/></linearGradient>
        <mask id="fade"><rect width="340" height="340" fill="url(#fadeG)"/></mask>
        <linearGradient id="scanG" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#67e8f9" stop-opacity="0"/><stop offset=".85" stop-color="#67e8f9" stop-opacity=".45"/><stop offset="1" stop-color="#e0fcff" stop-opacity=".95"/></linearGradient>
        <radialGradient id="glowG"><stop offset="0" stop-color="#67e8f9" stop-opacity=".85"/><stop offset=".4" stop-color="#22d3ee" stop-opacity=".38"/><stop offset="1" stop-color="#0F9D8A" stop-opacity="0"/></radialGradient>
        <radialGradient id="heartG" cx=".35" cy=".3" r=".85"><stop offset="0" stop-color="#ffa3b5"/><stop offset=".5" stop-color="#e11d48"/><stop offset="1" stop-color="#8a1034"/></radialGradient>
        <linearGradient id="aortaG" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#be123c"/><stop offset="1" stop-color="#fb7185"/></linearGradient>
        <linearGradient id="veinG" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#1d4ed8"/><stop offset="1" stop-color="#60a5fa"/></linearGradient>
        <clipPath id="bodyClip"><path d="__BODY__"/><ellipse cx="170" cy="52" rx="27" ry="33"/></clipPath>
      </defs>

      <circle class="ring" cx="170" cy="188" r="158" fill="none" stroke="rgba(103,232,249,.32)" stroke-width="1.2" stroke-dasharray="2 9" stroke-linecap="round"/>
      <circle class="ring ring2" cx="170" cy="188" r="128" fill="none" stroke="rgba(94,234,212,.28)" stroke-width="1.2" stroke-dasharray="26 12"/>

      <g mask="url(#fade)"><g class="bodyg">
        <path d="__BODY__" fill="url(#bodyFill)" stroke="url(#bodyStroke)" stroke-width="2.2" stroke-linejoin="round"/>
        <ellipse cx="170" cy="52" rx="27" ry="33" fill="url(#bodyFill)" stroke="url(#bodyStroke)" stroke-width="2.2"/>
        <g fill="none" stroke="rgba(190,248,255,.5)" stroke-width="1.8" stroke-linecap="round">
          <path d="M168 108 C150 102 128 104 108 116"/><path d="M172 108 C190 102 212 104 232 116"/>
          <path d="M170 114 L170 240"/>
          <path d="M168 130 C140 132 118 144 106 164"/><path d="M172 130 C200 132 222 144 234 164"/>
          <path d="M168 156 C142 158 122 170 112 190"/><path d="M172 156 C198 158 218 170 228 190"/>
          <path d="M168 182 C146 184 130 196 122 214"/><path d="M172 182 C194 184 210 196 218 214"/>
        </g>
        <g clip-path="url(#bodyClip)"><rect class="scan" x="40" y="0" width="260" height="46" fill="url(#scanG)"/></g>
      </g></g>

      <circle class="glow" cx="184" cy="184" r="86" fill="url(#glowG)"/>

      <g transform="translate(184 184) scale(1.2)"><g class="beat">
        <path d="M-8 -28 C-12 -58 16 -66 30 -52 C38 -44 34 -32 26 -32" fill="none" stroke="url(#aortaG)" stroke-width="12" stroke-linecap="round"/>
        <path d="M4 -30 C2 -46 -20 -54 -34 -44" fill="none" stroke="url(#veinG)" stroke-width="10" stroke-linecap="round"/>
        <path d="M-24 -28 C-28 -44 -40 -58 -40 -70" fill="none" stroke="url(#veinG)" stroke-width="9" stroke-linecap="round"/>
        <path d="M0 42 C-46 10 -44 -30 -16 -34 C-6 -35 0 -28 0 -22 C0 -28 8 -36 20 -34 C46 -30 50 8 0 42 Z" fill="url(#heartG)" stroke="#8cf0ff" stroke-width="1.6"/>
        <path d="M-4 -20 C-9 0 -5 22 0 40" fill="none" stroke="rgba(80,0,25,.55)" stroke-width="2" stroke-linecap="round"/>
        <g fill="none" stroke="#ffd0da" stroke-width="1.7" stroke-linecap="round" opacity=".75">
          <path d="M-30 -14 C-24 4 -14 22 -5 34"/><path d="M30 -12 C26 6 16 22 5 34"/><path d="M-12 -28 C-16 -8 -14 8 -10 24"/>
        </g>
        <ellipse cx="-21" cy="-14" rx="8" ry="15" transform="rotate(20 -21 -14)" fill="#ffffff" opacity=".26"/>
      </g></g>

      <g fill="#a5f3fc">
        <circle class="fl" cx="40" cy="120" r="2.6"/><circle class="fl fl2" cx="306" cy="150" r="3"/>
        <circle class="fl fl2" cx="296" cy="64" r="2.2"/><circle class="fl" cx="62" cy="228" r="2.2"/>
      </g>
      <g fill="none" stroke="#5eead4" stroke-width="2.4" stroke-linecap="round">
        <path class="fl" d="M300 104 v12 M294 110 h12"/><path class="fl fl2" d="M36 168 v10 M31 173 h10"/>
      </g>
    </svg>
  </div>
</div></body></html>"""


def render_dashboard_hero(n_patients):
    ai_ok = api_is_configured()
    page_html = (_HERO_HTML
                 .replace("__BODY__", _BODY)
                 .replace("__ECG__", ecg_path(12))
                 .replace("__N__", str(int(n_patients)))
                 .replace("__AI__", "Connected" if ai_ok else "Not configured")
                 .replace("__AIDOT__", "" if ai_ok else "warn"))
    components.html(page_html, height=376)


# =====================================================================
#  Dashboard chart helpers (Altair ships with Streamlit)
# =====================================================================
MARKER_COLS = {"Glucose": "glucose", "Haemoglobin": "haemoglobin", "Cholesterol": "cholesterol"}
MARKER_COLORS = {"Glucose": "#2563EB", "Haemoglobin": "#0F9D8A", "Cholesterol": "#7C3AED"}
ALT5 = hasattr(alt, "selection_point")


def numeric_frame(df):
    d = df.copy()
    for c in MARKER_COLS.values():
        d[c] = pd.to_numeric(d[c], errors="coerce")
    return d


def themed(chart, height=330):
    return (chart.properties(height=height, background="#FFFFFF", padding={"left": 8, "right": 10, "top": 8, "bottom": 4})
            .configure_view(strokeWidth=0)
            .configure_axis(labelColor="#334155", titleColor="#334155", labelFontSize=12, titleFontSize=12.5,
                            titleFontWeight=600, gridColor="#E2E8F0", domainColor="#CBD5E1", tickColor="#CBD5E1",
                            labelFont="Inter", titleFont="Inter", titlePadding=10)
            .configure_legend(labelColor="#1E293B", titleColor="#334155", labelFontSize=13, titleFontSize=12,
                              orient="top", symbolType="circle", symbolSize=140, labelFont="Inter", padding=4))


def blood_chart(df_num, marker_choice):
    d = df_num.tail(8)
    chosen = list(MARKER_COLS) if marker_choice == "All markers" else [marker_choice]
    long = d.melt(id_vars=["full_name"], value_vars=[MARKER_COLS[m] for m in chosen], var_name="col", value_name="Value")
    inv = {v: k for k, v in MARKER_COLS.items()}
    long["Marker"] = long["col"].map(inv)
    long = long.dropna(subset=["Value"]).rename(columns={"full_name": "Patient"})
    enc = dict(
        x=alt.X("Patient:N", sort=None, axis=alt.Axis(labelAngle=-28, title=None, labelLimit=150)),
        color=alt.Color("Marker:N", scale=alt.Scale(domain=list(MARKER_COLORS), range=list(MARKER_COLORS.values())),
                        legend=alt.Legend(title=None)),
        tooltip=[alt.Tooltip("Patient:N"), alt.Tooltip("Marker:N"), alt.Tooltip("Value:Q", format=",.2f")],
    )
    if ALT5:
        enc["xOffset"] = "Marker:N"
        enc["y"] = alt.Y("Value:Q", title="Value as entered (units not supplied)")
    else:
        enc["y"] = alt.Y("Value:Q", stack=None, title="Value as entered (units not supplied)")
    chart = alt.Chart(long).mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6, opacity=.92).encode(**enc)
    return themed(chart)


def scatter_chart(df_num):
    d = df_num.dropna(subset=["glucose", "haemoglobin", "cholesterol"]).rename(columns={"full_name": "Patient"})
    chart = (alt.Chart(d).mark_circle(opacity=.88, stroke="#FFFFFF", strokeWidth=2).encode(
        x=alt.X("glucose:Q", title="Glucose", scale=alt.Scale(zero=False)),
        y=alt.Y("cholesterol:Q", title="Cholesterol", scale=alt.Scale(zero=False)),
        size=alt.Size("haemoglobin:Q", title="Haemoglobin", scale=alt.Scale(range=[180, 1000])),
        color=alt.Color("haemoglobin:Q", scale=alt.Scale(range=["#0F9D8A", "#7C3AED"]), legend=None),
        tooltip=[alt.Tooltip("Patient:N"), alt.Tooltip("glucose:Q", title="Glucose"),
                 alt.Tooltip("haemoglobin:Q", title="Haemoglobin"), alt.Tooltip("cholesterol:Q", title="Cholesterol")],
    ).interactive())
    return themed(chart)


def stats_card(df_num):
    rows_html = ""
    for label, col in MARKER_COLS.items():
        s = df_num[col].dropna()
        if s.empty:
            continue
        avg, lo, hi = s.mean(), s.min(), s.max()
        pct = max(4, min(100, (avg / hi * 100) if hi else 0))
        color = MARKER_COLORS[label]
        rows_html += (f"<div class='hp-stat-row'><div class='hp-stat-top'><span class='hp-swatch' style='background:{color}'></span>"
                      f"<b>{label}</b><span class='avg'>{fmt_num(round(avg, 2))}</span></div>"
                      f"<div class='hp-bar'><i style='width:{pct:.0f}%;background:{color}'></i></div>"
                      f"<div class='hp-stat-sub'>Average · range {fmt_num(lo)} – {fmt_num(hi)} · {len(s)} record(s)</div></div>")
    return ("<div class='hp-card'><div class='hp-card-label'>Patient statistics</div>"
            "<h3 style='margin-top:10px'>Blood-test averages</h3>"
            "<p class='hp-muted' style='font-size:13.5px'>Calculated from the records stored in SQLite.</p>" + rows_html + "</div>")


def recent_table(df):
    body = ""
    for _, r in df.iterrows():
        body += (f"<tr><td><div class='hp-who'><div class='hp-avatar'>{esc(initials(r['full_name']))}</div>"
                 f"<div><b>{esc(r['full_name'])}</b><span>Record #{esc(r['id'])}</span></div></div></td>"
                 f"<td class='hp-muted'>{esc(r['dob'])}</td><td class='hp-muted'>{esc(r['email'])}</td>"
                 f"<td><span class='hp-pill g'>{fmt_num(r['glucose'])}</span></td>"
                 f"<td><span class='hp-pill h'>{fmt_num(r['haemoglobin'])}</span></td>"
                 f"<td><span class='hp-pill c'>{fmt_num(r['cholesterol'])}</span></td></tr>")
    return ("<div class='hp-table-wrap'><table class='hp-table'><thead><tr><th>Patient</th><th>Date of birth</th><th>Email</th>"
            "<th>Glucose</th><th>Haemoglobin</th><th>Cholesterol</th></tr></thead><tbody>" + body + "</tbody></table></div>")


# =====================================================================
#  Pages
# =====================================================================
if page == "Dashboard":
    rows = list_patients(); issues = list_issues()
    render_dashboard_hero(len(rows))

    a, b, c, d = st.columns(4)
    latest = rows[-1]["full_name"] if rows else None
    kpi(a, "users", "teal", "Patient records", len(rows), f"Latest: {latest}" if latest else "No records saved yet",
        "Valid unique patient records saved in SQLite")
    kpi(b, "alert", "purple", "Validation issues", len(issues), "Rejected or duplicate assessment rows",
        "Rejected or duplicate assessment rows")
    kpi(c, "cpu", "blue", "AI service", "Connected" if api_is_configured() else "Not configured",
        "External remarks generation", small=True)
    kpi(d, "db", "navy", "Data storage", "SQLite", "Local relational database", small=True)

    if rows:
        df = pd.DataFrame(rows)
        dnum = numeric_frame(df)

        section("Blood test snapshot", "Values as entered · units not supplied")
        left, right = st.columns([1.6, 1])
        with left:
            choice = st.radio("Marker", ["All markers"] + list(MARKER_COLS), horizontal=True, label_visibility="collapsed", key="marker_choice")
            st.altair_chart(blood_chart(dnum, choice), use_container_width=True, theme=None)
            st.caption("Latest 8 patients · hover any bar for exact values · scales differ by marker, so pick a single marker to compare closely.")
        with right:
            st.markdown(flat(stats_card(dnum)), unsafe_allow_html=True)

        section("Patient insights", "Glucose vs cholesterol · bubble size shows haemoglobin")
        l2, r2 = st.columns([1.6, 1])
        with l2:
            if dnum.dropna(subset=["glucose", "haemoglobin", "cholesterol"]).empty:
                st.info("Not enough numeric values to draw the insight chart yet.")
            else:
                st.altair_chart(scatter_chart(dnum), use_container_width=True, theme=None)
                st.caption("Scroll to zoom and drag to pan · hover a bubble to identify the patient.")
        with r2:
            st.markdown('<div class="hp-card"><div class="hp-card-label">Data interpretation</div><h3 style="margin-top:12px">Clinical context matters</h3><p>Blood-test values must be interpreted with their units, laboratory reference ranges, fasting status and patient history. This prototype does not diagnose disease.</p></div>', unsafe_allow_html=True)

        section("Recent patient activity", "Latest saved records")
        st.markdown(flat(recent_table(df[["id", "full_name", "dob", "email", "glucose", "haemoglobin", "cholesterol"]].tail(6).iloc[::-1])), unsafe_allow_html=True)
    else:
        st.write("")
        st.info("Your patient workspace is ready. Add a patient or process the supplied assessment dataset to begin.")
        st.markdown('<div class="hp-card"><div class="hp-card-label">Getting started</div><h3 style="margin-top:8px">Build your first patient record</h3><p>Use Add Patient to enter a record, or open Test Data & Validation to process the ten assessment records and inspect validation outcomes.</p></div>', unsafe_allow_html=True)
    st.caption("Educational prototype only · AI-generated remarks are informational and must be reviewed by a qualified healthcare professional.")

elif page == "Add Patient":
    hero("PATIENT MANAGEMENT", "Register a patient", "Enter patient details and blood-test values. All fields are validated before saving.")
    with st.form("add", clear_on_submit=True):
        st.markdown("#### Personal information")
        x, y = st.columns(2)
        name = x.text_input("Full name", placeholder="e.g. Alex Morgan")
        dob = y.date_input("Date of birth", value=date(1995, 1, 1), max_value=date.today(), format="DD/MM/YYYY")
        email = x.text_input("Email address", placeholder="name@example.com")
        st.markdown("---")
        st.markdown("#### Blood test results")
        st.caption("Enter the numeric values exactly as provided by the laboratory. Units and reference ranges are not specified in this assessment.")
        p, q, r = st.columns(3)
        glucose = p.text_input("Glucose", placeholder="e.g. 95")
        hb = q.text_input("Haemoglobin", placeholder="e.g. 13.5")
        chol = r.text_input("Cholesterol", placeholder="e.g. 180")
        go = st.form_submit_button("Validate and save patient", type="primary", use_container_width=True)
    if go:
        data = {"full_name": name, "dob": dob.strftime("%d/%m/%Y"), "email": email, "glucose": glucose, "haemoglobin": hb, "cholesterol": chol}
        errors = validate_patient(data)
        if errors:
            st.error("Please correct the following before saving:")
            for e in errors: st.write("• " + e)
        else:
            try:
                create_patient(data, "Not generated yet — open AI Health Remarks to call the external API.")
                st.success("Patient record saved successfully.")
            except ValueError as e: st.error(str(e))

elif page == "Patient Records":
    hero("RECORDS DIRECTORY", "Patient records", "View, export, update or remove saved patient information.")
    rows = list_patients()
    if rows:
        df = pd.DataFrame(rows)
        x, y = st.columns([3, 1])
        with x: st.caption(f"{len(rows)} patient record(s) in your database")
        with y: st.download_button("↓ Export CSV", df.to_csv(index=False).encode(), "healthpredict_records.csv", "text/csv", use_container_width=True)
        st.dataframe(df[["id", "full_name", "dob", "email", "glucose", "haemoglobin", "cholesterol", "remarks"]], use_container_width=True, hide_index=True)
        section("Manage a record", "Select a patient below")
        pid = st.selectbox("Patient record", [r["id"] for r in rows], format_func=lambda i: f'#{i}  ·  {next(r["full_name"] for r in rows if r["id"] == i)}')
        rec = get_patient(pid)
        with st.expander("✎  Edit patient details", expanded=True):
            with st.form("edit"):
                a, b = st.columns(2)
                n = a.text_input("Full name", rec["full_name"]); dob = b.text_input("DOB (DD/MM/YYYY)", rec["dob"])
                em = a.text_input("Email address", rec["email"]); gl = b.text_input("Glucose", str(rec["glucose"]))
                he = a.text_input("Haemoglobin", str(rec["haemoglobin"])); ch = b.text_input("Cholesterol", str(rec["cholesterol"]))
                save = st.form_submit_button("Save changes", type="primary")
            if save:
                data = {"full_name": n, "dob": dob, "email": em, "glucose": gl, "haemoglobin": he, "cholesterol": ch}
                errs = validate_patient(data)
                if errs:
                    for z in errs: st.error(z)
                else:
                    try: update_patient(pid, data); st.success("Patient record updated."); st.rerun()
                    except ValueError as z: st.error(str(z))
        with st.expander("⚠  Delete patient record"):
            st.warning("Deleting a record is permanent for this local database.")
            confirm = st.checkbox("I understand and want to delete this record.")
            if st.button("Delete selected patient", disabled=not confirm):
                delete_patient(pid); st.success("Record deleted."); st.rerun()
    else:
        st.info("No valid patient records are available yet. Add a patient or process the assessment data.")

elif page == "AI Health Remarks":
    hero("AI ASSISTANCE", "AI health remarks", "Generate a cautious informational summary from the selected patient's blood-test values.")
    if not api_is_configured():
        st.warning("Gemini API is not configured. Add GEMINI_API_KEY to your local .env file to enable external AI remarks.")
    rows = list_patients()
    if rows:
        pid = st.selectbox("Select patient", [r["id"] for r in rows], format_func=lambda i: f'#{i}  ·  {next(r["full_name"] for r in rows if r["id"] == i)}')
        rec = get_patient(pid)
        st.markdown(flat(f"""
        <div class="hp-patient"><div class="hp-avatar lg">{esc(initials(rec.get('full_name')))}</div>
        <div><div class="nm">{esc(rec.get('full_name'))}</div>
        <div class="sub">Record #{esc(pid)} · {esc(rec.get('email'))} · DOB {esc(rec.get('dob'))}</div></div></div>"""), unsafe_allow_html=True)
        a, b, c = st.columns(3)
        a.metric("Glucose", rec["glucose"]); b.metric("Haemoglobin", rec["haemoglobin"]); c.metric("Cholesterol", rec["cholesterol"])
        st.write("")
        if st.button("✦ Generate AI remarks", type="primary", disabled=not api_is_configured()):
            with st.spinner("Requesting an informational summary from Gemini..."):
                try:
                    remark = generate_health_remarks(rec); update_patient(pid, rec, remarks=remark); st.success("AI remarks generated and saved."); st.rerun()
                except Exception as e: st.error(str(e))
        section("Saved remarks", "AI-generated content · requires human review")
        if rec.get("remarks"):
            st.markdown(flat(f"""
            <div class="hp-remarks"><div class="hp-remarks-head">{svg_icon('spark', 18, '#0b5e53', 2)} AI-generated remarks · informational only</div>
            <div class="hp-remarks-body">{md_to_html(rec["remarks"])}</div></div>"""), unsafe_allow_html=True)
        else: st.info("No AI remarks have been generated for this patient.")
    else: st.info("Add or import a valid patient record before generating AI remarks.")
    st.caption("AI output is not a medical diagnosis or a substitute for professional medical advice.")

elif page == "Test Data & Validation":
    hero("ASSESSMENT WORKSPACE", "Test data & validation", "Process the exact ten records supplied in the assignment and inspect every validation outcome.")
    rows = [
        ("Robyn Pears", "28.01.1960", "robyn@gmail.com", "232", "13.5", "180"),
        ("John Hunter", "10.12.1990", "hunter@gmail", "94", "15", "200"),
        ("Darryl Tim", "12.11.1993", "timd@smh.com.au", "240", "18.6", "326"),
        ("Peter Larry", "31.11.2001", "Larry@hotmail.com", "88", "11.5", "165"),
        ("Sam Kerr", "09.12.2006", "sam@news.com.au", "198", "8.9", "192"),
        ("Robyn Pears", "28.01.1960", "robyn@gmail.com", "232", "13.5", "180"),
        ("Madison XI", "12.09.1998", "madison@hotmail.com", "85", "7.6", "163"),
        ("Kris Wu", "19.10.2030", "Kris.wu.gmail.com", "79", "16.5", "197"),
        ("Tenille Singh", "30.11.1991", "Tenille@yahoo.com", "101", "15", "310"),
        ("Prem Kumar", "28.04.1990", "prem@telstra.com", "155", "12.5", "265")]
    k1, k2, k3 = st.columns(3)
    kpi(k1, "file", "blue", "Supplied records", len(rows), "Assessment dataset")
    kpi(k2, "check", "teal", "Saved in database", len(list_patients()), "Valid unique records")
    kpi(k3, "alert", "purple", "Logged issues", len(list_issues()), "Invalid or duplicate rows")
    st.write("")
    st.markdown('<div class="hp-note"><b>Important:</b> The supplied values are preserved exactly. Invalid records and duplicates are logged with reasons rather than silently corrected.</div>', unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(rows, columns=["Name", "DOB", "Email", "Glucose", "Haemoglobin", "Cholesterol"]), use_container_width=True, hide_index=True)
    st.write("")
    if st.button("Process all 10 supplied records", type="primary"):
        clear_issues(); saved = 0
        for i, row in enumerate(rows, 1):
            data = dict(zip(["full_name", "dob", "email", "glucose", "haemoglobin", "cholesterol"], row))
            errs = validate_patient(data)
            if not errs:
                try: create_patient(data, "Not generated — generate using AI Health Remarks."); saved += 1
                except ValueError as e: errs = [str(e)]
            if errs: log_issue(i, data, "; ".join(errs))
        st.success(f"Processing complete: {saved} valid unique records saved. Rejected or duplicate rows are listed below.")
        st.rerun()
    section("Validation log", "Invalid and duplicate rows")
    log = list_issues()
    if log: st.dataframe(pd.DataFrame(log), use_container_width=True, hide_index=True)
    else: st.info("No validation issues logged yet. Process the ten supplied rows to populate this report.")
