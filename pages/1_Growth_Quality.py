"""Growth Quality — the score behind the headline."""
import streamlit as st
import plotly.graph_objects as go
import lib
from lib import (load, setup_page, render_sidebar, apply_filters, page_title,
                 section, score_card, insight_callout, status_pill, H,
                 chart_layout, growth_quality_score,
                 INK, INK_SOFT, SUBTLE, MUTE, ACCENT, GOOD, BAD, WARN, LINE,
                 CARD, GRID)

setup_page("Growth Quality")
c0, o0, a0, f0 = load()
flt = render_sidebar(c0, o0, a0, f0, active="Growth Quality")
c, o, a, f = apply_filters(c0, o0, a0, f0, flt)
if o.empty:
    st.warning("No data for the current filter selection. Widen your filters.")
    st.stop()

score, status, tone, comps, m = growth_quality_score(c, o)
page_title("How healthy is the growth, really?",
           f"A single composite — <b>{score}/100, {status}</b> — across eight "
           "growth-health signals, each scored against its benchmark so one strong "
           "number can't hide a weak one.")

section("The score", "Eight weighted signals roll up into one growth-health read.")
sl, sr = st.columns([1, 1])
with sl:
    st.markdown(score_card(
        score, status, tone,
        "Acquisition momentum is strong, but returning-revenue share and LTV:CAC "
        "sit below target — the score lands in Watchlist rather than Healthy."),
        unsafe_allow_html=True)
with sr:
    weakest = min(comps.items(), key=lambda kv: kv[1][0])
    strongest = max(comps.items(), key=lambda kv: kv[1][0])
    st.markdown(H(
        f"""<div class="pcard" style="background:{CARD};border:1px solid {LINE};
        border-radius:16px;padding:1.15rem 1.25rem;height:100%">
        <div style="font-size:.74rem;color:{SUBTLE};font-weight:700;
          text-transform:uppercase;letter-spacing:.08em;margin-bottom:.6rem">
          Reading the score</div>
        <div style="font-size:.9rem;color:{INK_SOFT};line-height:1.55">
        The brand's strongest signal is <b>{strongest[0].lower()}</b>
        ({strongest[1][1]}), and its weakest is <b>{weakest[0].lower()}</b>
        ({weakest[1][1]}). Closing the gap on returning-revenue share and LTV:CAC
        is what moves this from <b>Watchlist</b> toward <b>Healthy (80+)</b>.</div>
        <div style="margin-top:.8rem;display:flex;gap:.4rem;flex-wrap:wrap">
        {status_pill("Healthy 80–100", "good")}
        {status_pill("Watchlist 60–79", "warn")}
        {status_pill("At Risk <60", "bad")}</div>
        </div>"""), unsafe_allow_html=True)

# --- component bar (existing score data, just visualized) ------------------
section("Signal breakdown", "Each signal scored 0–100 against its benchmark.")
labels = list(comps.keys())
scores = [comps[k][0] for k in labels]
disp = [comps[k][1] for k in labels]
colors = [GOOD if s >= 70 else (WARN if s >= 50 else BAD) for s in scores]
fig = go.Figure(go.Bar(
    x=scores, y=labels, orientation="h",
    marker=dict(color=colors), text=[f"  {d}" for d in disp],
    textposition="outside", textfont=dict(color=INK, size=12),
    hovertemplate="%{y}<br>score %{x:.0f}/100<extra></extra>"))
fig.add_vline(x=70, line_dash="dash", line_color=GOOD,
              annotation_text="healthy", annotation_position="top",
              annotation_font=dict(color=GOOD, size=11))
fig.update_xaxes(range=[0, 112], title="")
fig.update_layout(yaxis=dict(autorange="reversed"))
st.plotly_chart(chart_layout(fig, h=380, legend=False), width="stretch")

insight_callout(
    "Strong top of funnel, soft middle.",
    f"The score is dragged down by the things that compound — "
    f"<b>returning-revenue share</b> and <b>LTV:CAC</b> — while the things that "
    f"are easy to buy — revenue growth and order volume — score well. That's the "
    f"signature of a brand growing on acquisition rather than loyalty.",
    tone="warn",
    actions=["Treat returning-revenue share as the weekly north-star",
             "Move LTV:CAC toward 3:1 by reallocating to high-retention channels",
             "Re-check the score each Monday alongside the Founder Memo"])
