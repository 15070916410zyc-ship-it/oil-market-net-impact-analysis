"""Single-source visual system for the Streamlit research workspace."""

from __future__ import annotations

import streamlit as st


def apply_design_system() -> None:
    """Apply the bright editorial product theme without legacy overrides."""
    st.markdown(
        """
        <style>
        :root {
            --canvas: #f3f6f4;
            --surface: #fbfcfa;
            --surface-soft: #eaf0ed;
            --ink: #172522;
            --ink-soft: #64716d;
            --line: #d7e0dc;
            --line-strong: #bdcbc5;
            --accent: #2f7168;
            --accent-strong: #20564f;
            --accent-soft: #dcece7;
            --positive: #55786f;
            --warning: #8b7454;
            --radius-control: 14px;
            --radius-panel: 26px;
            --shadow-soft: 0 22px 64px rgba(39, 67, 60, 0.08);
            --font-sans: "Aptos", "SF Pro Display", "Segoe UI", "PingFang SC", "Microsoft YaHei UI", sans-serif;
            --font-display: "Aptos Display", "SF Pro Display", "Segoe UI", "PingFang SC", "Microsoft YaHei UI", sans-serif;
        }

        html, body, .stApp, [data-testid="stAppViewContainer"],
        [data-testid="stMain"], [data-testid="stMainBlockContainer"] {
            background: var(--canvas) !important;
            color: var(--ink) !important;
            color-scheme: light !important;
            font-family: var(--font-sans) !important;
        }
        html { scroll-behavior: smooth; }
        body { overflow-x: hidden; }
        .stApp {
            background:
                radial-gradient(ellipse at 10% 4%, rgba(80, 148, 132, .14), transparent 31rem),
                radial-gradient(ellipse at 92% 28%, rgba(112, 151, 163, .12), transparent 36rem),
                radial-gradient(ellipse at 51% 88%, rgba(133, 167, 154, .10), transparent 42rem),
                linear-gradient(145deg, #f7f9f7 0%, #f2f6f4 52%, #f7f8f6 100%) !important;
            isolation: isolate;
        }
        .stApp > [data-testid="stAppViewContainer"] {
            position: relative;
            z-index: 1;
            background: transparent !important;
        }
        [data-testid="stMain"], [data-testid="stMainBlockContainer"] {
            background: transparent !important;
        }
        [data-testid="stHeader"] {
            height: 0 !important;
            min-height: 0 !important;
            background: transparent !important;
            border: 0 !important;
        }
        [data-testid="stToolbar"], [data-testid="stDecoration"] { visibility: hidden !important; }
        .block-container {
            max-width: 1440px !important;
            position: relative;
            z-index: 1;
            padding: 1.5rem 3rem 5rem !important;
        }
        #MainMenu, footer { visibility: hidden; }
        [data-testid="stSidebar"] { background: var(--surface) !important; border-right: 1px solid var(--line); }

        h1, h2, h3, h4, h5, h6, p, label, span, small,
        [data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] * {
            color: inherit;
        }
        h1, h2, h3 { text-wrap: balance; }
        h1, h2, h3, [id] { scroll-margin-top: 1.5rem; }
        h1 { font-family: var(--font-sans) !important; letter-spacing: -0.055em !important; }
        h2 { font-family: var(--font-display) !important; letter-spacing: -0.035em !important; }
        h3, h4, h5, h6 { font-family: var(--font-sans) !important; letter-spacing: -0.018em !important; }
        p { text-wrap: pretty; }
        a { color: var(--accent-strong) !important; text-underline-offset: 0.2em; }
        hr { border-color: var(--line) !important; }
        .skip-link {
            position: fixed;
            top: 0.75rem;
            left: 0.75rem;
            z-index: 50;
            padding: 0.65rem 0.85rem;
            border-radius: 10px;
            background: var(--ink);
            color: var(--surface) !important;
            transform: translateY(-160%);
            transition: transform 150ms ease;
        }
        .skip-link:focus-visible { transform: translateY(0); outline: 3px solid var(--accent); }

        .stApp::before {
            content: "";
            position: fixed;
            inset: -8%;
            z-index: 0;
            pointer-events: none;
            background-image:
                radial-gradient(circle at 26% 22%, rgba(47,113,104,.14) 0 1px, transparent 2px),
                radial-gradient(circle at 73% 68%, rgba(78,126,139,.12) 0 1px, transparent 2px),
                url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1600 1200' fill='none' stroke='%23587970' stroke-opacity='.29' stroke-width='1.15'%3E%3Cpath d='M-180 235 C115 45 360 415 690 205 S1205 30 1770 290'/%3E%3Cpath d='M-180 276 C125 86 370 456 700 246 S1215 71 1770 331'/%3E%3Cpath d='M-180 317 C135 127 380 497 710 287 S1225 112 1770 372'/%3E%3Cpath d='M-180 358 C145 168 390 538 720 328 S1235 153 1770 413'/%3E%3Cpath d='M-180 399 C155 209 400 579 730 369 S1245 194 1770 454'/%3E%3Cpath d='M-210 835 C105 585 390 1010 735 752 S1280 575 1810 842'/%3E%3Cpath d='M-210 880 C115 630 400 1055 745 797 S1290 620 1810 887'/%3E%3Cpath d='M-210 925 C125 675 410 1100 755 842 S1300 665 1810 932'/%3E%3Cpath d='M1110 -140 C875 160 1360 390 1040 665 S870 1065 1290 1340'/%3E%3Cpath d='M1170 -140 C935 160 1420 390 1100 665 S930 1065 1350 1340'/%3E%3Cpath d='M1230 -140 C995 160 1480 390 1160 665 S990 1065 1410 1340'/%3E%3C/svg%3E");
            background-position: center;
            background-repeat: no-repeat;
            background-size: cover;
            opacity: .88;
            transform-origin: center;
            animation: ambient-field 12s cubic-bezier(.4,0,.2,1) infinite alternate;
        }
        .stApp::after {
            content: "";
            position: fixed;
            inset: 0;
            z-index: 0;
            pointer-events: none;
            background-image:
                radial-gradient(ellipse at 76% 18%, rgba(65,130,118,.12), transparent 18rem),
                linear-gradient(90deg, rgba(243,246,244,.04), rgba(243,246,244,.48) 48%, rgba(243,246,244,.02)),
                url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1600 1200' fill='none'%3E%3Cg stroke-width='1.15' stroke-opacity='.46'%3E%3Cpath d='M1050 -120V1320' stroke='%23699186'/%3E%3Cpath d='M1165 -120V1320' stroke='%232f7168'/%3E%3Cpath d='M1280 -120V1320' stroke='%237d98a2'/%3E%3Cpath d='M1395 -120V1320' stroke='%2390a09a'/%3E%3C/g%3E%3Cg fill='%23f3f6f4' stroke-width='1.6'%3E%3Ccircle cx='1050' cy='245' r='8' stroke='%23699186'/%3E%3Ccircle cx='1165' cy='410' r='5' stroke='%232f7168'/%3E%3Ccircle cx='1280' cy='665' r='7' stroke='%237d98a2'/%3E%3Ccircle cx='1395' cy='870' r='6' stroke='%2390a09a'/%3E%3Ccircle cx='1050' cy='940' r='58' stroke='%23699186' stroke-dasharray='3 4'/%3E%3Ccircle cx='1165' cy='170' r='38' stroke='%232f7168' stroke-opacity='.8'/%3E%3C/g%3E%3C/svg%3E");
            background-position: center;
            background-repeat: no-repeat;
            background-size: cover;
            opacity: .72;
            transform-origin: center;
            animation: ambient-nodes 16s cubic-bezier(.4,0,.2,1) infinite alternate;
        }
        @supports (animation-timeline: scroll()) {
            .stApp::after { animation: art-node-scroll linear both; animation-timeline: scroll(root block); }
        }
        @keyframes ambient-field {
            from { transform: translate3d(-1.8%, -1.1%, 0) scale(1.035) rotate(-.35deg); opacity: .62; }
            to { transform: translate3d(2.2%, 1.6%, 0) scale(1.085) rotate(.45deg); opacity: .92; }
        }
        @keyframes ambient-nodes {
            from { transform: translate3d(0, -1.2%, 0) scale(1.01); opacity: .48; }
            to { transform: translate3d(-1.6%, 2.2%, 0) scale(1.045); opacity: .78; }
        }
        @keyframes art-field-scroll {
            from { transform: translate3d(-2%, -1.5%, 0) scale(1.03); opacity: .74; }
            to { transform: translate3d(2.5%, 4%, 0) scale(1.10); opacity: .46; }
        }
        @keyframes art-node-scroll {
            from { transform: translate3d(0, -5%, 0) scale(1.02); opacity: .38; }
            to { transform: translate3d(-1.5%, 8%, 0) scale(1.06); opacity: .76; }
        }
        @supports (animation-timeline: view()) {
            .view-reveal {
                animation: section-enter linear both;
                animation-timeline: view();
                animation-range: entry 4% cover 28%;
            }
        }
        @keyframes section-enter {
            from { opacity: .18; transform: translate3d(0, 2.4rem, 0) scale(.985); }
            to { opacity: 1; transform: translate3d(0, 0, 0) scale(1); }
        }

        .research-brand {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            min-height: 2.75rem;
            margin-bottom: 0.65rem;
            color: var(--ink);
            font-family: var(--font-display);
            font-size: 1.24rem;
            font-weight: 700;
            letter-spacing: -0.02em;
        }
        .research-brand-mark {
            position: relative;
            width: 2rem;
            height: 2rem;
            border: 2px solid var(--accent);
            border-radius: 58% 42% 62% 38% / 65% 46% 54% 35%;
            transform: rotate(45deg);
            box-shadow: inset 0 0 0 5px var(--canvas);
            animation: brand-breathe 3.6s ease-in-out infinite alternate;
        }
        .research-brand-mark::after {
            content: "";
            position: absolute;
            inset: 0.38rem;
            border: 1.5px solid var(--accent-strong);
            border-radius: 50%;
        }
        .research-brand-mark > i { display: none; }
        @keyframes brand-breathe {
            from { transform: rotate(36deg) scale(.94); border-radius: 58% 42% 62% 38% / 65% 46% 54% 35%; }
            to { transform: rotate(54deg) scale(1.06); border-radius: 42% 58% 39% 61% / 48% 62% 38% 52%; }
        }

        .hero-copy {
            min-height: calc(100vh - 7rem);
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            padding: 7rem 0 8rem;
            text-align: left;
            animation: reveal-up 620ms cubic-bezier(.22,.72,.2,1) both;
        }
        .hero-kicker, .section-kicker {
            margin: 0 0 1rem !important;
            color: var(--accent-strong) !important;
            font-size: 0.78rem !important;
            font-weight: 700 !important;
            letter-spacing: 0.14em !important;
            text-transform: uppercase;
        }
        .hero-copy h1 {
            max-width: 11ch;
            margin: 0 !important;
            color: var(--ink) !important;
            font-size: clamp(3.4rem, 7.6vw, 7.8rem) !important;
            font-weight: 640 !important;
            line-height: 0.98 !important;
        }
        .hero-copy > p:last-of-type {
            max-width: 38rem;
            margin: 1.5rem 0 0 !important;
            color: var(--ink-soft) !important;
            font-size: clamp(1rem, 1.35vw, 1.18rem) !important;
            line-height: 1.85 !important;
        }
        .hero-actions { display: flex; gap: 1.3rem; align-items: center; justify-content: flex-start; margin-top: 2rem; }
        .hero-action-primary, .hero-action-secondary {
            display: inline-flex;
            align-items: center;
            min-height: 2.8rem;
            font-size: 0.94rem;
            font-weight: 650;
        }
        .hero-action-primary {
            padding: 0.72rem 1.2rem;
            border-radius: var(--radius-control);
            background: var(--accent);
            color: #f8faf7 !important;
            box-shadow: 0 10px 24px rgba(53, 107, 101, 0.18);
        }
        .hero-action-secondary { color: var(--ink) !important; }
        .hero-action-secondary::after { content: "↗"; margin-left: 0.45rem; color: var(--accent); }
        .section-intro, .decision-hero, .data-library-intro {
            margin: 3rem 0 1.5rem;
            padding: 0 !important;
            border: 0 !important;
            background: transparent !important;
            box-shadow: none !important;
        }
        .section-intro h2, .decision-hero h2, .data-library-intro h2 {
            max-width: 19ch;
            margin: 0.2rem 0 0.9rem !important;
            color: var(--ink) !important;
            font-size: clamp(2.15rem, 3.5vw, 3.65rem) !important;
            font-weight: 650 !important;
            line-height: 1.12 !important;
        }
        .decision-hero span, .data-library-intro span {
            color: var(--accent-strong) !important;
            font-size: 0.76rem;
            font-weight: 700;
            letter-spacing: 0.12em;
        }
        .section-intro p, .decision-hero p, .data-library-intro p {
            max-width: 52rem;
            margin: 0 !important;
            color: var(--ink-soft) !important;
            font-size: 1rem !important;
            line-height: 1.8 !important;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 0.35rem !important;
            min-height: 3.4rem;
            width: fit-content;
            max-width: 100%;
            padding: 0.35rem !important;
            border: 1px solid var(--line);
            border-radius: 999px !important;
            background: rgba(234, 240, 237, 0.84) !important;
            backdrop-filter: blur(18px);
        }
        .stTabs [data-baseweb="tab"] {
            min-height: 2.7rem;
            padding: 0.5rem 1rem !important;
            border: 0 !important;
            border-radius: 999px !important;
            background: transparent !important;
            color: var(--ink-soft) !important;
            font-weight: 600;
            transition: color 160ms cubic-bezier(.2,.7,.2,1), transform 160ms cubic-bezier(.2,.7,.2,1), background-color 160ms cubic-bezier(.2,.7,.2,1), box-shadow 160ms cubic-bezier(.2,.7,.2,1);
        }
        .stTabs [data-baseweb="tab"]:hover { color: var(--ink) !important; transform: translateY(-1px); }
        .stTabs [aria-selected="true"] {
            background: var(--surface) !important;
            color: var(--ink) !important;
            box-shadow: 0 5px 16px rgba(39,67,60,.09);
        }
        .stTabs [data-baseweb="tab-highlight"] { display: none !important; }
        .stTabs [data-baseweb="tab-border"] { display: none; }

        [data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--line) !important;
            border-radius: var(--radius-panel) !important;
            background: rgba(251, 252, 250, 0.86) !important;
            box-shadow: 0 1px 0 rgba(255, 255, 255, 0.88) inset;
            corner-shape: squircle;
        }
        [data-testid="stMetric"] {
            padding: 1rem 1.1rem !important;
            border: 1px solid var(--line);
            border-radius: 18px;
            background: rgba(251,252,250,.76) !important;
            box-shadow: 0 10px 30px rgba(39,67,60,.045);
        }
        [data-testid="stMetricLabel"] { color: var(--ink-soft) !important; }
        [data-testid="stMetricValue"] {
            color: var(--ink) !important;
            font-variant-numeric: tabular-nums;
            letter-spacing: -0.03em;
        }
        [data-testid="stDataFrame"], [data-testid="stTable"], [data-testid="stPlotlyChart"] {
            overflow: hidden;
            border: 1px solid var(--line) !important;
            border-radius: var(--radius-panel) !important;
            background: rgba(251, 252, 250, 0.94) !important;
            box-shadow: var(--shadow-soft);
            corner-shape: squircle;
        }
        [data-testid="stPlotlyChart"] { padding: 0.45rem; }

        div[data-baseweb="select"] > div,
        div[data-baseweb="base-input"],
        div[data-baseweb="input"] > div,
        div[data-baseweb="textarea"] > div,
        [data-testid="stTextInput"] input,
        [data-testid="stNumberInput"] input,
        [data-testid="stDateInput"] input {
            min-height: 2.9rem !important;
            border-color: var(--line-strong) !important;
            border-radius: var(--radius-control) !important;
            background: var(--surface) !important;
            color: var(--ink) !important;
            box-shadow: none !important;
        }
        div[data-baseweb="select"] *, div[data-baseweb="base-input"] *,
        [data-testid="stTextInput"] input::placeholder { color: var(--ink-soft) !important; }
        [data-baseweb="popover"], [data-baseweb="menu"], [role="listbox"] {
            border-color: var(--line) !important;
            border-radius: 14px !important;
            background: var(--surface) !important;
            color: var(--ink) !important;
            box-shadow: var(--shadow-soft) !important;
        }
        [role="option"] { background: var(--surface) !important; color: var(--ink) !important; }
        [role="option"]:hover, [aria-selected="true"][role="option"] { background: var(--accent-soft) !important; }
        [data-baseweb="tag"] {
            border: 1px solid rgba(53, 107, 101, 0.20) !important;
            border-radius: 9px !important;
            background: var(--accent-soft) !important;
            color: var(--ink) !important;
        }
        [data-baseweb="tag"] * { color: var(--ink) !important; }
        .stSelectbox label, .stMultiSelect label, .stTextInput label,
        .stNumberInput label, .stDateInput label, .stRadio label {
            color: var(--ink-soft) !important;
            font-size: 0.86rem !important;
            font-weight: 560 !important;
        }

        .stButton > button, .stDownloadButton > button, [data-testid="baseButton-secondary"],
        [data-testid="baseButton-primary"], [data-testid="stBaseButton-secondary"],
        [data-testid="stBaseButton-primary"] {
            min-height: 2.9rem !important;
            padding: 0.68rem 1.1rem !important;
            border: 1px solid var(--line-strong) !important;
            border-radius: var(--radius-control) !important;
            background: var(--surface) !important;
            color: var(--ink) !important;
            font-weight: 650 !important;
            box-shadow: none !important;
            transition: transform 160ms cubic-bezier(.2,.7,.2,1), border-color 160ms cubic-bezier(.2,.7,.2,1), box-shadow 160ms cubic-bezier(.2,.7,.2,1), background-color 160ms cubic-bezier(.2,.7,.2,1) !important;
            touch-action: manipulation;
        }
        .stButton > button:hover, .stDownloadButton > button:hover {
            transform: translateY(-1px);
            border-color: #aeb6c7 !important;
            box-shadow: 0 8px 20px rgba(55, 65, 89, 0.08) !important;
        }
        .stButton > button[data-testid="stBaseButton-primary"],
        .stDownloadButton > button[data-testid="stBaseButton-primary"],
        [data-testid="baseButton-primary"], [data-testid="stBaseButton-primary"] {
            border-color: var(--accent) !important;
            background: var(--accent) !important;
            color: #f8faf7 !important;
            opacity: 1 !important;
            box-shadow: 0 10px 24px rgba(53, 107, 101, 0.18) !important;
        }
        .stButton > button[data-testid="stBaseButton-primary"] *,
        .stDownloadButton > button[data-testid="stBaseButton-primary"] *,
        [data-testid="baseButton-primary"] *, [data-testid="stBaseButton-primary"] * { color: #f8faf7 !important; }
        [data-testid="baseButton-primary"]:hover, [data-testid="stBaseButton-primary"]:hover { background: #2b5d57 !important; }
        [data-testid="baseButton-primary"]:disabled, [data-testid="stBaseButton-primary"]:disabled {
            border-color: #b9ccc7 !important;
            background: #dfeae7 !important;
            color: #49645f !important;
            opacity: 1 !important;
            box-shadow: none !important;
        }
        [data-testid="baseButton-primary"]:disabled *, [data-testid="stBaseButton-primary"]:disabled * {
            color: #49645f !important;
        }
        button:focus-visible, [role="tab"]:focus-visible, input:focus-visible,
        [role="combobox"]:focus-visible, [role="radio"]:focus-visible {
            outline: 3px solid rgba(53, 107, 101, 0.28) !important;
            outline-offset: 2px !important;
        }

        [data-testid="stRadio"] [role="radiogroup"] {
            display: inline-flex !important;
            gap: 0.25rem !important;
            padding: 0.25rem !important;
            border: 1px solid var(--line) !important;
            border-radius: 14px !important;
            background: var(--surface-soft) !important;
        }
        [data-testid="stRadio"] [role="radiogroup"] > label {
            min-height: 2.35rem;
            margin: 0 !important;
            padding: 0.48rem 0.82rem !important;
            border-radius: 10px !important;
            background: transparent !important;
            color: var(--ink-soft) !important;
            transition: background-color 150ms cubic-bezier(.2,.7,.2,1), color 150ms cubic-bezier(.2,.7,.2,1), box-shadow 150ms cubic-bezier(.2,.7,.2,1);
        }
        [data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked) {
            background: var(--surface) !important;
            color: var(--ink) !important;
            box-shadow: 0 3px 10px rgba(55, 65, 89, 0.08);
        }
        [data-testid="stRadio"] [role="radiogroup"] > label p { color: var(--ink-soft) !important; }
        [data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked) p { color: var(--ink) !important; }
        [data-testid="stRadio"] [role="radiogroup"] > label > div:first-child { display: none !important; }

        [data-testid="stAlert"] {
            border: 1px solid var(--line) !important;
            border-radius: 16px !important;
            background: var(--accent-soft) !important;
            color: var(--ink) !important;
        }
        [data-testid="stAlert"] [data-testid="stAlertContainer"] {
            background: transparent !important;
            color: var(--ink) !important;
        }
        [data-testid="stAlert"] [data-testid^="stAlertContent"] *,
        [data-testid="stAlert"] [data-testid="stMarkdownContainer"] * {
            color: var(--ink) !important;
        }
        [data-testid="stExpander"] {
            overflow: hidden;
            border: 1px solid var(--line) !important;
            border-radius: 16px !important;
            background: var(--surface) !important;
        }
        [data-testid="stPopoverButton"],
        [data-testid="stPopover"] > button,
        [data-testid="stPopover"] button[data-testid^="baseButton"] {
            min-height: 2.75rem !important;
            border: 1px solid var(--line) !important;
            border-radius: var(--radius-control) !important;
            background: rgba(251, 252, 250, 0.92) !important;
            color: var(--ink) !important;
            box-shadow: none !important;
        }
        [data-testid="stPopoverButton"] *, [data-testid="stPopover"] button * { color: var(--ink) !important; }
        [data-testid="stStatusWidget"] {
            border-color: var(--line) !important;
            border-radius: 16px !important;
            background: var(--surface) !important;
        }
        [data-testid="stFileUploaderDropzone"] {
            border-color: var(--line-strong) !important;
            border-radius: 16px !important;
            background: var(--surface-soft) !important;
        }
        .decision-summary, .investment-card, .hedge-card, .source-audit-card,
        .data-result-card, .forecast-summary {
            border: 1px solid var(--line) !important;
            border-radius: var(--radius-panel) !important;
            background: var(--surface) !important;
            box-shadow: var(--shadow-soft) !important;
        }
        .data-empty-state {
            min-height: 13rem;
            display: grid;
            align-content: center;
            gap: .6rem;
            margin: 1.2rem 0 2.5rem;
            padding: 2rem;
            border: 1px dashed var(--line-strong);
            border-radius: var(--radius-panel);
            background:
                radial-gradient(circle at 18% 30%, rgba(53,107,101,.10), transparent 18rem),
                rgba(251,252,250,.76);
        }
        .data-empty-state strong { color: var(--ink); font-size: 1.35rem; }
        .data-empty-state span { color: var(--ink-soft); }
        [data-testid="stHorizontalBlock"]:has(.research-brand) {
            align-items: center !important;
        }
        [data-testid="stColumn"]:has(.tool-dock-anchor) {
            padding: .25rem .3rem !important;
            border: 1px solid var(--line);
            border-radius: 999px;
            background: rgba(251,252,250,.78);
            box-shadow: 0 10px 30px rgba(39,67,60,.06);
            backdrop-filter: blur(18px) saturate(140%);
        }
        [data-testid="stColumn"]:has(.tool-dock-anchor) > [data-testid="stVerticalBlock"] {
            gap: 0 !important;
        }
        .tool-dock-anchor { display: none; }
        [data-testid="stColumn"]:has(.tool-dock-anchor) [data-testid="stPopoverButton"],
        [data-testid="stColumn"]:has(.tool-dock-anchor) div[data-baseweb="select"] > div {
            min-height: 2.35rem !important;
            height: 2.35rem !important;
            padding-inline: .65rem !important;
            font-size: .78rem !important;
            border: 0 !important;
            background: transparent !important;
        }

        @keyframes reveal-up {
            from { opacity: 0; transform: translateY(14px); }
            to { opacity: 1; transform: translateY(0); }
        }
        @media (prefers-reduced-motion: reduce) {
            html { scroll-behavior: auto; }
            *, *::before, *::after {
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.01ms !important;
            }
            .stApp::before, .stApp::after { transform: none !important; opacity: .52 !important; }
        }
        @media (max-width: 900px) {
            .block-container { padding: 1rem 1.25rem 4rem !important; }
            [data-testid="stHorizontalBlock"]:has(.research-brand) {
                display: grid !important;
                grid-template-columns: minmax(7.8rem, 1fr) minmax(8.2rem, 10rem) !important;
                gap: 0.55rem !important;
                align-items: center !important;
            }
            [data-testid="stHorizontalBlock"]:has(.research-brand) > [data-testid="stColumn"] {
                width: auto !important;
                min-width: 0 !important;
            }
            [data-testid="stColumn"]:has(.tool-dock-anchor) [data-testid="stPopoverButton"] {
                min-height: 2.55rem !important;
                padding-inline: 0.7rem !important;
                font-size: 0.75rem !important;
                white-space: nowrap;
            }
            [data-testid="stColumn"]:has(.tool-dock-anchor) div[data-baseweb="select"] > div {
                min-height: 2.55rem !important;
            }
            [data-testid="stColumn"]:has(.tool-dock-anchor) div[data-baseweb="select"] {
                min-width: 3.8rem !important;
            }
            .research-brand { margin: 0; font-size: 1.05rem; }
            .research-brand-mark { width: 1.7rem; height: 1.7rem; }
            .hero-copy { min-height: 72vh; padding: 5rem 0 5.5rem; align-items: flex-start; }
            .hero-copy h1 { max-width: 12ch; font-size: clamp(2.8rem, 12vw, 4.4rem) !important; }
            .stTabs [data-baseweb="tab-list"] { gap: 1rem !important; overflow-x: auto; }
            .stTabs [data-baseweb="tab"] { white-space: nowrap; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
