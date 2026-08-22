"""The single visual system for the Streamlit oil research workspace."""

from __future__ import annotations

import streamlit as st


def apply_design_system() -> None:
    """Render a bright, responsive and motion-aware product design system."""
    st.markdown(
        """
        <style>
        :root {
            --canvas: #f4f8f7;
            --canvas-deep: #eaf2f0;
            --surface: #fbfdfc;
            --surface-glass: rgba(251, 253, 252, .82);
            --surface-muted: #edf4f2;
            --ink: #102622;
            --ink-soft: #62736f;
            --line: rgba(42, 91, 82, .14);
            --line-strong: rgba(42, 91, 82, .24);
            --teal: #24796d;
            --teal-deep: #155c54;
            --teal-soft: #dceee9;
            --blue: #6eafc6;
            --blue-soft: #e0f0f5;
            --lime: #afcf63;
            --amber: #e8b45b;
            --danger: #c85d52;
            --radius-control: 14px;
            --radius-card: 22px;
            --radius-panel: 30px;
            --shadow-float: 0 24px 70px rgba(26, 67, 59, .09);
            --shadow-control: 0 10px 30px rgba(26, 67, 59, .07);
            --font-sans: "Aptos", "Segoe UI Variable", "PingFang SC", "Microsoft YaHei UI", sans-serif;
            --font-display: "Bahnschrift", "Aptos Display", "Segoe UI Variable Display", "PingFang SC", "Microsoft YaHei UI", sans-serif;
        }

        html { scroll-behavior: smooth; background: var(--canvas); }
        body { overflow-x: hidden; background: var(--canvas); }
        html, body, .stApp, [data-testid="stAppViewContainer"],
        [data-testid="stMain"], [data-testid="stMainBlockContainer"] {
            color: var(--ink) !important;
            color-scheme: light !important;
            font-family: var(--font-sans) !important;
        }
        .stApp {
            isolation: isolate;
            background:
                radial-gradient(58rem 42rem at -8% 4%, rgba(110,175,198,.20), transparent 66%),
                radial-gradient(50rem 44rem at 105% 24%, rgba(175,207,99,.13), transparent 68%),
                linear-gradient(145deg, #f8fbfa 0%, var(--canvas) 42%, #eef6f4 100%) !important;
        }
        .stApp::before {
            content: "";
            position: fixed;
            inset: -20%;
            z-index: 0;
            pointer-events: none;
            background:
                radial-gradient(34rem 24rem at 22% 31%, rgba(36,121,109,.14), transparent 72%),
                radial-gradient(28rem 30rem at 72% 18%, rgba(110,175,198,.18), transparent 70%),
                radial-gradient(35rem 29rem at 63% 77%, rgba(175,207,99,.10), transparent 72%);
            filter: blur(34px) saturate(112%);
            transform: translate3d(-2%, -1%, 0) scale(1.03);
            transform-origin: center;
            animation: ambient-drift 18s cubic-bezier(.45,.05,.25,1) infinite alternate;
        }
        .stApp::after {
            content: "";
            position: fixed;
            inset: 0;
            z-index: 0;
            pointer-events: none;
            background-image:
                radial-gradient(circle, rgba(36,121,109,.17) 0 .7px, transparent .85px),
                linear-gradient(112deg, transparent 0 45%, rgba(255,255,255,.64) 49%, transparent 54%);
            background-position: 0 0, center;
            background-size: 7px 7px, cover;
            mask-image: linear-gradient(to bottom, rgba(0,0,0,.75), rgba(0,0,0,.16) 75%, transparent);
            opacity: .27;
            transform: translate3d(0, -1%, 0);
            animation: node-drift 24s cubic-bezier(.45,.05,.25,1) infinite alternate;
        }
        @keyframes ambient-drift {
            to { transform: translate3d(3%, 2%, 0) scale(1.10) rotate(1deg); }
        }
        @keyframes node-drift {
            to { transform: translate3d(-1.8%, 2.8%, 0) scale(1.035); opacity: .40; }
        }
        .stApp > [data-testid="stAppViewContainer"],
        [data-testid="stMain"], [data-testid="stMainBlockContainer"] {
            position: relative;
            z-index: 1;
            background: transparent !important;
        }
        [data-testid="stHeader"] { height: 0 !important; min-height: 0 !important; background: transparent !important; }
        [data-testid="stToolbar"], [data-testid="stDecoration"] { visibility: hidden !important; }
        .block-container {
            position: relative;
            z-index: 1;
            max-width: 1480px !important;
            padding: 1.25rem 3rem 6rem !important;
        }
        #MainMenu, footer { visibility: hidden; }
        [data-testid="stSidebar"] { border-right: 1px solid var(--line); background: rgba(251,253,252,.95) !important; }

        h1, h2, h3, h4, h5, h6, p, label, span, small,
        [data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] * { color: inherit; }
        h1, h2, h3 { text-wrap: balance; }
        h1, h2, h3, [id] { scroll-margin-top: 1.5rem; }
        h1, h2 { font-family: var(--font-display) !important; font-weight: 660 !important; }
        h1 { letter-spacing: -.055em !important; }
        h2 { letter-spacing: -.04em !important; }
        h3, h4, h5, h6 { letter-spacing: -.018em !important; }
        p { text-wrap: pretty; }
        a { color: var(--teal-deep) !important; text-underline-offset: .22em; }
        hr { border-color: var(--line) !important; }
        .skip-link {
            position: fixed;
            top: .75rem;
            left: .75rem;
            z-index: 80;
            padding: .7rem .9rem;
            border-radius: 12px;
            background: var(--ink);
            color: #fff !important;
            transform: translateY(-170%);
            transition: transform 150ms ease;
        }
        .skip-link:focus-visible { transform: translateY(0); }

        /* Brand / the only mode switch / API and language. */
        [data-testid="stHorizontalBlock"]:has(.research-brand) {
            display: grid !important;
            grid-template-columns: minmax(12rem, 1fr) minmax(17rem, .72fr) minmax(10.8rem, 1fr) !important;
            gap: 1rem !important;
            align-items: center !important;
            min-height: 3.4rem;
        }
        [data-testid="stHorizontalBlock"]:has(.research-brand) > [data-testid="stColumn"] { width: auto !important; min-width: 0 !important; }
        .research-brand {
            display: flex;
            align-items: center;
            gap: .7rem;
            min-height: 2.75rem;
            color: var(--ink);
            font-family: var(--font-display);
            font-size: 1.1rem;
            font-weight: 720;
            letter-spacing: -.02em;
            white-space: nowrap;
        }
        .research-brand-mark {
            position: relative;
            width: 1.9rem;
            height: 1.9rem;
            flex: 0 0 1.9rem;
            border: 1.5px solid var(--teal);
            border-radius: 56% 44% 60% 40% / 64% 46% 54% 36%;
            transform: rotate(42deg);
            animation: brand-morph 5s ease-in-out infinite alternate;
        }
        .research-brand-mark::before, .research-brand-mark::after {
            content: "";
            position: absolute;
            border: 1px solid rgba(36,121,109,.72);
            border-radius: 50%;
        }
        .research-brand-mark::before { inset: .34rem; }
        .research-brand-mark::after { inset: .65rem; background: var(--teal); }
        .research-brand-mark > i { display: none; }
        @keyframes brand-morph {
            to { transform: rotate(57deg) scale(1.055); border-radius: 42% 58% 39% 61% / 48% 62% 38% 52%; }
        }
        .mode-dock-anchor, .tool-dock-anchor { display: none; }
        [data-testid="stElementContainer"]:has(.mode-dock-anchor),
        [data-testid="stElementContainer"]:has(.tool-dock-anchor) { display: none !important; }
        [data-testid="stColumn"]:has(.mode-dock-anchor) {
            justify-self: center;
            width: 100% !important;
            max-width: 22rem !important;
        }
        .st-key-primary_workspace_mode { width: 100% !important; }
        [data-testid="stColumn"]:has(.mode-dock-anchor) [data-testid="stButtonGroup"] { width: 100%; }
        [data-testid="stColumn"]:has(.mode-dock-anchor) [data-baseweb="button-group"] {
            display: grid !important;
            grid-template-columns: 1fr 1fr;
            width: 100% !important;
            padding: .25rem;
            border: 1px solid var(--line);
            border-radius: 16px;
            background: rgba(234,243,240,.76);
            box-shadow: inset 0 1px 0 rgba(255,255,255,.8);
            backdrop-filter: blur(18px) saturate(120%);
        }
        [data-testid="stColumn"]:has(.mode-dock-anchor) [data-baseweb="button-group"] > button {
            min-width: 0 !important;
            min-height: 2.45rem !important;
            padding: .55rem .8rem !important;
            border: 0 !important;
            border-radius: 12px !important;
            background: transparent !important;
            color: var(--ink-soft) !important;
            box-shadow: none !important;
            font-weight: 660 !important;
            transition: transform 160ms cubic-bezier(.2,.7,.2,1), background-color 160ms ease, color 160ms ease, box-shadow 160ms ease !important;
        }
        [data-testid="stColumn"]:has(.mode-dock-anchor) [data-testid="stBaseButton-segmented_controlActive"] {
            background: var(--surface) !important;
            color: var(--teal-deep) !important;
            box-shadow: 0 7px 20px rgba(26,67,59,.09) !important;
        }
        [data-testid="stColumn"]:has(.mode-dock-anchor) [data-baseweb="button-group"] > button:hover {
            transform: translateY(-1px);
            color: var(--ink) !important;
        }
        [data-testid="stColumn"]:has(.tool-dock-anchor) {
            justify-self: end;
            width: 9rem !important;
            max-width: 9rem !important;
            min-width: 9rem !important;
        }
        [data-testid="stColumn"]:has(.tool-dock-anchor) > [data-testid="stVerticalBlock"] { min-height: 0 !important; gap: 0 !important; }
        [data-testid="stColumn"]:has(.tool-dock-anchor) > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"] {
            height: 2.9rem !important;
            min-height: 2.8rem !important;
            max-height: 2.9rem !important;
            align-self: center !important;
            padding: .22rem !important;
            border: 1px solid var(--line);
            border-radius: 16px;
            background: var(--surface-glass);
            box-shadow: var(--shadow-control), inset 0 1px 0 rgba(255,255,255,.9);
            backdrop-filter: blur(20px) saturate(125%);
            overflow: visible !important;
        }
        [data-testid="stColumn"]:has(.tool-dock-anchor) [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"] {
            width: 100% !important;
            min-height: 2.35rem !important;
            height: 2.35rem !important;
            align-self: center !important;
        }
        [data-testid="stColumn"]:has(.tool-dock-anchor) [data-testid="stHorizontalBlock"] {
            display: grid !important;
            grid-template-columns: minmax(5.25rem, 1fr) minmax(3rem, .56fr) !important;
            gap: .18rem !important;
            width: 100% !important;
            align-items: center !important;
        }
        [data-testid="stColumn"]:has(.tool-dock-anchor) [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
            width: auto !important;
            min-width: 0 !important;
            padding: 0 !important;
            overflow: visible !important;
        }
        [data-testid="stColumn"]:has(.tool-dock-anchor) [data-testid="stElementContainer"],
        [data-testid="stColumn"]:has(.tool-dock-anchor) [data-testid="stPopover"] {
            width: 100% !important;
            min-width: 0 !important;
            max-width: none !important;
        }
        [data-testid="stColumn"]:has(.tool-dock-anchor) [data-testid="stPopoverButton"],
        [data-testid="stColumn"]:has(.tool-dock-anchor) [data-testid="stPopover"] > button,
        [data-testid="stColumn"]:has(.tool-dock-anchor) [data-testid="stHorizontalBlock"] button {
            width: 100% !important;
            min-width: 0 !important;
            min-height: 2.35rem !important;
            height: 2.35rem !important;
            padding-inline: .62rem !important;
            border: 0 !important;
            border-radius: 11px !important;
            background: transparent !important;
            color: var(--ink) !important;
            box-shadow: none !important;
            font-size: .82rem !important;
            white-space: nowrap !important;
        }
        [data-testid="stColumn"]:has(.tool-dock-anchor) [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2) button {
            border-left: 1px solid var(--line) !important;
            border-radius: 0 11px 11px 0 !important;
        }
        [data-testid="stColumn"]:has(.tool-dock-anchor) [data-testid="stMarkdownContainer"] p { white-space: nowrap; }

        /* The hero is the animated data field; there is no detached decoration. */
        .product-hero {
            position: relative;
            min-height: clamp(32rem, 66dvh, 47rem);
            display: grid;
            align-items: center;
            margin: 1rem 0 1.6rem;
            overflow: hidden;
            border-block: 1px solid var(--line);
            isolation: isolate;
        }
        .product-hero::before {
            content: "";
            position: absolute;
            z-index: -1;
            width: min(49vw, 42rem);
            aspect-ratio: 1;
            right: -4%;
            top: 7%;
            border-radius: 50%;
            background: radial-gradient(circle at 42% 38%, rgba(255,255,255,.95), rgba(110,175,198,.20) 36%, rgba(36,121,109,.10) 54%, transparent 72%);
            filter: blur(3px);
            opacity: .88;
            animation: signal-orbit 10s ease-in-out infinite alternate;
        }
        @keyframes signal-orbit { to { transform: translate3d(-5%, 4%, 0) scale(1.08); opacity: .68; } }
        .hero-data-field { position: absolute; inset: 0; z-index: -1; pointer-events: none; }
        .hero-data-field svg { width: 100%; height: 100%; overflow: visible; }
        .hero-data-field .flow {
            fill: none;
            stroke: var(--teal);
            stroke-width: 1.2;
            stroke-linecap: round;
            opacity: .21;
            stroke-dasharray: 7 12;
            animation: flow-travel 12s linear infinite;
        }
        .hero-data-field .flow-b { stroke: var(--blue); animation-duration: 16s; animation-direction: reverse; }
        .hero-data-field .flow-c { stroke: var(--lime); animation-duration: 20s; }
        .hero-data-field .node {
            fill: var(--surface);
            stroke: var(--teal);
            stroke-width: 2;
            opacity: .8;
            transform-origin: center;
            animation: node-pulse 3.8s ease-in-out infinite alternate;
        }
        .hero-data-field .node-b { stroke: var(--blue); animation-delay: -1.2s; }
        .hero-data-field .node-c { stroke: var(--lime); animation-delay: -2.2s; }
        @keyframes flow-travel { to { stroke-dashoffset: -190; } }
        @keyframes node-pulse { to { opacity: .34; transform: scale(.72); } }
        .hero-content {
            width: min(54rem, 74%);
            padding: clamp(4.2rem, 9vh, 7rem) clamp(.3rem, 2vw, 2rem);
            animation: reveal-up 620ms cubic-bezier(.22,.72,.2,1) both;
        }
        .hero-kicker, .section-kicker {
            margin: 0 0 1rem !important;
            color: var(--teal-deep) !important;
            font-size: .75rem !important;
            font-weight: 760 !important;
            letter-spacing: .15em !important;
            text-transform: uppercase;
        }
        .hero-content h1 {
            max-width: 11.5ch;
            margin: 0 !important;
            color: var(--ink) !important;
            font-size: clamp(3.2rem, 6.4vw, 6.4rem) !important;
            line-height: .98 !important;
        }
        .hero-content > p:not(.hero-kicker) {
            max-width: 43rem;
            margin: 1.55rem 0 0 !important;
            color: var(--ink-soft) !important;
            font-size: clamp(1rem, 1.3vw, 1.15rem) !important;
            line-height: 1.78 !important;
        }
        .hero-actions { display: flex; align-items: center; gap: 1rem; margin-top: 2rem; }
        .hero-action-primary {
            display: inline-flex;
            align-items: center;
            gap: .8rem;
            min-height: 3rem;
            padding: .76rem 1.15rem;
            border-radius: var(--radius-control);
            background: var(--ink);
            color: #f7fbfa !important;
            font-weight: 690;
            text-decoration: none;
            box-shadow: 0 14px 32px rgba(16,38,34,.17);
            transition: transform 170ms cubic-bezier(.2,.7,.2,1), box-shadow 170ms ease, background-color 170ms ease;
        }
        .hero-action-primary:hover { transform: translateY(-2px); background: var(--teal-deep); box-shadow: 0 18px 38px rgba(16,38,34,.21); }
        .hero-action-primary span { color: inherit; }
        .hero-sequence {
            display: flex;
            align-items: center;
            gap: .72rem;
            margin-top: 3rem;
            color: var(--ink-soft);
            font-size: .78rem;
            font-weight: 650;
            letter-spacing: .025em;
        }
        .hero-sequence i {
            width: clamp(.8rem, 2.2vw, 2.2rem);
            height: 1px;
            background: linear-gradient(90deg, var(--line-strong), rgba(110,175,198,.45));
        }
        .professional-content-anchor { height: .25rem; }

        /* Editorial sections, cards and charts. */
        .section-intro, .decision-hero, .data-library-intro {
            margin: 3.25rem 0 1.6rem;
            padding: 0 !important;
            border: 0 !important;
            background: transparent !important;
            box-shadow: none !important;
        }
        .professional-intro { margin-top: 2rem; }
        .section-intro h2, .decision-hero h2, .data-library-intro h2 {
            max-width: 20ch;
            margin: .25rem 0 .85rem !important;
            color: var(--ink) !important;
            font-size: clamp(2rem, 3.5vw, 3.6rem) !important;
            line-height: 1.08 !important;
        }
        .decision-hero span, .data-library-intro span { color: var(--teal-deep) !important; font-size: .74rem; font-weight: 760; letter-spacing: .13em; }
        .section-intro p, .decision-hero p, .data-library-intro p {
            max-width: 54rem;
            margin: 0 !important;
            color: var(--ink-soft) !important;
            font-size: 1rem !important;
            line-height: 1.78 !important;
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--line) !important;
            border-radius: var(--radius-panel) !important;
            background: var(--surface-glass) !important;
            box-shadow: inset 0 1px 0 rgba(255,255,255,.88), 0 18px 54px rgba(26,67,59,.045);
            backdrop-filter: blur(16px) saturate(112%);
        }
        [data-testid="stMetric"] {
            min-width: 0;
            padding: 1rem 1.05rem !important;
            border: 1px solid var(--line);
            border-radius: 18px;
            background: var(--surface-glass) !important;
            box-shadow: 0 10px 30px rgba(26,67,59,.045);
        }
        [data-testid="stMetricLabel"] { color: var(--ink-soft) !important; }
        [data-testid="stMetricValue"] { color: var(--ink) !important; font-variant-numeric: tabular-nums; letter-spacing: -.035em; }
        [data-testid="stDataFrame"], [data-testid="stTable"], [data-testid="stPlotlyChart"] {
            width: 100% !important;
            max-width: 100% !important;
            overflow: hidden;
            border: 1px solid var(--line) !important;
            border-radius: var(--radius-panel) !important;
            background: rgba(251,253,252,.94) !important;
            box-shadow: var(--shadow-float);
        }
        [data-testid="stPlotlyChart"] { padding: .38rem; }
        [data-testid="stPlotlyChart"] > div, [data-testid="stPlotlyChart"] .js-plotly-plot,
        [data-testid="stPlotlyChart"] .plot-container { width: 100% !important; max-width: 100% !important; }
        .decision-summary, .investment-card, .hedge-card, .source-audit-card,
        .data-result-card, .forecast-summary {
            border: 1px solid var(--line) !important;
            border-radius: var(--radius-panel) !important;
            background: var(--surface-glass) !important;
            box-shadow: var(--shadow-float) !important;
        }
        .data-empty-state {
            min-height: 13rem;
            display: grid;
            align-content: center;
            gap: .55rem;
            margin: 1.2rem 0 2.5rem;
            padding: 2rem;
            border: 1px dashed var(--line-strong);
            border-radius: var(--radius-panel);
            background: radial-gradient(circle at 16% 28%, rgba(110,175,198,.13), transparent 20rem), var(--surface-glass);
        }
        .data-empty-state strong { color: var(--ink); font-size: 1.3rem; }
        .data-empty-state span { color: var(--ink-soft); }
        .deferred-results-note {
            margin: 1.5rem 0 .8rem;
            padding: 1.25rem 1.4rem;
            border-left: 3px solid var(--teal);
            border-radius: 4px 18px 18px 4px;
            background: rgba(220,238,233,.62);
        }

        /* Controls. */
        div[data-baseweb="select"] > div, div[data-baseweb="base-input"], div[data-baseweb="input"] > div,
        div[data-baseweb="textarea"] > div, [data-testid="stTextInput"] input,
        [data-testid="stNumberInput"] input, [data-testid="stDateInput"] input {
            min-height: 2.9rem !important;
            border-color: var(--line-strong) !important;
            border-radius: var(--radius-control) !important;
            background: var(--surface) !important;
            color: var(--ink) !important;
            box-shadow: none !important;
        }
        div[data-baseweb="select"] *, div[data-baseweb="base-input"] *, [data-testid="stTextInput"] input::placeholder { color: var(--ink-soft) !important; }
        [data-baseweb="popover"], [data-baseweb="menu"], [role="listbox"] {
            border-color: var(--line) !important;
            border-radius: 16px !important;
            background: var(--surface) !important;
            color: var(--ink) !important;
            box-shadow: var(--shadow-float) !important;
        }
        [role="option"] { background: var(--surface) !important; color: var(--ink) !important; }
        [role="option"]:hover, [aria-selected="true"][role="option"] { background: var(--teal-soft) !important; }
        [data-baseweb="tag"] { border: 1px solid rgba(36,121,109,.18) !important; border-radius: 10px !important; background: var(--teal-soft) !important; color: var(--ink) !important; }
        [data-baseweb="tag"] * { color: var(--ink) !important; }
        .stSelectbox label, .stMultiSelect label, .stTextInput label,
        .stNumberInput label, .stDateInput label, .stRadio label { color: var(--ink-soft) !important; font-size: .86rem !important; font-weight: 580 !important; }
        .stButton > button, .stDownloadButton > button, [data-testid="baseButton-secondary"],
        [data-testid="baseButton-primary"], [data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-primary"] {
            min-height: 2.9rem !important;
            padding: .68rem 1.05rem !important;
            border: 1px solid var(--line-strong) !important;
            border-radius: var(--radius-control) !important;
            background: var(--surface) !important;
            color: var(--ink) !important;
            font-weight: 660 !important;
            box-shadow: none !important;
            transition: transform 160ms cubic-bezier(.2,.7,.2,1), border-color 160ms ease, box-shadow 160ms ease, background-color 160ms ease !important;
            touch-action: manipulation;
        }
        .stButton > button:hover, .stDownloadButton > button:hover { transform: translateY(-1px); border-color: var(--teal) !important; box-shadow: var(--shadow-control) !important; }
        .stButton > button[data-testid="stBaseButton-primary"], .stDownloadButton > button[data-testid="stBaseButton-primary"] {
            border-color: var(--teal-deep) !important;
            background: var(--teal-deep) !important;
            color: #fff !important;
        }
        .stButton > button[data-testid="stBaseButton-primary"] *, .stDownloadButton > button[data-testid="stBaseButton-primary"] * { color: #fff !important; }
        button:focus-visible, [role="tab"]:focus-visible, input:focus-visible,
        [role="combobox"]:focus-visible, [role="radio"]:focus-visible, a:focus-visible { outline: 3px solid rgba(110,175,198,.45) !important; outline-offset: 2px !important; }
        [data-testid="stRadio"] [role="radiogroup"] {
            display: inline-flex !important;
            gap: .25rem !important;
            padding: .25rem !important;
            border: 1px solid var(--line) !important;
            border-radius: 14px !important;
            background: var(--surface-muted) !important;
        }
        [data-testid="stRadio"] [role="radiogroup"] > label {
            min-height: 2.35rem;
            margin: 0 !important;
            padding: .48rem .82rem !important;
            border-radius: 10px !important;
            background: transparent !important;
            color: var(--ink-soft) !important;
        }
        [data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked) { background: var(--surface) !important; color: var(--ink) !important; box-shadow: 0 4px 12px rgba(26,67,59,.08); }
        [data-testid="stRadio"] [role="radiogroup"] > label > div:first-child { display: none !important; }
        [data-testid="stSlider"] [data-testid="stSliderThumbValue"] {
            width: max-content !important;
            min-width: max-content !important;
            max-width: none !important;
            overflow: visible !important;
            white-space: nowrap !important;
        }
        [data-testid="stSlider"] [data-testid="stSliderThumbValue"] p,
        [data-testid="stSlider"] [data-testid="stSliderThumbValue"] span {
            width: max-content !important;
            min-width: max-content !important;
            margin: 0 !important;
            overflow: visible !important;
            white-space: nowrap !important;
            font-variant-numeric: tabular-nums;
        }
        [data-testid="stAlert"] { border: 1px solid var(--line) !important; border-radius: 17px !important; background: rgba(220,238,233,.72) !important; color: var(--ink) !important; }
        [data-testid="stAlert"] * { color: var(--ink) !important; }
        [data-testid="stExpander"] { overflow: hidden; border: 1px solid var(--line) !important; border-radius: 17px !important; background: var(--surface-glass) !important; }
        [data-testid="stPopoverButton"], [data-testid="stPopover"] > button,
        [data-testid="stPopover"] button[data-testid^="baseButton"] {
            min-height: 2.75rem !important;
            border: 1px solid var(--line) !important;
            border-radius: var(--radius-control) !important;
            background: var(--surface-glass) !important;
            color: var(--ink) !important;
            box-shadow: none !important;
        }
        [data-testid="stPopoverButton"] *, [data-testid="stPopover"] button * { color: var(--ink) !important; }
        [data-testid="stStatusWidget"], [data-testid="stFileUploaderDropzone"] { border-color: var(--line) !important; border-radius: 17px !important; background: var(--surface-glass) !important; }
        .stTabs [data-baseweb="tab-list"] {
            gap: .18rem !important;
            width: fit-content;
            max-width: 100%;
            min-height: 3.2rem;
            padding: .3rem !important;
            overflow-x: auto;
            border: 1px solid var(--line);
            border-radius: 16px !important;
            background: rgba(234,243,240,.78) !important;
            backdrop-filter: blur(16px);
        }
        .stTabs [data-baseweb="tab"] { min-height: 2.55rem; padding: .5rem .9rem !important; border: 0 !important; border-radius: 11px !important; background: transparent !important; color: var(--ink-soft) !important; font-weight: 620; white-space: nowrap; }
        .stTabs [aria-selected="true"] { background: var(--surface) !important; color: var(--teal-deep) !important; box-shadow: 0 5px 16px rgba(26,67,59,.08); }
        .stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display: none !important; }
        .st-key-professional_workspace_mode [data-baseweb="button-group"] {
            display: grid !important;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            width: min(100%, 42rem) !important;
            padding: .25rem;
            gap: .18rem;
            border: 1px solid var(--line);
            border-radius: 16px;
            background: rgba(234,243,240,.78);
        }
        .st-key-professional_workspace_mode [data-baseweb="button-group"] > button {
            min-width: 0 !important;
            border: 0 !important;
            border-radius: 11px !important;
            white-space: nowrap;
        }

        @keyframes reveal-up {
            from { opacity: 0; transform: translate3d(0, 15px, 0); }
            to { opacity: 1; transform: translate3d(0, 0, 0); }
        }
        @supports (animation-timeline: view()) {
            .view-reveal { animation: section-enter linear both; animation-timeline: view(); animation-range: entry 3% cover 25%; }
        }
        @keyframes section-enter {
            from { opacity: .25; transform: translate3d(0, 2rem, 0); }
            to { opacity: 1; transform: translate3d(0, 0, 0); }
        }

        @media (max-width: 900px) {
            .block-container { padding: 1rem 1.3rem 5rem !important; }
            [data-testid="stHorizontalBlock"]:has(.research-brand) { grid-template-columns: minmax(8.5rem, 1fr) 9rem !important; gap: .65rem !important; }
            [data-testid="stHorizontalBlock"]:has(.research-brand) > [data-testid="stColumn"]:nth-child(2) {
                grid-column: 1 / -1;
                grid-row: 2;
                justify-self: center;
                width: min(100%, 22rem) !important;
            }
            [data-testid="stHorizontalBlock"]:has(.research-brand) > [data-testid="stColumn"]:nth-child(3) { grid-column: 2; grid-row: 1; }
            [data-testid="stColumn"]:has(.tool-dock-anchor) { width: 9rem !important; min-width: 9rem !important; max-width: 9rem !important; }
            [data-testid="stColumn"]:has(.tool-dock-anchor) [data-testid="stHorizontalBlock"] { grid-template-columns: minmax(5.2rem, 1fr) minmax(3rem, .56fr) !important; }
            .product-hero { min-height: 34rem; margin-top: .75rem; }
            .hero-content { width: min(42rem, 87%); padding-inline: .2rem; }
            .hero-content h1 { font-size: clamp(3rem, 10vw, 5.3rem) !important; }
            .product-hero::before { width: min(68vw, 34rem); right: -15%; top: 22%; }
        }
        @media (max-width: 600px) {
            .block-container { padding: .8rem .85rem 4rem !important; }
            [data-testid="stHorizontalBlock"]:has(.research-brand) { grid-template-columns: minmax(7.2rem, 1fr) 8.75rem !important; gap: .45rem !important; }
            [data-testid="stColumn"]:has(.tool-dock-anchor) { width: 8.75rem !important; min-width: 8.75rem !important; max-width: 8.75rem !important; }
            .research-brand { gap: .5rem; font-size: .96rem; }
            .research-brand-mark { width: 1.55rem; height: 1.55rem; flex-basis: 1.55rem; }
            [data-testid="stColumn"]:has(.tool-dock-anchor) > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"] { min-height: 2.65rem !important; }
            [data-testid="stColumn"]:has(.tool-dock-anchor) [data-testid="stHorizontalBlock"] { grid-template-columns: minmax(5rem, 1fr) minmax(2.9rem, .55fr) !important; }
            [data-testid="stColumn"]:has(.tool-dock-anchor) [data-testid="stPopoverButton"],
            [data-testid="stColumn"]:has(.tool-dock-anchor) [data-testid="stPopover"] > button,
            [data-testid="stColumn"]:has(.tool-dock-anchor) [data-testid="stHorizontalBlock"] button {
                min-height: 2.2rem !important;
                height: 2.2rem !important;
                padding-inline: .48rem !important;
                font-size: .78rem !important;
            }
            .product-hero { min-height: 32rem; }
            .hero-content { width: 94%; padding-block: 4.4rem; }
            .hero-content h1 { max-width: 9.5ch; font-size: clamp(2.75rem, 13.5vw, 4.2rem) !important; }
            .hero-content > p:not(.hero-kicker) { max-width: 32rem; line-height: 1.68 !important; }
            .hero-sequence { gap: .42rem; overflow: hidden; font-size: .7rem; }
            .hero-sequence i { width: .65rem; flex: 0 1 .65rem; }
            .section-intro, .decision-hero, .data-library-intro { margin-top: 2.35rem; }
            [data-testid="stMetric"] { padding: .85rem .9rem !important; }
            .stTabs [data-baseweb="tab-list"] {
                display: grid !important;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                width: 100%;
                overflow: visible;
            }
            .stTabs [data-baseweb="tab"] {
                width: 100%;
                justify-content: center;
            }
            .st-key-professional_workspace_mode [data-baseweb="button-group"] {
                grid-template-columns: repeat(2, minmax(0, 1fr));
                width: 100% !important;
            }
        }
        @media (max-width: 390px) {
            .block-container { padding-inline: .7rem !important; }
            [data-testid="stHorizontalBlock"]:has(.research-brand) { grid-template-columns: minmax(6.7rem, 1fr) 8.6rem !important; }
            [data-testid="stColumn"]:has(.tool-dock-anchor) { width: 8.6rem !important; min-width: 8.6rem !important; max-width: 8.6rem !important; }
            [data-testid="stColumn"]:has(.tool-dock-anchor) [data-testid="stHorizontalBlock"] { grid-template-columns: minmax(4.9rem, 1fr) minmax(2.85rem, .55fr) !important; }
            .research-brand { font-size: .88rem; }
            .hero-content h1 { font-size: clamp(2.55rem, 13.2vw, 3.45rem) !important; }
            .hero-sequence span:nth-of-type(2), .hero-sequence i:nth-of-type(2) { display: none; }
        }
        @media (prefers-reduced-motion: reduce) {
            html { scroll-behavior: auto; }
            *, *::before, *::after {
                animation-duration: .01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: .01ms !important;
            }
            .stApp::before, .stApp::after, .product-hero::before { transform: none !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
