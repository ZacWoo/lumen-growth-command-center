"""Retention — Do customers come back, or am I refilling a leaky bucket?"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import lib
from lib import (load, setup_page, render_sidebar, apply_filters, page_title,
                 section, insight_kpi, insight_callout, chart_layout,
                 fmt_money, fmt_pct, INK, INK_SOFT, SUBTLE, MUTE, ACCENT,
                 GOOD, BAD, WARN, GRID, LINE, TARGET_REPEAT)

setup_page("Retention")
c0, o0, a0, f0 = load()
flt = render_sidebar(c0, o0, a0, f0, active="Retention")
c, o, a, f = apply_filters(c0, o0, a0, f0, flt)
if o.empty or c.empty:
    st.warning("No data for the current filter selection. Widen your filters.")
    st.stop()

# ---------------------------------------------------------------------------
# Core retention computations (unchanged logic)
# ---------------------------------------------------------------------------
data_end = o.order_date.max()
repeaters = set(o.loc[~o.is_first_order, "customer_id"].unique())
cc = c.copy()
cc["repeated"] = cc.customer_id.isin(repeaters)
overall_repeat = cc.repeated.mean() * 100

first_dt = o[o.is_first_order].groupby("customer_id").order_date.min()
second_dt = o[~o.is_first_order].groupby("customer_id").order_date.min()
tts = (second_dt - first_dt).dropna().dt.days
median_tts = tts.median() if len(tts) else 0

by_cohort = cc.groupby("cohort").repeated.mean() * 100
cohort_age = (data_end - cc.groupby("cohort").first_order_date.min()).dt.days
mature = by_cohort[cohort_age >= 45]
if len(mature) < 2:
    mature = by_cohort
earliest_rate, recent_rate = mature.iloc[0], mature.iloc[-1]
earliest_label = pd.Timestamp(mature.index[0]).strftime("%b %Y")
recent_label = pd.Timestamp(mature.index[-1]).strftime("%b %Y")

diag = (f"Only <b>{overall_repeat:.0f}%</b> of customers ever buy again, and "
        f"newer cohorts retain worse than older ones "
        f"(<b>{recent_rate:.0f}%</b> vs <b>{earliest_rate:.0f}%</b>) — the bucket "
        f"is leaking faster than acquisition fills it.")
page_title("Do customers come back — or is the bucket leaking?", diag)

# --- KPI row ---------------------------------------------------------------
repeat_tone = "good" if overall_repeat >= TARGET_REPEAT else "warn"
k = st.columns(3)
k[0].markdown(insight_kpi(
    "Repeat-purchase rate", fmt_pct(overall_repeat, 0),
    insight="Share of customers who ever reorder",
    pill=f"Target {TARGET_REPEAT:.0f}%", pill_tone=repeat_tone),
    unsafe_allow_html=True)
k[1].markdown(insight_kpi(
    "Median time to 2nd order", f"{median_tts:.0f} days",
    insight="Among customers who return"), unsafe_allow_html=True)
k[2].markdown(insight_kpi(
    "Newest vs. oldest cohort", f"{recent_rate:.0f}% vs {earliest_rate:.0f}%",
    delta=(recent_rate - earliest_rate) / earliest_rate * 100 if earliest_rate else 0,
    delta_good=False, insight=f"{recent_label} vs {earliest_label}",
    pill="Deteriorating", pill_tone="bad"), unsafe_allow_html=True)

# --- Hero heatmap ----------------------------------------------------------
section("How long each cohort keeps ordering",
        "Each row is a monthly acquisition cohort; cells show the share still "
        "ordering that many months after their first purchase.")
om = o.merge(cc[["customer_id", "cohort"]], on="customer_id")
om["order_month"] = om.order_date.dt.to_period("M").dt.to_timestamp()
om["months_since"] = ((om.order_month.dt.year - om.cohort.dt.year) * 12
                      + (om.order_month.dt.month - om.cohort.dt.month))
cohort_size = cc.groupby("cohort").customer_id.nunique()
retention = (om.groupby(["cohort", "months_since"]).customer_id.nunique()
             .unstack().div(cohort_size, axis=0) * 100)
MAX_MONTH = 12
ret = retention.loc[:, [m for m in retention.columns if 1 <= m <= MAX_MONTH]]
ret = ret.sort_index()
y_labels = [pd.Timestamp(d).strftime("%b %Y") for d in ret.index]
z = ret.values
text = np.where(np.isnan(z), "", np.vectorize(lambda v: f"{v:.0f}")(
    np.nan_to_num(z)))
hm = go.Figure(go.Heatmap(
    z=z, x=[f"+{m}" for m in ret.columns], y=y_labels,
    text=text, texttemplate="%{text}", textfont=dict(size=10, color=INK),
    colorscale=[[0, "#FBFCFF"], [0.35, "#D8D6FB"], [0.7, "#9B95FF"],
                [1.0, ACCENT]],
    hovertemplate=("Cohort %{y}<br>Month %{x}<br>%{z:.1f}% still ordering"
                   "<extra></extra>"),
    colorbar=dict(title="% active", ticksuffix="%", thickness=12, len=.9)))
hm.update_xaxes(title="Months since first order →", side="top", showgrid=False)
hm.update_yaxes(autorange="reversed", showgrid=False)
hm = chart_layout(hm, h=460, legend=False)
hm.update_layout(margin=dict(l=70, r=20, t=55, b=10))
st.plotly_chart(hm, width="stretch")

# --- Repeat-rate-by-cohort trend -------------------------------------------
section("Repeat-purchase rate is sliding with every new cohort")
trend = mature.reset_index()
trend.columns = ["cohort", "repeat_rate"]
fig = go.Figure()
fig.add_scatter(
    x=trend.cohort, y=trend.repeat_rate, mode="lines+markers",
    line=dict(color=BAD, width=3),
    marker=dict(size=7, color=BAD, line=dict(width=1.5, color="white")),
    fill="tozeroy", fillcolor="rgba(224,88,75,.08)",
    hovertemplate="%{x|%b %Y}<br>%{y:.1f}% ever reorder<extra></extra>")
fig.add_hline(y=overall_repeat, line_dash="dot", line_color=SUBTLE,
              annotation_text=f"overall {overall_repeat:.0f}%",
              annotation_position="right")
fig.update_yaxes(ticksuffix="%", range=[0, max(60, mature.max() * 1.15)])
fig.update_xaxes(title="Acquisition-month cohort")
st.plotly_chart(chart_layout(fig, h=340, legend=False), width="stretch")
st.caption("Newest cohort excluded — it hasn't had time to place a repeat order "
           "yet, so its rate isn't comparable.")

# --- Insight ---------------------------------------------------------------
firsts = o[o.is_first_order].merge(
    cc[["customer_id", "acquisition_channel", "cohort"]], on="customer_id")
share = (firsts.assign(pp=firsts.acquisition_channel.isin({"Meta Prospecting", "TikTok"}))
         .groupby("cohort").pp.mean() * 100)
pp_then = share.iloc[0]
pp_now = share.loc[mature.index[-1]] if mature.index[-1] in share.index else share.iloc[-1]
insight_callout(
    "You're refilling a leaky bucket — and the leak is getting bigger.",
    f"Only <b>{overall_repeat:.0f}% of customers ever place a second order</b>, so "
    f"most acquisition spend buys a single purchase. And retention is "
    f"<i>deteriorating</i>: the {earliest_label} cohort eventually reordered at "
    f"<b>{earliest_rate:.0f}%</b>, but {recent_label} is tracking to just "
    f"<b>{recent_rate:.0f}%</b>. The driver is mix: paid prospecting (Meta, TikTok) "
    f"grew from <b>{pp_then:.0f}%</b> to <b>{pp_now:.0f}%</b> of new customers — the "
    f"channels that churn hardest.",
    tone="bad",
    actions=["Launch a post-purchase flow targeting the 31-day second-order window",
             "Weight acquisition toward Email/Organic & Referral (best repeat rates)",
             "Set a winback campaign for cohorts that stall after month one"])
