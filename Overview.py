"""Overview — the executive growth diagnosis."""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import lib
from lib import (load, setup_page, render_sidebar, apply_filters, page_title,
                 section, insight_kpi, score_card, insight_callout, action_card,
                 status_pill, chart_layout, money_compact, fmt_money, fmt_pct, H,
                 channel_decision_table, render_decision_table, recommended_moves,
                 what_changed, growth_quality_score,
                 INK, INK_SOFT, SUBTLE, MUTE, ACCENT, GOOD, BAD, WARN, LINE,
                 CARD, GOOD_SOFT, WARN_SOFT, BAD_SOFT, CHANNEL_COLORS,
                 TARGET_NEW_SHARE)

setup_page("Overview")
c0, o0, a0, f0 = load()
flt = render_sidebar(c0, o0, a0, f0, active="Overview")
c, o, a, f = apply_filters(c0, o0, a0, f0, flt)

if o.empty:
    st.warning("No data for the current filter selection. Widen your filters.")
    st.stop()

score, status, tone, comps, m = growth_quality_score(c, o)

# --- founder question + executive diagnosis --------------------------------
diagnosis = (
    f"Revenue is up <b>{m['rev_mom']:+.1f}% MoM</b> to "
    f"<b>{money_compact(m['rev'])}</b>, but <b>{m['new_share']:.0f}% of revenue "
    f"still comes from new customers</b>. Growth is real — but it's "
    f"acquisition-dependent, not retention-led.")
page_title("Is the business growing — and is it healthy, profitable, "
           "repeatable growth?", diagnosis)

# ===========================================================================
# 1) EXECUTIVE SUMMARY
# ===========================================================================
section("Executive summary", "The one-screen read on growth health this month.")

left, right = st.columns([1.05, 1])
with left:
    st.markdown(score_card(
        score, status, tone,
        "A weighted read across revenue growth, retention, unit economics, CAC "
        "trend, margin, payback and discount dependency. Acquisition strength is "
        "masking weak returning-revenue and below-target LTV:CAC."),
        unsafe_allow_html=True)
with right:
    bullets = what_changed(o)
    items = ""
    for txt, bt in bullets:
        items += (f'<div style="display:flex;gap:.5rem;align-items:start;'
                  f'margin:.3rem 0"><span style="margin-top:.15rem">'
                  f'{status_pill("", bt)}</span>'
                  f'<span style="font-size:.88rem;color:{INK_SOFT};'
                  f'line-height:1.4">{txt}</span></div>')
    st.markdown(H(
        f"""<div class="pcard" style="background:{CARD};border:1px solid {LINE};
        border-radius:16px;padding:1.1rem 1.2rem;height:100%;
        box-shadow:0 4px 14px rgba(10,37,64,.05)">
        <div style="font-size:.74rem;color:{SUBTLE};font-weight:700;
          text-transform:uppercase;letter-spacing:.08em;margin-bottom:.5rem">
          What changed this month?</div>{items}</div>"""),
        unsafe_allow_html=True)

st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

# --- insight KPI cards ------------------------------------------------------
k = st.columns(5)
cards = [
    insight_kpi("Revenue", money_compact(m["rev"]), m["rev_mom"],
                m["rev_mom"] >= 0, "Top-line growth is positive"),
    insight_kpi("Orders", f"{int(m['orders']):,}", m["orders_mom"],
                m["orders_mom"] >= 0, "Growth is volume-driven"),
    insight_kpi("AOV", fmt_money(m["aov"], 0), m["aov_mom"], m["aov_mom"] >= 0,
                "Basket size is flat"),
    insight_kpi("Returning rev. share", fmt_pct(m["returning_share"], 0),
                insight="Retention isn't compounding enough",
                pill="Below target", pill_tone="bad"),
    insight_kpi("LTV : CAC", f"{m['ltv_cac']:.1f} : 1",
                insight="Near healthy; target is 3:1+",
                pill="Watch", pill_tone="warn"),
]
for col, card in zip(k, cards):
    col.markdown(card, unsafe_allow_html=True)

