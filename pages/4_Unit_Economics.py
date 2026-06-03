"""Unit Economics — Are we making money per customer, or buying revenue at a loss?"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import lib
from lib import (load, setup_page, render_sidebar, apply_filters, page_title,
                 section, insight_kpi, insight_callout, status_pill, H,
                 chart_layout, channel_economics, fmt_money, money_compact,
                 INK, INK_SOFT, SUBTLE, MUTE, ACCENT, GOOD, BAD, WARN, GRID,
                 LINE, CARD, GOOD_SOFT, WARN_SOFT, BAD_SOFT, CHANNEL_COLORS,
                 TARGET_LTV_CAC, TARGET_PAYBACK)

setup_page("Unit Economics")
c0, o0, a0, f0 = load()
flt = render_sidebar(c0, o0, a0, f0, active="Unit Economics")
c, o, a, f = apply_filters(c0, o0, a0, f0, flt)
if o.empty or c.empty:
    st.warning("No data for the current filter selection. Widen your filters.")
    st.stop()

data_end = o.order_date.max()
blended_cac = c.acquisition_cost.mean()
cm_per_cust = o.groupby("customer_id").contribution.sum()
ltv_cm = cm_per_cust.mean()
ltv_cac = ltv_cm / blended_cac if blended_cac else 0
life = ((data_end.year - c.first_order_date.dt.year) * 12
        + (data_end.month - c.first_order_date.dt.month) + 1).clip(lower=1)
life.index = c.customer_id
total_cm = cm_per_cust.reindex(c.customer_id).fillna(0).sum()
monthly_rr = total_cm / life.sum()
payback_mo = blended_cac / monthly_rr if monthly_rr else 0

scalable = ltv_cac >= TARGET_LTV_CAC and payback_mo <= TARGET_PAYBACK
vtone = "good" if scalable else "warn"
diag = (f"Every acquisition dollar comes back — but slowly. At "
        f"<b>{ltv_cac:.1f}:1</b> with a <b>{payback_mo:.1f}-month</b> payback, the "
        f"brand clears breakeven yet sits below the 3:1 / &lt;3-month bar needed to "
        f"scale paid acquisition aggressively.")
page_title("Are we making money per customer — or buying revenue at a loss?", diag)

# --- KPI row ---------------------------------------------------------------
k = st.columns(4)
k[0].markdown(insight_kpi("LTV : CAC", f"{ltv_cac:.1f} : 1",
              insight="Healthy ≈ 3:1", pill="Below target" if ltv_cac < 3 else "Healthy",
              pill_tone="warn" if ltv_cac < 3 else "good"), unsafe_allow_html=True)
k[1].markdown(insight_kpi("Blended CAC", fmt_money(blended_cac, 0),
              insight="Avg cost to acquire a customer"), unsafe_allow_html=True)
k[2].markdown(insight_kpi("LTV (contribution margin)", fmt_money(ltv_cm, 0),
              insight="Lifetime margin per customer"), unsafe_allow_html=True)
k[3].markdown(insight_kpi("CAC payback", f"{payback_mo:.1f} mo",
              insight="Months of margin to recoup CAC",
              pill=f"Target <{TARGET_PAYBACK:.0f} mo",
              pill_tone="good" if payback_mo <= TARGET_PAYBACK else "warn"),
              unsafe_allow_html=True)

# --- Hero gauge + verdict --------------------------------------------------
section("The verdict: return on every acquisition dollar",
        "Measured against the 3:1 line most DTC brands need to fund growth.")
left, right = st.columns([3, 2])
with left:
    gauge = go.Figure(go.Indicator(
        mode="gauge+number", value=ltv_cac,
        number=dict(suffix=" : 1", font=dict(size=46, color=INK)),
        gauge=dict(
            axis=dict(range=[0, 4], tickwidth=1, tickcolor=MUTE,
                      tickvals=[0, 1, 2, 3, 4]),
            bar=dict(color=(WARN if ltv_cac < 3 else GOOD), thickness=0.55),
            bgcolor="rgba(0,0,0,0)", borderwidth=0,
            steps=[dict(range=[0, 1], color=BAD_SOFT),
                   dict(range=[1, 2], color=WARN_SOFT),
                   dict(range=[2, 3], color="#FBF6EC"),
                   dict(range=[3, 4], color=GOOD_SOFT)],
            threshold=dict(line=dict(color=GOOD, width=4), thickness=0.85,
                           value=3.0))))
    gauge.update_layout(height=300, margin=dict(l=30, r=30, t=20, b=0),
                        paper_bgcolor="rgba(0,0,0,0)",
                        font=dict(family="Inter, system-ui, sans-serif", color=INK))
    st.plotly_chart(gauge, width="stretch")
with right:
    st.markdown("<div style='height:1.4rem'></div>", unsafe_allow_html=True)
    verdict = "Below healthy" if ltv_cac < 3 else "Healthy"
    gap_pct = (3 - ltv_cac) / 3 * 100
    answer = ("Not yet — fix the mix first" if not scalable else "Yes — economics clear the bar")
    st.markdown(H(
        f"""<div class="pcard" style="background:{CARD};border:1px solid {LINE};
        border-radius:14px;padding:1.1rem 1.2rem">
        <div style="margin-bottom:.5rem">{status_pill("Can we scale paid? " + answer, vtone)}</div>
        <div style="font-size:.78rem;color:{SUBTLE};font-weight:700;
        text-transform:uppercase;letter-spacing:.08em">Reading</div>
        <div style="font-size:1.35rem;font-weight:800;color:{WARN};margin:.15rem 0">
        {verdict} — {ltv_cac:.1f}:1</div>
        <div style="color:{INK_SOFT};font-size:.9rem;line-height:1.55">
        For every <b>{fmt_money(blended_cac,0)}</b> spent to acquire a customer, the
        brand earns back <b>{fmt_money(ltv_cm,0)}</b> in lifetime contribution margin —
        clearing breakeven but <b>{gap_pct:.0f}% short</b> of 3:1. The business isn't
        losing money per customer; it just lacks the headroom to scale paid
        acquisition hard.</div></div>"""), unsafe_allow_html=True)

# --- CM per order over time ------------------------------------------------
section("Contribution margin per order, over time")
cmo = o.groupby("month").contribution.mean().reset_index()
fig = go.Figure()
fig.add_scatter(x=cmo.month, y=cmo.contribution, mode="lines",
                line=dict(color=ACCENT, width=3), fill="tozeroy",
                fillcolor="rgba(99,91,255,.08)",
                hovertemplate="%{x|%b %Y}<br>%{y:$.2f} margin/order<extra></extra>")
fig.add_hline(y=cmo.contribution.mean(), line_dash="dot", line_color=SUBTLE,
              annotation_text=f"avg {fmt_money(cmo.contribution.mean(),0)}",
              annotation_position="right")
fig.update_yaxes(tickprefix="$", range=[0, cmo.contribution.max() * 1.25])
st.plotly_chart(chart_layout(fig, h=300, legend=False), width="stretch")
st.caption("Per-order margin is stable around "
           f"{fmt_money(cmo.contribution.mean(),0)} — pricing and discounting aren't "
           "the problem. The weak LTV:CAC comes from how *few* orders each customer "
           "places, not thin margins on the ones they do.")

# --- Payback by channel ----------------------------------------------------
section("How long each channel takes to pay back")
ch_idx = c.set_index("customer_id").acquisition_channel
cm_c = cm_per_cust.reindex(c.customer_id).fillna(0)
pdf = pd.DataFrame({"cm": cm_c.values, "life": life.reindex(c.customer_id).values,
                    "ch": ch_idx.reindex(c.customer_id).values})
g = pdf.groupby("ch")
rr_ch = g.cm.sum() / g.life.sum()
cac_ch = c.groupby("acquisition_channel").acquisition_cost.mean()
pb = (cac_ch / rr_ch).sort_values(ascending=False).reset_index()
pb.columns = ["channel", "payback"]
fig2 = go.Figure(go.Bar(
    x=pb.payback, y=pb.channel, orientation="h",
    marker_color=[CHANNEL_COLORS[ch] for ch in pb.channel],
    text=[f"{v:.1f} mo" for v in pb.payback], textposition="outside",
    textfont=dict(color=INK),
    hovertemplate="%{y}<br>%{x:.1f} months to recoup CAC<extra></extra>"))
fig2.add_vline(x=TARGET_PAYBACK, line_dash="dash", line_color=GOOD,
               annotation_text=f"target <{TARGET_PAYBACK:.0f} mo",
               annotation_font=dict(color=GOOD, size=11))
fig2.update_xaxes(title="Months to recoup CAC →", range=[0, pb.payback.max() * 1.2])
st.plotly_chart(chart_layout(fig2, h=320, legend=False), width="stretch")

# --- Insight ---------------------------------------------------------------
eco = channel_economics(c, o)
best = eco.sort_values("ltv_cac", ascending=False).iloc[0]
worst = eco.sort_values("ltv_cac").iloc[0]
insight_callout(
    "The blended number looks fine — and that's the trap.",
    f"At <b>{ltv_cac:.1f}:1</b> blended, the economics read as merely \"a bit below "
    f"target\" — the kind of number that invites scaling spend to grow into it. But "
    f"the average hides a split business: <b>{best.acquisition_channel}</b> returns "
    f"<b>{best.ltv_cac:.0f}:1</b> while <b>{worst.acquisition_channel}</b> returns "
    f"just <b>{worst.ltv_cac:.1f}:1</b> and pays back slowest. More budget at the "
    f"blended rate mostly funds the weak channels.",
    tone="warn",
    actions=["Scale paid only on channels already clearing 3:1 with <3-month payback",
             "Reallocate from the slowest-payback channels into Email/Referral",
             "Re-underwrite blended CAC monthly as the channel mix shifts"])
