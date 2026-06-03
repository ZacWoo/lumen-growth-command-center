"""Recommendations — the action backlog and the Weekly Founder Memo."""
import datetime as dt
import streamlit as st
import lib
from lib import (load, setup_page, render_sidebar, apply_filters, page_title,
                 section, action_card, status_pill, build_founder_memo,
                 recommended_moves, H,
                 INK, INK_SOFT, SUBTLE, MUTE, ACCENT, GOOD, BAD, WARN, LINE,
                 CARD, GOOD_SOFT, BAD_SOFT, ACCENT_SOFT, BRAND)

setup_page("Recommendations")
c0, o0, a0, f0 = load()
flt = render_sidebar(c0, o0, a0, f0, active="Recommendations")
c, o, a, f = apply_filters(c0, o0, a0, f0, flt)
if o.empty:
    st.warning("No data for the current filter selection. Widen your filters.")
    st.stop()

page_title("What should we do next?",
           "The highest-leverage moves this week, and a one-click founder memo "
           "you can forward to the team every Monday.")

# --- action backlog --------------------------------------------------------
section("Action backlog", "Ranked by priority and expected impact.")
moves = recommended_moves(c, o, a)
# render in row-pairs so each row's two cards share one (equal) height
for i in range(0, len(moves), 2):
    row = st.columns(2)
    for j, mv in enumerate(moves[i:i + 2]):
        row[j].markdown(action_card(**mv), unsafe_allow_html=True)
    st.markdown("<div style='height:.7rem'></div>", unsafe_allow_html=True)

# --- weekly founder memo ---------------------------------------------------
section("Weekly Founder Memo",
        "Auto-drafted from this week's data — wins, risks, what changed, and the "
        "actions to take.")

memo_md, memo = build_founder_memo(c, o, a)
gen = st.button("📝  Generate Weekly Founder Memo", type="primary")

if gen or st.session_state.get("memo_open"):
    st.session_state["memo_open"] = True

    def _col(items, tone, title, icon):
        bg = {"good": GOOD_SOFT, "bad": BAD_SOFT, "neutral": ACCENT_SOFT}[tone]
        fg = {"good": GOOD, "bad": BAD, "neutral": ACCENT}[tone]
        lis = "".join(f'<li style="margin:.28rem 0;color:{INK_SOFT};'
                      f'font-size:.88rem;line-height:1.45">{x}</li>' for x in items)
        return (f'<div class="pcard" style="background:{CARD};border:1px solid {LINE};'
                f'border-radius:14px;padding:1rem 1.1rem;height:100%">'
                f'<div style="display:inline-block;background:{bg};color:{fg};'
                f'font-weight:800;font-size:.8rem;border-radius:999px;'
                f'padding:.2rem .6rem;margin-bottom:.55rem">{icon} {title}</div>'
                f'<ul style="margin:0;padding-left:1.1rem">{lis}</ul></div>')

    today = dt.date.today().strftime("%B %d, %Y")
    st.markdown(H(
        f"""<div style="background:linear-gradient(135deg,{INK} 0%,#0B2A49 100%);
        border-radius:16px;padding:1.2rem 1.4rem;margin:.3rem 0 1rem;
        box-shadow:0 8px 28px rgba(10,37,64,.10)">
        <div style="display:flex;justify-content:space-between;align-items:center;
          flex-wrap:wrap;gap:.5rem">
          <div>
            <div style="color:#fff;font-weight:800;font-size:1.15rem">
              {BRAND} — Weekly Founder Memo</div>
            <div style="color:#9DB2D4;font-size:.82rem;margin-top:.1rem">{today}</div>
          </div>
          <div style="background:rgba(255,255,255,.12);color:#fff;font-weight:800;
            border-radius:999px;padding:.3rem .8rem;font-size:.85rem">
            Growth Quality {memo['score']}/100 · {memo['status']}</div>
        </div></div>"""), unsafe_allow_html=True)

    r1 = st.columns(2)
    r1[0].markdown(_col(memo["wins"], "good", "Top 3 wins", "🟢"),
                   unsafe_allow_html=True)
    r1[1].markdown(_col(memo["risks"], "bad", "Top 3 risks", "🔴"),
                   unsafe_allow_html=True)
    st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)
    r2 = st.columns(2)
    r2[0].markdown(_col(memo["changed"], "neutral", "What changed", "📈"),
                   unsafe_allow_html=True)
    r2[1].markdown(_col(memo["actions"], "neutral", "Recommended actions", "✅"),
                   unsafe_allow_html=True)

    st.markdown("<div style='height:.9rem'></div>", unsafe_allow_html=True)
    st.download_button("⬇️  Download memo (Markdown)", memo_md,
                       file_name=f"{BRAND.replace(' & ','_')}_founder_memo_"
                                 f"{dt.date.today().isoformat()}.md",
                       mime="text/markdown")
else:
    st.markdown(
        f"<div style='color:{SUBTLE};font-size:.9rem'>Click "
        f"<b>Generate Weekly Founder Memo</b> to draft this week's summary "
        f"and download it as Markdown.</div>", unsafe_allow_html=True)
