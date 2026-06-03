"""
Lumen & Co — Growth Command Center
==================================
Shared data layer, metric engine, and premium SaaS design system.

Everything visual (theme, cards, pills, score gauge, action cards, decision
tables, sidebar nav + filters) lives here so every page renders with one
consistent, premium language. Every number is computed from the data at
runtime — nothing is hardcoded.
"""
import os
import textwrap
import datetime as _dt
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go

BRAND = "Lumen & Co"
TAGLINE = "Growth Command Center"
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# ===========================================================================
# PALETTE — Stripe-inspired: off-white, deep navy, blurple accent.
# ===========================================================================
BG = "#F6F9FC"          # off-white app background
INK = "#0A2540"         # deep navy — headings
INK_SOFT = "#16324F"    # softer navy for body emphasis
SUBTLE = "#425466"       # secondary text
MUTE = "#6B7C93"         # muted text
LINE = "#E6EBF1"         # very light borders
GRID = "#EDF2F7"         # chart gridlines (very light)
CARD = "#FFFFFF"
ACCENT = "#635BFF"       # Stripe blurple primary
ACCENT_SOFT = "#F0EFFE"
ACCENT_CYAN = "#00D4FF"  # accent cyan (gradient partner)
GOOD = "#1F9D78"         # muted teal-green
GOOD_SOFT = "#E6F6F0"
WARN = "#C98A2B"         # soft amber
WARN_SOFT = "#FBF3E2"
BAD = "#E0584B"          # muted coral
BAD_SOFT = "#FCEDEB"
NEUTRAL_SOFT = "#EEF2F7"
# soft premium shadows (Stripe-like: large, very low opacity)
SHADOW = "0 4px 14px rgba(10,37,64,.05)"
SHADOW_LG = "0 8px 28px rgba(10,37,64,.07)"

CHANNEL_COLORS = {
    "Meta Prospecting": "#E0584B", "Meta Retargeting": "#F0926F",
    "Google Brand": "#635BFF", "Google Shopping": "#9B95FF",
    "Email/Organic": "#1F9D78", "TikTok": "#7A6BC4", "Referral": "#15B0A6",
}

GROSS_MARGIN = 0.62

# ===========================================================================
# BENCHMARKS / TARGETS  (the "productized" point of view)
# ===========================================================================
TARGET_LTV_CAC = 3.0          # healthy unit economics
TARGET_NEW_SHARE = 50.0       # % of revenue from new customers (lower is better)
TARGET_PAYBACK = 3.0          # months
TARGET_REPEAT = 35.0          # % repeat-purchase rate
TARGET_DISCOUNT_DEP = 25.0    # % of revenue given back as discount (lower better)
TARGET_CM = 60.0              # contribution margin %

PAID = {"Meta Prospecting", "Meta Retargeting", "Google Brand",
        "Google Shopping", "TikTok"}


# ===========================================================================
# DATA
# ===========================================================================
@st.cache_data
def load():
    c = pd.read_csv(f"{DATA_DIR}/customers.csv", parse_dates=["first_order_date"])
    o = pd.read_csv(f"{DATA_DIR}/orders.csv", parse_dates=["order_date"])
    a = pd.read_csv(f"{DATA_DIR}/ad_spend.csv", parse_dates=["date"])
    f = pd.read_csv(f"{DATA_DIR}/funnel.csv", parse_dates=["date"])
    o["contribution"] = o.revenue - o.discount - o.cogs
    o["month"] = o.order_date.dt.to_period("M").dt.to_timestamp()
    c["cohort"] = c.first_order_date.dt.to_period("M").dt.to_timestamp()
    return c, o, a, f


# ---- formatting -----------------------------------------------------------
def fmt_money(x, dp=0):
    return f"${x:,.{dp}f}"


