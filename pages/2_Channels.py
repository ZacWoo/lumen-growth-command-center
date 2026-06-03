"""Channels — Which channels actually work, and where is the money burning?"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import lib
from lib import (load, setup_page, render_sidebar, apply_filters, page_title,
                 section, insight_kpi, insight_callout, chart_layout,
                 channel_economics, fmt_money, fmt_pct, money_compact,
                 INK, INK_SOFT, SUBTLE, MUTE, ACCENT, GOOD, BAD, WARN, GRID,
                 LINE, CHANNEL_COLORS, TARGET_LTV_CAC)

setup_page("Channels")
c0, o0, a0, f0 = load()
flt = render_sidebar(c0, o0, a0, f0, active="Channels")
c, o, a, f = apply_filters(c0, o0, a0, f0, flt)
if o.empty or c.empty:
    st.warning("No data for the current filter selection. Widen your filters.")
    st.stop()

eco = channel_economics(c, o).sort_values("cac")
spend_by_ch = a.groupby("channel").spend.sum()
eco["total_spend"] = eco.acquisition_channel.map(spend_by_ch).fillna(0)
cheapest = eco.iloc[0]
best_value = eco.sort_values("ltv_cac", ascending=False).iloc[0]
worst_value = eco.sort_values("ltv_cac").iloc[0]
meta = eco[eco.acquisition_channel == "Meta Prospecting"].iloc[0] \
    if (eco.acquisition_channel == "Meta Prospecting").any() else worst_value

diag = (f"Acquisition cost is only half the story. <b>{worst_value.acquisition_channel}</b> "
        f"looks cheap but returns just <b>{worst_value.ltv_cac:.1f}:1</b>, while "
        f"<b>{best_value.acquisition_channel}</b> quietly returns "
        f"<b>{best_value.ltv_cac:.0f}:1</b> — the budget is pointed the wrong way.")
page_title("Which channels actually work — and where is the money burning?", diag)

# --- KPI row ---------------------------------------------------------------
k = st.columns(4)
k[0].markdown(insight_kpi("Lowest CAC channel", cheapest.acquisition_channel,
              insight=f"{fmt_money(cheapest.cac,0)} per customer"),
              unsafe_allow_html=True)
k[1].markdown(insight_kpi("Best LTV : CAC", best_value.acquisition_channel,
              insight=f"{best_value.ltv_cac:.1f}:1 return", pill="Invest more",
              pill_tone="good"), unsafe_allow_html=True)
k[2].markdown(insight_kpi("Biggest spend", meta.acquisition_channel,
              insight=f"{money_compact(meta.total_spend)} total"),
              unsafe_allow_html=True)
k[3].markdown(insight_kpi("Meta Prosp. repeat rate", f"{meta.repeat_rate:.0f}%",
              insight="Lowest of any channel", pill="Churns", pill_tone="bad"),
              unsafe_allow_html=True)

# --- Hero: CAC vs repeat-rate quadrant -------------------------------------
section("What you pay vs. whether they come back",
        "Bubble size = total spend. The quadrant a channel lands in is the verdict.")
fig = go.Figure()
for _, r in eco.iterrows():
    fig.add_scatter(
        x=[r.cac], y=[r.repeat_rate], mode="markers+text",
        marker=dict(size=np.sqrt(max(r.total_spend, 1)) / 6 + 12,
                    color=CHANNEL_COLORS[r.acquisition_channel],
                    line=dict(width=1.5, color="white"), opacity=.92),
        text=[r.acquisition_channel], textposition="top center",
        textfont=dict(size=11, color=INK), name=r.acquisition_channel,
        hovertemplate=(f"<b>{r.acquisition_channel}</b><br>CAC: {fmt_money(r.cac,0)}"
                       f"<br>Repeat rate: {r.repeat_rate:.0f}%"
                       f"<br>LTV:CAC: {r.ltv_cac:.1f}:1"
                       f"<br>Total spend: {money_compact(r.total_spend)}<extra></extra>"))
cac_mid, rep_mid = eco.cac.mean(), eco.repeat_rate.mean()
fig.add_vline(x=cac_mid, line_dash="dot", line_color=MUTE)
fig.add_hline(y=rep_mid, line_dash="dot", line_color=MUTE)
fig.update_layout(showlegend=False)
fig.update_xaxes(title="Customer acquisition cost (CAC) →", tickprefix="$")
fig.update_yaxes(title="Repeat purchase rate →", ticksuffix="%")
quad = [(eco.cac.min(), eco.repeat_rate.max(), "Cheap + loyal · scale", GOOD, "left"),
        (eco.cac.max(), eco.repeat_rate.max(), "Expensive + loyal · optimize", WARN, "right"),
        (eco.cac.min(), eco.repeat_rate.min(), "Cheap + churns · dangerous", BAD, "left"),
        (eco.cac.max(), eco.repeat_rate.min(), "Expensive + churns · cut or fix", BAD, "right")]
for x, y, t, col, anc in quad:
    fig.add_annotation(x=x, y=y, text=t, showarrow=False,
                       font=dict(color=col, size=10.5, family="Inter"),
                       xanchor=anc, opacity=.9)
st.plotly_chart(chart_layout(fig, h=440, legend=False), width="stretch")

insight_callout(
    "Your cheapest channel is one of your worst investments.",
    f"<b>{meta.acquisition_channel}</b> has nearly the lowest CAC "
    f"({fmt_money(meta.cac,0)}) — so it <i>looks</i> like a bargain and gets the "
    f"biggest budget ({money_compact(meta.total_spend)}). But only "
    f"<b>{meta.repeat_rate:.0f}% ever buy again</b>, the worst of any channel, a thin "
    f"{meta.ltv_cac:.1f}:1 return. <b>Email/Organic and Referral</b> cost a fraction "
    f"and return {best_value.ltv_cac:.0f}×+ — that's where the budget belongs.",
    tone="bad",
    actions=[f"Cap {meta.acquisition_channel} spend and reallocate to "
             f"{best_value.acquisition_channel}",
             "Hold each paid channel to a 3:1 LTV:CAC and <3-month payback bar",
             "Audit Google Brand for organic cannibalization before scaling"])

# --- supporting charts (unchanged) -----------------------------------------
left, right = st.columns([3, 4])
with left:
    section("Return on each channel (LTV : CAC)")
    e2 = eco.sort_values("ltv_cac")
    fig2 = go.Figure(go.Bar(
        x=e2.ltv_cac, y=e2.acquisition_channel, orientation="h",
        marker_color=[GOOD if v >= 3 else (WARN if v >= 2 else BAD) for v in e2.ltv_cac],
        text=[f"{v:.1f}:1" for v in e2.ltv_cac], textposition="outside",
        textfont=dict(color=INK)))
    fig2.add_vline(x=TARGET_LTV_CAC, line_dash="dash", line_color=GOOD,
                   annotation_text="healthy 3:1", annotation_font=dict(color=GOOD, size=11))
    fig2.update_xaxes(title="", range=[0, e2.ltv_cac.max() * 1.18])
    st.plotly_chart(chart_layout(fig2, h=320, legend=False), width="stretch")
with right:
    section("Spend share vs. profit share — the misallocation")
    eco["spend_share"] = eco.total_spend / eco.total_spend.sum() * 100
    val = o.groupby("customer_id").contribution.sum()
    cust_ch = c.set_index("customer_id").acquisition_channel
    val_by_ch = val.groupby(cust_ch).sum()
    eco["value_share"] = eco.acquisition_channel.map(
        val_by_ch / val_by_ch.sum() * 100).fillna(0)
    e3 = eco.sort_values("spend_share")
    fig3 = go.Figure()
    fig3.add_bar(y=e3.acquisition_channel, x=e3.spend_share, name="% of spend",
                 orientation="h", marker_color=BAD, opacity=.9)
    fig3.add_bar(y=e3.acquisition_channel, x=e3.value_share, name="% of profit",
                 orientation="h", marker_color=GOOD, opacity=.9)
    fig3.update_layout(barmode="group")
    fig3.update_xaxes(ticksuffix="%")
    st.plotly_chart(chart_layout(fig3, h=320), width="stretch")
st.caption("Where the coral bar (spend) exceeds the green (profit), you're "
           "over-invested. Meta Prospecting eats budget out of proportion to the "
           "profit it makes; Email/Organic and Referral are the reverse.")

with st.expander("See the full channel breakdown"):
    show = eco[["acquisition_channel", "customers", "cac", "ltv_cm",
                "repeat_rate", "ltv_cac", "total_spend"]].copy()
    show.columns = ["Channel", "Customers", "CAC", "LTV (margin)", "Repeat %",
                    "LTV:CAC", "Total spend"]
    show["CAC"] = show["CAC"].map(lambda x: fmt_money(x, 0))
    show["LTV (margin)"] = show["LTV (margin)"].map(lambda x: fmt_money(x, 0))
    show["Repeat %"] = show["Repeat %"].map(lambda x: f"{x:.0f}%")
    show["LTV:CAC"] = show["LTV:CAC"].map(lambda x: f"{x:.1f}:1")
    show["Total spend"] = show["Total spend"].map(lambda x: money_compact(x))
    show["Customers"] = show["Customers"].map(lambda x: f"{x:,}")
    st.dataframe(show, width="stretch", hide_index=True)