# ===========================================================================
# 2) GROWTH QUALITY
# ===========================================================================
section("Growth quality",
        "Is revenue powered by a compounding base — or by buying new customers "
        "every month?")

split = (o.groupby(["month", "is_first_order"]).revenue.sum().unstack()
         .fillna(0).rename(columns={True: "New", False: "Returning"}))
split["pct_new"] = split["New"] / (split["New"] + split["Returning"]) * 100

gl, gr = st.columns([3, 2])
with gl:
    st.markdown(f"<div style='font-weight:700;color:{INK};font-size:.92rem;"
                f"margin-bottom:.2rem'>Revenue by customer type</div>",
                unsafe_allow_html=True)
    fig = go.Figure()
    fig.add_bar(x=split.index, y=split["Returning"], name="Returning",
                marker_color=GOOD)
    fig.add_bar(x=split.index, y=split["New"], name="New",
                marker_color=ACCENT)
    fig.update_layout(barmode="stack")
    fig.update_yaxes(tickprefix="$")
    st.plotly_chart(chart_layout(fig, h=330), width="stretch")
with gr:
    st.markdown(f"<div style='font-weight:700;color:{INK};font-size:.92rem;"
                f"margin-bottom:.2rem'>New-customer revenue share</div>",
                unsafe_allow_html=True)
    fig2 = go.Figure()
    fig2.add_scatter(x=split.index, y=split["pct_new"], mode="lines",
                     line=dict(color=BAD, width=3), fill="tozeroy",
                     fillcolor="rgba(209,91,71,.10)", name="% new")
    fig2.add_hline(y=TARGET_NEW_SHARE, line_dash="dash", line_color=GOOD,
                   annotation_text=f"target <{TARGET_NEW_SHARE:.0f}%",
                   annotation_position="bottom right",
                   annotation_font=dict(color=GOOD, size=11))
    fig2.update_yaxes(ticksuffix="%", range=[0, 100])
    st.plotly_chart(chart_layout(fig2, h=330, legend=False), width="stretch")

pct_now, pct_then = split["pct_new"].iloc[-1], split["pct_new"].iloc[0]
insight_callout(
    "Growth is rented, not owned.",
    f"<b>{pct_now:.0f}%</b> of last month's revenue came from brand-new "
    f"customers — barely moved from {pct_then:.0f}% at the start, and well above "
    f"the <{TARGET_NEW_SHARE:.0f}% healthy line. A compounding DTC brand sees "
    f"this share <i>fall</i> as a loyal base builds. Flat here means every month "
    f"of growth has to be re-bought.",
    tone="bad",
    actions=["Stand up post-purchase lifecycle flows to lift the second-order rate",
             "Shift incremental budget to channels that produce repeat buyers",
             "Track returning-revenue share as a weekly north-star metric"])

# ===========================================================================
# 3) CHANNEL EFFICIENCY  — decision table
# ===========================================================================
section("Channel efficiency",
        "Not just where customers come from — what to do about each channel.")
eco = channel_decision_table(c, o, a)
render_decision_table(eco)
st.caption("ROAS = revenue ÷ paid spend (organic/referral carry little spend, so "
           "their ROAS runs high). Payback = months of contribution margin to "
           "recoup CAC. Verdicts blend LTV:CAC and payback against the 3:1 / "
           "<3-month targets.")

# ===========================================================================
# 4) RECOMMENDED NEXT MOVES
# ===========================================================================
section("Recommended next moves",
        "The highest-leverage actions this week, ranked by priority.")
moves = recommended_moves(c, o, a)
row1 = st.columns(2)
row2 = st.columns(2)
for col, mv in zip(row1 + row2, moves[:4]):
    col.markdown(action_card(**mv), unsafe_allow_html=True)
    col.markdown("<div style='height:.7rem'></div>", unsafe_allow_html=True)

st.markdown(
    f"<div style='text-align:center;margin-top:.6rem'>"
    f"<a href='Recommendations' target='_self' style='color:{ACCENT};"
    f"font-weight:700;font-size:.9rem;text-decoration:none'>"
    f"See the full action backlog & generate the Weekly Founder Memo →</a></div>",
    unsafe_allow_html=True)