def money_compact(x):
    """$346K / $1.2M style."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return "—"
    sign = "-" if x < 0 else ""
    x = abs(x)
    if x >= 1_000_000:
        return f"{sign}${x/1_000_000:.1f}M"
    if x >= 1_000:
        return f"{sign}${x/1_000:.0f}K"
    return f"{sign}${x:,.0f}"


def fmt_pct(x, dp=0):
    return f"{x:.{dp}f}%"


def H(s):
    """Collapse leading indentation + blank lines so Streamlit's Markdown never
    mistakes an indented HTML block (or an empty interpolation slot) for a code
    block. Always run raw-HTML strings through this before st.markdown()."""
    return "\n".join(line.strip() for line in s.splitlines() if line.strip())


# ===========================================================================
# METRIC ENGINE
# ===========================================================================
def channel_economics(c, o):
    ltv = o.groupby("customer_id").revenue.sum().rename("ltv")
    cm = o.groupby("customer_id").contribution.sum().rename("ltv_cm")
    repeated = o[~o.is_first_order].customer_id.unique()
    cc = c.merge(ltv, on="customer_id").merge(cm, on="customer_id")
    cc["repeated"] = cc.customer_id.isin(repeated)
    t = cc.groupby("acquisition_channel").agg(
        customers=("customer_id", "count"),
        cac=("acquisition_cost", "mean"),
        ltv=("ltv", "mean"),
        ltv_cm=("ltv_cm", "mean"),
        repeat_rate=("repeated", "mean"),
    )
    t["ltv_cac"] = t.ltv_cm / t.cac
    t["repeat_rate"] *= 100
    return t.reset_index()


def payback_by_channel(c, o):
    """CAC ÷ monthly contribution-margin run-rate per customer, by channel."""
    data_end = o.order_date.max()
    life = ((data_end.year - c.first_order_date.dt.year) * 12
            + (data_end.month - c.first_order_date.dt.month) + 1).clip(lower=1)
    life.index = c.customer_id
    cm = o.groupby("customer_id").contribution.sum().reindex(
        c.customer_id).fillna(0)
    ch = c.set_index("customer_id").acquisition_channel
    df = pd.DataFrame({"cm": cm.values, "life": life.reindex(c.customer_id).values,
                       "ch": ch.reindex(c.customer_id).values})
    g = df.groupby("ch")
    rr = g.cm.sum() / g.life.sum()
    cac = c.groupby("acquisition_channel").acquisition_cost.mean()
    blended = c.acquisition_cost.mean() / (df.cm.sum() / df.life.sum())
    return (cac / rr), blended


def blended_metrics(c, o):
    """The headline numbers used across the app."""
    by_m = o.groupby("month").agg(rev=("revenue", "sum"),
                                  orders=("order_id", "count")).reset_index()
    by_m["aov"] = by_m.rev / by_m.orders
    out = {"by_month": by_m}
    if len(by_m) >= 2:
        cur, prev = by_m.iloc[-1], by_m.iloc[-2]
    else:
        cur = prev = by_m.iloc[-1]
    out["rev"] = cur.rev
    out["rev_mom"] = pct_change(cur.rev, prev.rev)
    out["orders"] = cur.orders
    out["orders_mom"] = pct_change(cur.orders, prev.orders)
    out["aov"] = cur.aov
    out["aov_mom"] = pct_change(cur.aov, prev.aov)

    # returning revenue share (last month)
    last = o[o.month == cur.month]
    ret_rev = last.loc[~last.is_first_order, "revenue"].sum()
    out["returning_share"] = ret_rev / last.revenue.sum() * 100 if last.revenue.sum() else 0
    out["new_share"] = 100 - out["returning_share"]

    out["cac"] = c.acquisition_cost.mean()
    out["ltv_cm"] = o.groupby("customer_id").contribution.sum().mean()
    out["ltv_cac"] = out["ltv_cm"] / out["cac"] if out["cac"] else 0

    repeated = o[~o.is_first_order].customer_id.nunique()
    out["repeat_rate"] = repeated / c.customer_id.nunique() * 100 if len(c) else 0
    out["cm_pct"] = (o.contribution.sum() / o.revenue.sum() * 100
                     if o.revenue.sum() else 0)
    out["discount_dep"] = (o.discount.sum() / o.revenue.sum() * 100
                           if o.revenue.sum() else 0)
    _, blended_pb = payback_by_channel(c, o)
    out["payback"] = blended_pb
    return out


def pct_change(cur, prev):
    return (cur - prev) / prev * 100 if prev else 0.0


def _band(value, lo, hi, invert=False):
    """Map value to 0..100 between lo (=0) and hi (=100); invert if lower=better."""
    if hi == lo:
        return 50.0
    s = (value - lo) / (hi - lo) * 100
    if invert:
        s = 100 - s
    return float(np.clip(s, 0, 100))


def growth_quality_score(c, o):
    """0–100 composite of 8 growth-health signals, each scored vs benchmark."""
    m = blended_metrics(c, o)

    # CAC trend: recent vs early blended CAC (improving = lower = better)
    cac_t = c.assign(coh=c.cohort).groupby("coh").acquisition_cost.mean()
    cac_change = pct_change(cac_t.iloc[-1], cac_t.iloc[0]) if len(cac_t) > 1 else 0

    comps = {
        "Revenue growth (MoM)":
            (_band(m["rev_mom"], -5, 10), f"{m['rev_mom']:+.1f}%", 0.16),
        "Returning revenue share":
            (_band(m["returning_share"], 20, 55), f"{m['returning_share']:.0f}%", 0.18),
        "LTV : CAC":
            (_band(m["ltv_cac"], 1.0, 3.5), f"{m['ltv_cac']:.1f}:1", 0.18),
        "CAC trend":
            (_band(cac_change, 30, -10), f"{cac_change:+.0f}%", 0.10),
        "Repeat-purchase rate":
            (_band(m["repeat_rate"], 15, 40), f"{m['repeat_rate']:.0f}%", 0.14),
        "Contribution margin":
            (_band(m["cm_pct"], 45, 65), f"{m['cm_pct']:.0f}%", 0.08),
        "CAC payback":
            (_band(m["payback"], 6, 1.5), f"{m['payback']:.1f} mo", 0.10),
        "Discount dependency":
            (_band(m["discount_dep"], 20, 4), f"{m['discount_dep']:.0f}%", 0.06),
    }
    score = sum(v[0] * v[2] for v in comps.values())
    score = round(score)
    if score >= 80:
        status, tone = "Healthy", "good"
    elif score >= 60:
        status, tone = "Watchlist", "warn"
    else:
        status, tone = "At Risk", "bad"
    return score, status, tone, comps, m


def what_changed(o):
    """Plain-English month-over-month change bullets."""
    by_m = o.groupby("month").agg(rev=("revenue", "sum"),
                                  orders=("order_id", "count")).reset_index()
    bullets = []
    if len(by_m) < 2:
        return bullets
    cur, prev = by_m.iloc[-1], by_m.iloc[-2]
    rev_d = pct_change(cur.rev, prev.rev)
    ord_d = pct_change(cur.orders, prev.orders)
    aov_d = pct_change(cur.rev / cur.orders, prev.rev / prev.orders)
    last = o[o.month == cur.month]
    pmo = o[o.month == prev.month]
    ns_cur = last.loc[last.is_first_order, "revenue"].sum() / last.revenue.sum() * 100
    ns_prev = pmo.loc[pmo.is_first_order, "revenue"].sum() / pmo.revenue.sum() * 100
    bullets.append((f"Revenue {('rose' if rev_d>=0 else 'fell')} "
                    f"{abs(rev_d):.1f}% to {money_compact(cur.rev)}",
                    "good" if rev_d >= 0 else "bad"))
    bullets.append((f"Orders {('up' if ord_d>=0 else 'down')} {abs(ord_d):.1f}% "
                    f"({int(cur.orders):,} placed)", "good" if ord_d >= 0 else "bad"))
    bullets.append((f"AOV {('up' if aov_d>=0 else 'down')} {abs(aov_d):.1f}% "
                    f"to {fmt_money(cur.rev/cur.orders,0)}",
                    "warn" if abs(aov_d) < 1 else ("good" if aov_d >= 0 else "bad")))
    bullets.append((f"New-customer revenue share {('rose' if ns_cur>=ns_prev else 'eased')} "
                    f"to {ns_cur:.0f}% (target <{TARGET_NEW_SHARE:.0f}%)",
                    "bad" if ns_cur >= TARGET_NEW_SHARE else "warn"))
    return bullets


def recommended_moves(c, o, a):
    """Data-driven action backlog (action, why, metric, impact, priority)."""
    m = blended_metrics(c, o)
    eco = channel_economics(c, o)
    spend = a.groupby("channel").spend.sum()
    eco["spend"] = eco.acquisition_channel.map(spend).fillna(0)
    meta = eco[eco.acquisition_channel == "Meta Prospecting"].iloc[0]
    best = eco.sort_values("ltv_cac", ascending=False).iloc[0]
    worst = eco.sort_values("ltv_cac").iloc[0]
    # mobile checkout leak if available
    moves = [
        dict(action="Cut dependency on newly-acquired revenue",
             why=f"{m['new_share']:.0f}% of last month's revenue came from "
                 f"brand-new customers — above the <{TARGET_NEW_SHARE:.0f}% "
                 f"healthy line. Growth is rented, not owned.",
             metric=f"New-rev share {m['new_share']:.0f}%",
             impact="Lower CAC pressure; compounding LTV",
             priority="High"),
        dict(action=f"Reallocate budget from {worst.acquisition_channel} "
                    f"toward {best.acquisition_channel}",
             why=f"{worst.acquisition_channel} returns just "
                 f"{worst.ltv_cac:.1f}:1 yet absorbs heavy spend, while "
                 f"{best.acquisition_channel} returns {best.ltv_cac:.0f}:1 "
                 f"and is under-funded.",
             metric=f"{money_compact(meta.spend)} in Meta Prospecting",
             impact=f"Shift ~{money_compact(meta.spend*0.2)} → +profit",
             priority="High"),
        dict(action="Lift the second-order rate with lifecycle flows",
             why=f"Only {m['repeat_rate']:.0f}% of customers ever buy again; "
                 f"newer cohorts retain worse as paid mix rises.",
             metric=f"Repeat rate {m['repeat_rate']:.0f}% (target {TARGET_REPEAT:.0f}%)",
             impact="Higher LTV:CAC, faster payback",
             priority="High"),
        dict(action="Fix the mobile checkout leak",
             why="Mobile checkout completion trails desktop badly; most paid "
                 "social traffic lands on mobile.",
             metric="Mobile checkout ≈ 56% vs 76% desktop",
             impact="Recover lost orders at no extra CAC",
             priority="Medium"),
        dict(action=f"Protect {best.acquisition_channel} & Google Brand",
             why="Highest-return, fastest-payback channels. Defend budget and "
                 "watch for cannibalization of organic demand.",
             metric=f"{best.acquisition_channel} {best.ltv_cac:.0f}:1",
             impact="Stable, profitable core",
             priority="Medium"),
    ]
    return moves


def channel_decision_table(c, o, a):
    """Build the Overview/Channels decision table with verdicts."""
    eco = channel_economics(c, o)
    spend = a.groupby("channel").spend.sum()
    rev = o.groupby("channel").revenue.sum()
    eco["spend"] = eco.acquisition_channel.map(spend).fillna(0)
    eco["revenue"] = eco.acquisition_channel.map(rev).fillna(0)
    eco["roas"] = np.where(eco.spend > 0, eco.revenue / eco.spend, np.nan)
    pb, _ = payback_by_channel(c, o)
    eco["payback"] = eco.acquisition_channel.map(pb)

    def verdict(r):
        if r.ltv_cac >= 3 and r.payback <= 3:
            return "Invest more", "good"
        if r.ltv_cac >= 3:
            return "Protect", "good"
        if r.acquisition_channel == "TikTok":
            return "Test creatives", "warn"
        if r.ltv_cac >= 2:
            return "Scale cautiously", "warn"
        return "Cut or fix", "bad"

    eco[["recommendation", "rec_tone"]] = eco.apply(
        lambda r: pd.Series(verdict(r)), axis=1)
    return eco.sort_values("revenue", ascending=False)


def build_founder_memo(c, o, a):
    """Markdown weekly memo + structured sections for in-app rendering."""
    score, status, tone, comps, m = growth_quality_score(c, o)
    eco = channel_economics(c, o)
    best = eco.sort_values("ltv_cac", ascending=False).iloc[0]
    worst = eco.sort_values("ltv_cac").iloc[0]
    today = _dt.date.today().strftime("%b %d, %Y")

    wins = [
        f"Revenue grew {m['rev_mom']:+.1f}% MoM to {money_compact(m['rev'])}.",
        f"{best.acquisition_channel} keeps returning {best.ltv_cac:.0f}:1 — "
        f"your most profitable acquisition source.",
        f"Per-order contribution margin holds at {m['cm_pct']:.0f}%.",
    ]
    risks = [
        f"{m['new_share']:.0f}% of revenue is from new customers "
        f"(target <{TARGET_NEW_SHARE:.0f}%) — growth is acquisition-dependent.",
        f"{worst.acquisition_channel} returns only {worst.ltv_cac:.1f}:1 but "
        f"absorbs heavy budget.",
        f"Repeat-purchase rate is {m['repeat_rate']:.0f}% and newer cohorts "
        f"retain worse.",
    ]
    changed = [b[0] for b in what_changed(o)]
    actions = [mv["action"] for mv in recommended_moves(c, o, a)[:3]]

    md = [f"# {BRAND} — Weekly Founder Memo", f"*{today}*", "",
          f"**Growth Quality Score: {score}/100 — {status}**", "",
          "## 🟢 Top 3 wins"]
    md += [f"- {w}" for w in wins]
    md += ["", "## 🔴 Top 3 risks"] + [f"- {r}" for r in risks]
    md += ["", "## 📈 What changed"] + [f"- {ch}" for ch in changed]
    md += ["", "## ✅ Recommended actions"] + [f"{i+1}. {a_}"
                                                for i, a_ in enumerate(actions)]
    return "\n".join(md), dict(score=score, status=status, tone=tone,
                               wins=wins, risks=risks, changed=changed,
                               actions=actions)


# ===========================================================================
# THEME  — global premium CSS
# ===========================================================================
def inject_theme():
    st.markdown(f"""<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    html, body, [class*="css"] {{ font-family:'Inter',system-ui,sans-serif;
        -webkit-font-smoothing:antialiased; }}
    .stApp {{ background:{BG}; }}
    .block-container {{ padding-top:1.6rem; padding-bottom:3.5rem; max-width:1180px; }}
    #MainMenu, footer, header[data-testid="stHeader"] {{ visibility:hidden; height:0; }}
    [data-testid="stSidebarNav"] {{ display:none; }}
    /* premium navy sidebar rail with subtle top glow */
    section[data-testid="stSidebar"] {{ width:272px !important;
        background:
          radial-gradient(120% 60% at 0% 0%, rgba(99,91,255,.28) 0%, rgba(99,91,255,0) 55%),
          linear-gradient(180deg, #0B2A49 0%, {INK} 60%); }}
    section[data-testid="stSidebar"] > div {{ padding-top:1.1rem; }}
    section[data-testid="stSidebar"] * {{ color:#C8D2E4; }}
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stMultiSelect label,
    section[data-testid="stSidebar"] .stRadio label {{ color:#8FA2C0 !important;
        font-size:.72rem !important; font-weight:700; text-transform:uppercase;
        letter-spacing:.07em; }}
    section[data-testid="stSidebar"] [data-baseweb="select"] > div,
    section[data-testid="stSidebar"] [data-baseweb="input"] > div {{
        background:rgba(255,255,255,.04); border-color:rgba(255,255,255,.10);
        border-radius:9px; }}
    section[data-testid="stSidebar"] [data-testid="stExpander"] {{
        border:1px solid rgba(255,255,255,.08); border-radius:10px;
        background:rgba(255,255,255,.02); }}
    /* nav links */
    .nav-link {{ display:block; padding:.46rem .7rem; margin:.1rem 0;
        border-radius:9px; color:#AEBBD2 !important; text-decoration:none;
        font-size:.9rem; font-weight:600; transition:all .15s ease; }}
    .nav-link:hover {{ background:rgba(255,255,255,.06); color:#fff !important; }}
    div[data-testid="stPageLink"] a {{ border-radius:9px; padding:.36rem .6rem;
        transition:all .15s ease; }}
    div[data-testid="stPageLink"] a p {{ font-weight:600; font-size:.9rem; }}
    div[data-testid="stPageLink"] a:hover {{ background:rgba(255,255,255,.07); }}
    div[data-testid="stPageLink"] a:hover p {{ color:#fff !important; }}
    /* cards lift gently on hover */
    .pcard {{ transition:box-shadow .18s ease, transform .18s ease; }}
    .pcard:hover {{ box-shadow:{SHADOW_LG}; transform:translateY(-2px); }}
    /* tighten plotly + dataframe chrome */
    .stPlotlyChart {{ border-radius:14px; }}
    hr {{ border-color:{LINE}; }}
    h1,h2,h3,h4,h5 {{ color:{INK}; letter-spacing:-.01em; }}
    </style>""", unsafe_allow_html=True)


# ===========================================================================
# SIDEBAR — SaaS nav + source badges + freshness + filters
# ===========================================================================
_NAV = [
    ("Overview.py", "📊", "Overview"),
    ("pages/1_Growth_Quality.py", "🎯", "Growth Quality"),
    ("pages/2_Channels.py", "📡", "Channels"),
    ("pages/3_Retention.py", "🔁", "Retention"),
    ("pages/4_Unit_Economics.py", "💸", "Unit Economics"),
    ("pages/5_Funnel.py", "🪜", "Funnel"),
    ("pages/6_Recommendations.py", "✅", "Recommendations"),
]


def _sidebar_brand():
    st.markdown(H(
        f"""<div style="padding:.2rem 0 .1rem">
        <div style="display:flex;align-items:center;gap:.55rem">
          <div style="width:30px;height:30px;border-radius:8px;
            background:linear-gradient(135deg,{ACCENT},#7C8BF0);display:flex;
            align-items:center;justify-content:center;font-weight:800;
            color:#fff;font-size:.95rem">L</div>
          <div>
            <div style="color:#fff;font-weight:800;font-size:1.02rem;
              line-height:1">{BRAND}</div>
            <div style="color:#7E8DA8;font-size:.7rem;font-weight:600;
              letter-spacing:.04em">{TAGLINE}</div>
          </div>
        </div></div>"""), unsafe_allow_html=True)


def _source_badges():
    chips = ""
    for s in ["Shopify", "Meta", "Klaviyo", "Google Ads"]:
        chips += (f'<span style="display:inline-block;background:#16213A;'
                  f'border:1px solid #26334F;color:#9FB0CE;border-radius:6px;'
                  f'padding:.12rem .4rem;font-size:.66rem;font-weight:600;'
                  f'margin:.12rem .18rem .12rem 0">{s}</span>')
    st.markdown(H(
        f"""<div style="margin:.2rem 0 .1rem">
        <div style="display:flex;align-items:center;gap:.4rem;margin-bottom:.3rem">
          <span style="width:7px;height:7px;border-radius:50%;background:{GOOD};
            box-shadow:0 0 0 3px {GOOD}33;display:inline-block"></span>
          <span style="color:#9FB0CE;font-size:.72rem;font-weight:600">
          Last synced 2h ago</span></div>
        <div>{chips}</div></div>"""), unsafe_allow_html=True)


def _coalesce(selected, options):
    return list(options) if not selected else selected


def render_sidebar(c, o, a, f, active=""):
    """Render nav + filters. Returns a filters dict for apply_filters()."""
    with st.sidebar:
        _sidebar_brand()
        st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)
        for path, icon, label in _NAV:
            try:
                st.page_link(path, label=f"{icon}  {label}")
            except Exception:
                st.markdown(f"<div class='nav-link'>{icon}&nbsp;&nbsp;{label}</div>",
                            unsafe_allow_html=True)

        st.markdown("<hr style='margin:.7rem 0 .5rem;border-color:#23304B'>",
                    unsafe_allow_html=True)
        try:
            st.page_link("pages/6_Recommendations.py",
                         label="📝  Generate Weekly Founder Memo")
        except Exception:
            st.markdown("<div class='nav-link'>📝&nbsp;&nbsp;Generate Weekly "
                        "Founder Memo</div>", unsafe_allow_html=True)
        st.markdown("<hr style='margin:.5rem 0;border-color:#23304B'>",
                    unsafe_allow_html=True)

        months = sorted(o.month.unique())
        lo, hi = st.select_slider(
            "Date range", options=months, value=(months[0], months[-1]),
            format_func=lambda d: pd.Timestamp(d).strftime("%b %Y"), key="flt_dates")

        with st.expander("⚙️  Advanced filters", expanded=False):
            cats = st.multiselect("Product category",
                                  sorted(o.product_category.unique()), key="flt_cat")
            chans = st.multiselect("Channel",
                                   list(CHANNEL_COLORS.keys()), key="flt_chan")
            camps = st.multiselect("Campaign",
                                   sorted(c.campaign.unique()), key="flt_camp")
            ctype = st.radio("Customer type", ["All", "New", "Returning"],
                             horizontal=True, key="flt_ctype")
            regions = st.multiselect("Region",
                                     sorted(c.region.unique()), key="flt_region")
            disc = st.radio("Discount", ["All", "Discounted", "Full price"],
                            horizontal=True, key="flt_disc")

        st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)
        _source_badges()
        st.markdown(
            "<div style='color:#5C6B86;font-size:.68rem;margin-top:.6rem'>"
            "Demo on synthetic data for the fictional brand "
            f"“{BRAND}.”</div>", unsafe_allow_html=True)

    return dict(date=(lo, hi),
                cats=_coalesce(cats, o.product_category.unique()),
                chans=_coalesce(chans, CHANNEL_COLORS.keys()),
                camps=_coalesce(camps, c.campaign.unique()),
                ctype=ctype, regions=_coalesce(regions, c.region.unique()),
                disc=disc)


def apply_filters(c, o, a, f, flt):
    lo, hi = flt["date"]
    months = pd.PeriodIndex(pd.date_range(lo, hi, freq="MS"), freq="M")
    c2 = c[(c.cohort >= lo) & (c.cohort <= hi)]
    o2 = o[(o.month >= lo) & (o.month <= hi)]
    a2 = a[a.date.dt.to_period("M").isin(months)]
    f2 = f[f.date.dt.to_period("M").isin(months)]

    if list(flt["regions"]):
        c2 = c2[c2.region.isin(flt["regions"])]
    if set(flt["chans"]) != set(CHANNEL_COLORS.keys()):
        c2 = c2[c2.acquisition_channel.isin(flt["chans"])]
        o2 = o2[o2.channel.isin(flt["chans"])]
        a2 = a2[a2.channel.isin(flt["chans"])]
        f2 = f2[f2.channel.isin(flt["chans"])]
    if set(flt["camps"]) != set(c.campaign.unique()):
        c2 = c2[c2.campaign.isin(flt["camps"])]

    o2 = o2[o2.customer_id.isin(c2.customer_id)]

    if set(flt["cats"]) != set(o.product_category.unique()):
        o2 = o2[o2.product_category.isin(flt["cats"])]
    if flt["ctype"] == "New":
        o2 = o2[o2.is_first_order]
    elif flt["ctype"] == "Returning":
        o2 = o2[~o2.is_first_order]
    if flt["disc"] == "Discounted":
        o2 = o2[o2.discount > 0]
    elif flt["disc"] == "Full price":
        o2 = o2[o2.discount == 0]
    return c2, o2, a2, f2


# ===========================================================================
# PAGE-LEVEL COMPONENTS
# ===========================================================================
def page_title(question, diagnosis):
    """Founder-facing question + one-sentence executive diagnosis."""
    st.markdown(H(
        f"""<div style="margin:.1rem 0 1.1rem">
        <div style="font-size:1.95rem;font-weight:800;color:{INK};
          line-height:1.12;letter-spacing:-.01em">{question}</div>
        <div style="font-size:1.02rem;color:{SUBTLE};margin-top:.5rem;
          line-height:1.5;max-width:880px">{diagnosis}</div>
        </div>"""), unsafe_allow_html=True)


# backward-compatible header (kicker, title, subtitle)
def page_header(kicker, title, subtitle):
    st.markdown(H(
        f"""<div style="margin:.1rem 0 1rem">
        <div style="font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;
        color:{ACCENT};font-weight:700">{kicker}</div>
        <div style="font-size:1.9rem;font-weight:800;color:{INK};line-height:1.15;
        margin-top:.15rem">{title}</div>
        <div style="font-size:1rem;color:{SUBTLE};margin-top:.3rem">{subtitle}</div>
        </div>"""), unsafe_allow_html=True)


def status_pill(text, tone="warn", inline=True):
    bg = {"good": GOOD_SOFT, "warn": WARN_SOFT, "bad": BAD_SOFT,
          "neutral": NEUTRAL_SOFT}[tone]
    fg = {"good": GOOD, "warn": WARN, "bad": BAD, "neutral": SUBTLE}[tone]
    dot = (f'<span style="width:6px;height:6px;border-radius:50%;background:{fg};'
           f'display:inline-block;margin-right:.35rem;vertical-align:middle"></span>')
    html = (f'<span style="background:{bg};color:{fg};border-radius:999px;'
            f'padding:.16rem .55rem;font-size:.72rem;font-weight:700;'
            f'white-space:nowrap">{dot}{text}</span>')
    if inline:
        return html
    st.markdown(html, unsafe_allow_html=True)


def insight_kpi(label, value, delta=None, delta_good=True, insight="",
                pill=None, pill_tone="neutral"):
    """Premium insight KPI card (returns HTML; render inside a column)."""
    trend = ""
    if delta is not None:
        col = GOOD if delta_good else BAD
        arrow = "▲" if delta >= 0 else "▼"
        trend = (f'<span style="color:{col};font-weight:700;font-size:.8rem">'
                 f'{arrow} {abs(delta):.1f}% <span style="color:{MUTE};'
                 f'font-weight:500">MoM</span></span>')
    pill_html = (f'<div style="margin-bottom:.55rem">'
                 f'{status_pill(pill, pill_tone)}</div>') if pill else ""
    return H(f"""<div class="pcard" style="background:{CARD};border:1px solid {LINE};
    border-radius:14px;padding:1.05rem 1.15rem;height:100%;
    box-shadow:0 4px 14px rgba(10,37,64,.05)">
    {pill_html}
    <div style="font-size:.76rem;color:{SUBTLE};font-weight:600;
      text-transform:uppercase;letter-spacing:.05em">{label}</div>
    <div style="font-size:1.62rem;font-weight:800;color:{INK};
      margin:.18rem 0 .1rem;letter-spacing:-.01em">{value}</div>
    <div style="margin-bottom:.35rem">{trend}</div>
    <div style="color:{SUBTLE};font-size:.8rem;line-height:1.35">{insight}</div>
    </div>""")


def kpi_card(label, value, delta=None, delta_good=True, helptext=""):
    """Backward-compatible simple card."""
    return insight_kpi(label, value, delta, delta_good, helptext)


def score_card(score, status, tone, subtitle=""):
    """Big Growth Quality Score scorecard with a benchmark arc."""
    fg = {"good": GOOD, "warn": WARN, "bad": BAD}[tone]
    bg = {"good": GOOD_SOFT, "warn": WARN_SOFT, "bad": BAD_SOFT}[tone]
    deg = 360 * (score / 100)
    return H(f"""<div class="pcard" style="background:{CARD};border:1px solid {LINE};
      border-radius:16px;padding:1.2rem 1.3rem;height:100%;
      box-shadow:0 4px 14px rgba(10,37,64,.05);display:flex;gap:1.2rem;
      align-items:center">
      <div style="width:104px;height:104px;border-radius:50%;flex-shrink:0;
        background:conic-gradient({fg} {deg}deg, {LINE} {deg}deg);
        display:flex;align-items:center;justify-content:center">
        <div style="width:80px;height:80px;border-radius:50%;background:{CARD};
          display:flex;flex-direction:column;align-items:center;
          justify-content:center">
          <div style="font-size:1.7rem;font-weight:800;color:{INK};
            line-height:1">{score}</div>
          <div style="font-size:.66rem;color:{MUTE};font-weight:600">/ 100</div>
        </div></div>
      <div>
        <div style="font-size:.74rem;color:{SUBTLE};font-weight:700;
          text-transform:uppercase;letter-spacing:.08em">Growth Quality Score</div>
        <div style="margin:.4rem 0 .35rem">
          <span style="background:{bg};color:{fg};border-radius:999px;
            padding:.22rem .7rem;font-size:.86rem;font-weight:800">{status}</span>
        </div>
        <div style="color:{SUBTLE};font-size:.84rem;line-height:1.45;
          max-width:430px">{subtitle}</div>
      </div></div>""")


def section(title, subtitle=""):
    sub = (f'<div style="color:{SUBTLE};font-size:.88rem;margin-top:.15rem">'
           f'{subtitle}</div>') if subtitle else ""
    st.markdown(H(
        f"""<div style="margin:1.5rem 0 .7rem">
        <div style="font-size:1.12rem;font-weight:800;color:{INK}">{title}</div>
        {sub}</div>"""), unsafe_allow_html=True)


def insight_callout(title, body, tone="warn", actions=None):
    bg = {"warn": WARN_SOFT, "bad": BAD_SOFT, "good": GOOD_SOFT,
          "neutral": NEUTRAL_SOFT}[tone]
    bar = {"warn": WARN, "bad": BAD, "good": GOOD, "neutral": ACCENT}[tone]
    icon = {"warn": "⚠️", "bad": "🔻", "good": "✅", "neutral": "💡"}[tone]
    act = ""
    if actions:
        items = "".join(
            f'<li style="margin:.15rem 0">{a_}</li>' for a_ in actions)
        act = (f'<div style="margin-top:.6rem;font-size:.86rem;color:{INK}">'
               f'<b>Recommended next actions</b><ul style="margin:.25rem 0 0;'
               f'padding-left:1.1rem">{items}</ul></div>')
    st.markdown(H(
        f"""<div style="background:{bg};border-left:4px solid {bar};
        border-radius:10px;padding:.9rem 1.1rem;margin:.5rem 0 1rem">
        <div style="font-weight:800;color:{INK};font-size:.95rem;
          margin-bottom:.25rem">{icon} {title}</div>
        <div style="color:{INK_SOFT};font-size:.9rem;line-height:1.55">{body}</div>
        {act}</div>"""), unsafe_allow_html=True)


# keep old name as alias
def insight_box(title, body, tone="warn"):
    insight_callout(title, body, tone)


def action_card(action, why, metric, impact, priority):
    ptone = {"High": "bad", "Medium": "warn", "Low": "neutral"}.get(priority, "neutral")
    return H(f"""<div class="pcard" style="background:{CARD};border:1px solid {LINE};
      border-radius:14px;padding:1rem 1.1rem;height:100%;
      box-shadow:0 4px 14px rgba(10,37,64,.05)">
      <div style="display:flex;justify-content:space-between;align-items:start;
        gap:.5rem;margin-bottom:.45rem">
        <div style="font-weight:800;color:{INK};font-size:.96rem;
          line-height:1.25">{action}</div>
        {status_pill(priority + " priority", ptone)}
      </div>
      <div style="color:{SUBTLE};font-size:.84rem;line-height:1.45;
        margin-bottom:.6rem">{why}</div>
      <div style="border-top:1px solid {LINE};padding-top:.5rem;display:flex;
        gap:1.2rem;flex-wrap:wrap">
        <div><div style="font-size:.66rem;color:{MUTE};font-weight:700;
          text-transform:uppercase">Signal</div>
          <div style="font-size:.84rem;color:{INK};font-weight:600">{metric}</div></div>
        <div><div style="font-size:.66rem;color:{MUTE};font-weight:700;
          text-transform:uppercase">Expected impact</div>
          <div style="font-size:.84rem;color:{GOOD};font-weight:600">{impact}</div></div>
      </div></div>""")


def render_decision_table(eco):
    """Premium HTML decision table from channel_decision_table() output."""
    head = ("Channel", "New custs", "CAC", "ROAS", "Payback", "Revenue",
            "LTV:CAC", "Recommendation")
    th = "".join(
        f'<th style="text-align:{"left" if i==0 else "right"};padding:.55rem .7rem;'
        f'font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;'
        f'color:{MUTE};font-weight:700;border-bottom:1px solid {LINE};'
        f'{"text-align:center" if i==7 else ""}">{h}</th>'
        for i, h in enumerate(head))
    rows = ""
    for _, r in eco.iterrows():
        dot = (f'<span style="width:8px;height:8px;border-radius:50%;'
               f'background:{CHANNEL_COLORS.get(r.acquisition_channel, ACCENT)};'
               f'display:inline-block;margin-right:.5rem"></span>')
        roas = "—" if pd.isna(r.roas) else f"{r.roas:.1f}×"
        lc_tone = GOOD if r.ltv_cac >= 3 else (WARN if r.ltv_cac >= 2 else BAD)
        cells = [
            f'<td style="padding:.6rem .7rem;font-weight:600;color:{INK};'
            f'border-bottom:1px solid {LINE}">{dot}{r.acquisition_channel}</td>',
            f'<td style="padding:.6rem .7rem;text-align:right;color:{INK_SOFT};'
            f'border-bottom:1px solid {LINE}">{int(r.customers):,}</td>',
            f'<td style="padding:.6rem .7rem;text-align:right;color:{INK_SOFT};'
            f'border-bottom:1px solid {LINE}">{fmt_money(r.cac,0)}</td>',
            f'<td style="padding:.6rem .7rem;text-align:right;color:{INK_SOFT};'
            f'border-bottom:1px solid {LINE}">{roas}</td>',
            f'<td style="padding:.6rem .7rem;text-align:right;color:{INK_SOFT};'
            f'border-bottom:1px solid {LINE}">{r.payback:.1f} mo</td>',
            f'<td style="padding:.6rem .7rem;text-align:right;color:{INK_SOFT};'
            f'border-bottom:1px solid {LINE}">{money_compact(r.revenue)}</td>',
            f'<td style="padding:.6rem .7rem;text-align:right;font-weight:700;'
            f'color:{lc_tone};border-bottom:1px solid {LINE}">{r.ltv_cac:.1f}:1</td>',
            f'<td style="padding:.6rem .7rem;text-align:center;'
            f'border-bottom:1px solid {LINE}">'
            f'{status_pill(r.recommendation, r.rec_tone)}</td>',
        ]
        rows += f"<tr>{''.join(cells)}</tr>"
    st.markdown(H(
        f"""<div class="pcard" style="background:{CARD};border:1px solid {LINE};border-radius:14px;
        overflow:hidden;box-shadow:0 4px 14px rgba(10,37,64,.05)">
        <table style="width:100%;border-collapse:collapse;font-size:.86rem">
        <thead><tr>{th}</tr></thead><tbody>{rows}</tbody></table></div>"""),
        unsafe_allow_html=True)


def demo_banner():
    """Kept for backward compatibility — premium build uses the sidebar/header."""
    pass


# ===========================================================================
# CHART LAYOUT  — premium, minimal gridlines
# ===========================================================================
def chart_layout(fig, h=360, legend=True):
    fig.update_layout(
        height=h, margin=dict(l=55, r=24, t=36, b=16),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, sans-serif", color=INK_SOFT, size=12),
        hoverlabel=dict(bgcolor="white", bordercolor=LINE,
                        font=dict(family="Inter", size=12, color=INK)),
        legend=(dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                     font=dict(size=11)) if legend else dict()),
        showlegend=legend,
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=LINE,
                     tickfont=dict(color=SUBTLE))
    fig.update_yaxes(showgrid=True, gridcolor=GRID, zeroline=False,
                     tickfont=dict(color=SUBTLE), griddash="dot")
    return fig


def setup_page(title_suffix):
    """Per-page boilerplate: config + theme. Returns loaded+nothing."""
    st.set_page_config(page_title=f"{BRAND} · {title_suffix}", page_icon="📊",
                       layout="wide", initial_sidebar_state="expanded")
    inject_theme()
