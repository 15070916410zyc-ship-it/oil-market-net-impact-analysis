"""Single-source visual system for the Streamlit research workspace."""

from __future__ import annotations

import streamlit as st


def apply_design_system() -> None:
    """Apply the bright editorial product theme without legacy overrides."""
    st.markdown(
        """
        <style>
        :root {
            --canvas: #f7f7f2;
            --surface: #fcfcf8;
            --surface-soft: #eef1ed;
            --ink: #1f2825;
            --ink-soft: #68736e;
            --line: #dce2dd;
            --line-strong: #c8d0cb;
            --accent: #356b65;
            --accent-strong: #274f4b;
            --accent-soft: #e3eeea;
            --positive: #55786f;
            --warning: #8b7454;
            --radius-control: 12px;
            --radius-panel: 20px;
            --shadow-soft: 0 18px 50px rgba(52, 74, 67, 0.08);
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
                radial-gradient(circle at 14% 9%, rgba(82, 132, 120, .10), transparent 26rem),
                radial-gradient(circle at 86% 32%, rgba(118, 148, 161, .10), transparent 30rem),
                radial-gradient(circle at 48% 76%, rgba(166, 177, 159, .09), transparent 34rem),
                var(--canvas) !important;
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
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1600 1200' fill='none' stroke='%2358746c' stroke-opacity='.24' stroke-width='1.2'%3E%3Cpath d='M-120 255 C180 90 365 390 665 220 S1160 35 1720 270'/%3E%3Cpath d='M-120 290 C185 125 375 425 675 255 S1170 70 1720 305'/%3E%3Cpath d='M-120 325 C190 160 385 460 685 290 S1180 105 1720 340'/%3E%3Cpath d='M-120 360 C195 195 395 495 695 325 S1190 140 1720 375'/%3E%3Cpath d='M-120 395 C200 230 405 530 705 360 S1200 175 1720 410'/%3E%3Cpath d='M-180 845 C130 620 390 980 700 760 S1220 590 1760 815'/%3E%3Cpath d='M-180 885 C140 660 400 1020 710 800 S1230 630 1760 855'/%3E%3Cpath d='M-180 925 C150 700 410 1060 720 840 S1240 670 1760 895'/%3E%3Cpath d='M-180 965 C160 740 420 1100 730 880 S1250 710 1760 935'/%3E%3Cpath d='M1110 -100 C925 175 1320 365 1050 640 S880 1040 1260 1300'/%3E%3Cpath d='M1170 -100 C985 175 1380 365 1110 640 S940 1040 1320 1300'/%3E%3Cpath d='M1230 -100 C1045 175 1440 365 1170 640 S1000 1040 1380 1300'/%3E%3C/svg%3E");
            background-position: center;
            background-repeat: no-repeat;
            background-size: cover;
            opacity: .78;
            transform-origin: center;
            animation: ambient-field 4.8s cubic-bezier(.45,0,.55,1) infinite alternate;
        }
        .stApp::after {
            content: "";
            position: fixed;
            inset: 0;
            z-index: 0;
            pointer-events: none;
            background-image:
                linear-gradient(90deg, rgba(247,247,242,.06), rgba(247,247,242,.42) 48%, rgba(247,247,242,.04)),
                url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1600 1200' fill='none'%3E%3Cg stroke-width='1.3' stroke-opacity='.50'%3E%3Cpath d='M1080 -120V1320' stroke='%23699186'/%3E%3Cpath d='M1185 -120V1320' stroke='%23356b65'/%3E%3Cpath d='M1290 -120V1320' stroke='%237d98a2'/%3E%3Cpath d='M1395 -120V1320' stroke='%2390a09a'/%3E%3C/g%3E%3Cg fill='%23f7f7f2' stroke-width='1.6'%3E%3Ccircle cx='1080' cy='245' r='8' stroke='%23699186'/%3E%3Ccircle cx='1185' cy='410' r='5' stroke='%23356b65'/%3E%3Ccircle cx='1290' cy='665' r='7' stroke='%237d98a2'/%3E%3Ccircle cx='1395' cy='870' r='6' stroke='%2390a09a'/%3E%3Ccircle cx='1080' cy='940' r='58' stroke='%23699186' stroke-dasharray='3 4'/%3E%3Ccircle cx='1185' cy='170' r='38' stroke='%23356b65' stroke-opacity='.8'/%3E%3C/g%3E%3C/svg%3E");
            background-position: center;
            background-repeat: no-repeat;
            background-size: cover;
            opacity: .66;
            transform-origin: center;
        }
        @supports (animation-timeline: scroll()) {
            .stApp::after { animation: art-node-scroll linear both; animation-timeline: scroll(root block); }
        }
        @keyframes ambient-field {
            from { transform: translate3d(-1.2%, -0.8%, 0) scale(1.035); opacity: .58; }
            to { transform: translate3d(1.4%, 1.1%, 0) scale(1.075); opacity: .84; }
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
            padding: 7rem 1rem 8rem;
            text-align: center;
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
            max-width: 10ch;
            margin: 0 !important;
            color: var(--ink) !important;
            font-size: clamp(3.4rem, 7.2vw, 7.4rem) !important;
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
        .hero-actions { display: flex; gap: 1.3rem; align-items: center; justify-content: center; margin-top: 2rem; }
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
            gap: clamp(0.85rem, 2vw, 2.4rem) !important;
            min-height: 3.6rem;
            padding: 0 !important;
            border-bottom: 1px solid var(--line);
            background: transparent !important;
        }
        .stTabs [data-baseweb="tab"] {
            min-height: 3.6rem;
            padding: 0.45rem 0.05rem !important;
            border: 0 !important;
            border-radius: 0 !important;
            background: transparent !important;
            color: var(--ink-soft) !important;
            font-weight: 600;
            transition: color 160ms ease, transform 160ms ease;
        }
        .stTabs [data-baseweb="tab"]:hover { color: var(--ink) !important; transform: translateY(-1px); }
        .stTabs [aria-selected="true"] { color: var(--ink) !important; }
        .stTabs [data-baseweb="tab-highlight"] { background: var(--accent) !important; height: 2px !important; }
        .stTabs [data-baseweb="tab-border"] { display: none; }

        [data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--line) !important;
            border-radius: var(--radius-panel) !important;
            background: rgba(252, 252, 248, 0.84) !important;
            box-shadow: 0 1px 0 rgba(255, 255, 255, 0.88) inset;
        }
        [data-testid="stMetric"] {
            padding: 1rem 1.1rem !important;
            border-left: 1px solid var(--line);
            background: transparent !important;
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
            background: rgba(252, 252, 248, 0.92) !important;
            box-shadow: var(--shadow-soft);
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
            transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease, background-color 160ms ease !important;
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
            transition: background-color 150ms ease, color 150ms ease, box-shadow 150ms ease;
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
            background: rgba(252, 252, 248, 0.90) !important;
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
                rgba(252,252,248,.72);
        }
        .data-empty-state strong { color: var(--ink); font-size: 1.35rem; }
        .data-empty-state span { color: var(--ink-soft); }
        [data-testid="stHorizontalBlock"]:has(.research-brand) {
            align-items: center !important;
        }
        [data-testid="stHorizontalBlock"]:has(.research-brand) [data-testid="stPopoverButton"],
        [data-testid="stHorizontalBlock"]:has(.research-brand) div[data-baseweb="select"] > div {
            min-height: 2.35rem !important;
            height: 2.35rem !important;
            padding-inline: .65rem !important;
            font-size: .78rem !important;
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
                grid-template-columns: minmax(7.8rem, 1fr) 4.1rem 5.5rem !important;
                gap: 0.55rem !important;
                align-items: center !important;
            }
            [data-testid="stHorizontalBlock"]:has(.research-brand) > [data-testid="stColumn"] {
                width: auto !important;
                min-width: 0 !important;
            }
            [data-testid="stHorizontalBlock"]:has(.research-brand) [data-testid="stPopoverButton"] {
                min-height: 2.55rem !important;
                padding-inline: 0.7rem !important;
                font-size: 0.75rem !important;
                white-space: nowrap;
            }
            [data-testid="stHorizontalBlock"]:has(.research-brand) div[data-baseweb="select"] > div {
                min-height: 2.55rem !important;
            }
            [data-testid="stHorizontalBlock"]:has(.research-brand) div[data-baseweb="select"] {
                min-width: 5.5rem !important;
            }
            .research-brand { margin: 0; font-size: 1.05rem; }
            .research-brand-mark { width: 1.7rem; height: 1.7rem; }
            .hero-copy { min-height: 72vh; padding: 5rem 0 5.5rem; }
            .hero-copy h1 { max-width: 12ch; font-size: clamp(2.8rem, 12vw, 4.4rem) !important; }
            .stTabs [data-baseweb="tab-list"] { gap: 1rem !important; overflow-x: auto; }
            .stTabs [data-baseweb="tab"] { white-space: nowrap; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
