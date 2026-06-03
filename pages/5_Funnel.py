"""Funnel — Where do buyers drop off before they pay?"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import lib
from lib import (load, setup_page, render_sidebar, apply_filters, page_title,
                 section, insight_kpi, insight_callout, chart_layout,
                 fmt_money, fmt_pct, INK, INK_SOFT, SUBTLE, MUTE, ACCENT,
                 ACCENT_CYAN, GOOD, BAD, WARN, GRID, LINE, CHANNEL_COLORS)

setup_page("Funnel")
c0, o0, a0, f0 = load()
flt = render_sidebar(c0, o0, a0, f0, active="Funnel")
c, o, a, f = apply_filters(c0, o0, a0, f0, flt)
if f.empty:
    st.warning("No data for the current filter selection. Widen your filters.")
    st.stop()

STEPS = ["sessions", "product_views", "add_to_cart", "checkout_started", "purchased"]
STEP_LABELS = ["Sessions", "Product views", "Add to cart", "Checkout started",
               "Purchased"]

totals = f[STEPS].sum()
overall_conv = totals["purchased"] / totals["sessions"] * 100 if totals["sessions"] else 0
step_conv = [totals[STEPS[i + 1]] / totals[STEPS[i]] * 100 if totals[STEPS[i]] else 0
             for i in range(len(STEPS) - 1)]
drops = [100 - sc for sc in step_conv]
worst_step_i = int(np.argmax(drops))
worst_step_label = f"{STEP_LABELS[worst_step_i]} → {STEP_LABELS[worst_step_i + 1]}"

by_ch = f.groupby("channel")[STEPS].sum()
by_ch["checkout_compl"] = by_ch.purchased / by_ch.checkout_started * 100
worst_ch, worst_ch_val = by_ch.checkout_compl.idxmin(), by_ch.checkout_compl.min()
best_ch, best_ch_val = by_ch.checkout_compl.idxmax(), by_ch.checkout_compl.max()

diag = (f"Just <b>{overall_conv:.1f}%</b> of sessions end in a purchase. The "
        f"steepest sitewide drop is at <b>{worst_step_label.lower()}</b>, but the "
        f"most telling leak is checkout — where <b>{worst_ch}</b> traffic completes "
        f"at only <b>{worst_ch_val:.0f}%</b> vs <b>{best_ch_val:.0f}%</b> for {best_ch}.")
page_title("Where do buyers drop off before they pay?", diag)

# --- KPI row ---------------------------------------------------------------
k = st.columns(3)
k[0].markdown(insight_kpi("Sessions → purchase", fmt_pct(overall_conv, 1),
              insight="Overall conversion rate"), unsafe_allow_html=True)
k[1].markdown(insight_kpi("Biggest drop-off step", worst_step_label,
              insight=f"{drops[worst_step_i]:.0f}% of users lost here",
              pill="Mid-funnel", pill_tone="warn"), unsafe_allow_html=True)
k[2].markdown(insight_kpi("Worst checkout channel", worst_ch,
              insight=f"only {worst_ch_val:.0f}% complete checkout",
              pill="Leak", pill_tone="bad"), unsafe_allow_html=True)

# --- Hero funnel with channel + device filters -----------------------------
section("Where the funnel leaks", "Filter by channel and device to isolate the drop-off.")
fl1, fl2, _ = st.columns([1.2, 1.2, 2.6])
chan_opts = ["All channels"] + [ch for ch in CHANNEL_COLORS if ch in set(f.channel)]
dev_opts = ["All devices"] + sorted(f.device.unique()) if "device" in f.columns else ["All devices"]
choice = fl1.selectbox("Channel", chan_opts)
dev_choice = fl2.selectbox("Device", dev_opts)

fsub = f.copy()
if choice != "All channels":
    fsub = fsub[fsub.channel == choice]
if dev_choice != "All devices" and "device" in fsub.columns:
    fsub = fsub[fsub.device == dev_choice]
vals = fsub[STEPS].sum().values

funnel = go.Figure(go.Funnel(
    y=STEP_LABELS, x=vals, textposition="inside",
    texttemplate="%{value:,.0f}  (%{percentInitial:.0%})",
    textfont=dict(color="white", size=13),
    marker=dict(color=["#635BFF", "#7D77FF", "#9B95FF", WARN, GOOD]),
    connector=dict(line=dict(color=LINE, width=1)),
    hovertemplate="%{y}<br>%{x:,.0f} users<br>%{percentPrevious:.0%} of prior step"
                  "<extra></extra>"))
funnel.update_layout(height=400, margin=dict(l=10, r=10, t=10, b=10),
                     plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                     font=dict(family="Inter, system-ui, sans-serif", color=INK, size=12))
st.plotly_chart(funnel, width="stretch")

# --- Checkout completion by channel ----------------------------------------
section("Checkout completion rate by channel")
ccr = by_ch.sort_values("checkout_compl").reset_index()
fig = go.Figure(go.Bar(
    x=ccr.checkout_compl, y=ccr.channel, orientation="h",
    marker_color=[BAD if v < 60 else (WARN if v < 72 else GOOD) for v in ccr.checkout_compl],
    text=[f"{v:.0f}%" for v in ccr.checkout_compl], textposition="outside",
    textfont=dict(color=INK),
    hovertemplate="%{y}<br>%{x:.0f}% of checkouts completed<extra></extra>"))
fig.add_vline(x=by_ch.purchased.sum() / by_ch.checkout_started.sum() * 100,
              line_dash="dot", line_color=SUBTLE,
              annotation_text="site avg", annotation_position="top")
fig.update_xaxes(title="% of started checkouts that complete →", ticksuffix="%",
                 range=[0, 100])
st.plotly_chart(chart_layout(fig, h=320, legend=False), width="stretch")

insight_callout(
    "The leak isn't your checkout page — it's who you're sending to it.",
    f"Sitewide, the steepest drop is mid-funnel (browsers who never add to cart), but "
    f"the most telling leak is the final step: checkout completion ranges from "
    f"<b>{best_ch_val:.0f}% for {best_ch}</b> down to <b>{worst_ch_val:.0f}% for "
    f"{worst_ch}</b>. Same checkout page, wildly different results — the page isn't "
    f"broken, the <i>traffic</i> is. {worst_ch} sends low-intent, discount-primed "
    f"clicks that reach checkout and bail (and most of it lands on mobile).",
    tone="bad",
    actions=["Prioritize a mobile checkout/express-pay fix — the device gap is widest",
             f"Tighten {worst_ch} targeting & creative toward higher purchase intent",
             "A/B test guest checkout and fewer form fields on paid-social landings"])
