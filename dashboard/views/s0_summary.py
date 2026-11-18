"""요약 — F6 (US-01, US-02 / AC-01, AC-02). docs/05_design/UI_SPECIFICATION.md 5-1절.

결론 문장 → 지표 → 기회·위험 카드 → 공시 Q&A 바로가기.
결론·카드는 analysis/build_summary_cards.py 가 만든 data/processed/summary_cards.json (전체 기간 기준 고정 요약).
필터는 카드를 거르기만 한다 (U1 제안대로 — 팀 확인 전).
"""
import json
from datetime import date

import streamlit as st

from core import data, filters as flt, ui
from views import s1_trend, s2_policy, s3_tech, s4_compare, s5_linkage, s6_qa

CARDS_PATH = data.PROCESSED / "summary_cards.json"
# 카드의 출처 화면 → app.py 와 같은 함수·url_path (st.switch_page 가 찾는다)
SCREENS = {
    "trend": (s1_trend.render, "이슈·트렌드"), "policy": (s2_policy.render, "규제·정책"),
    "tech": (s3_tech.render, "기술·생산"), "compare": (s4_compare.render, "기업 비교"),
    "linkage": (s5_linkage.render, "뉴스-공시 연계"), "qa": (s6_qa.render, "공시 Q&A"),
}
LIMITS_S0 = [
    "결론과 카드는 전체 기간 데이터로 만든 고정 요약입니다. 사이드바 필터는 카드를 거르기만 하고 문장을 다시 쓰지 않습니다.",
    "결론·카드 문구는 Claude가 데이터(감성 라벨·LLM 이슈 이름·공시)로 초안을 쓰고 팀이 확인했습니다. 근거 기사·건수·기간은 "
    "analysis/build_summary_cards.py 가 데이터에서 뽑습니다.",
    "기회/위험 건수는 LLM 감성 라벨(표본 정확도 85.0%) 기준입니다. 이슈 이름(LLM 추출)은 사람 검수 전입니다.",
]


@st.cache_data(show_spinner=False)
def _load_cards() -> dict:
    return json.loads(CARDS_PATH.read_text(encoding="utf-8"))


def _page(screen: str):
    fn, title = SCREENS[screen]
    return st.Page(fn, title=title, url_path=screen)


def _visible(card: dict, filters: dict) -> bool:
    """카드 태그(기간·기업·키워드)가 적용 필터와 겹치는가 (U1). 기업 태그가 없는 카드는 산업 전체 카드라 기업으로 거르지 않는다."""
    t = card["tags"]
    s, e = filters["period"]
    if date.fromisoformat(t["end"]) < s or date.fromisoformat(t["start"]) > e:
        return False
    if t["companies"] and not set(t["companies"]) & set(filters["companies"]):
        return False
    if t["keywords"] and not set(t["keywords"]) & set(filters["keywords"]):
        return False
    return True


def _apply_card_filters(card: dict) -> None:
    """L1 — 카드 태그를 사이드바 필터로 넣는다 (위젯 값은 콜백에서만 바꿀 수 있다, 4-4절)."""
    lo, hi = flt.defaults()["period"]
    t = card["tags"]
    period = (max(lo, date.fromisoformat(t["start"])), min(hi, date.fromisoformat(t["end"])))
    companies = [c for c in data.COMPANIES if c in t["companies"]] or list(data.COMPANIES)
    keywords = [k for k in data.KEYWORDS if k in t["keywords"]] or list(data.KEYWORDS)
    st.session_state["flt_period"] = period
    st.session_state["flt_companies"] = companies
    st.session_state["flt_keywords"] = keywords
    st.session_state["filters"] = {"period": period, "companies": companies, "keywords": keywords}


def _card(card: dict) -> None:
    t = card["tags"]
    news = [e for e in card["evidence"] if e["kind"] == "기사"]
    discs = [e for e in card["evidence"] if e["kind"] == "공시"]
    with st.container(border=True):
        st.markdown(f"**{card['title']}**")
        st.markdown(card["desc"])
        tag = " · ".join(x for x in [", ".join(t["companies"]) or "산업 전체",
                                       ", ".join(k.removeprefix("CDMO ") for k in t["keywords"]),
                                       f"{t['start']} ~ {t['end']}"] if x)
        st.caption(f"{tag} · 관련 {card['type']} 기사 {card['n_articles']:,}건")
        st.markdown(f"근거: 기사 {len(news)} · 공시 {len(discs)}")
        lines = [f"- {e['date']} · [{e['title']}]({e['url']}) · {e['press']}" for e in news]
        lines += [f"- {e['date']} · :gray-badge[공시] [{e['title']}]({e['url']}) · {e['press']}" for e in discs]
        st.markdown("\n".join(lines))
        _, title = SCREENS[card["screen"]]
        if st.button(f"상세 보기 → {title}", key=f"s0_detail_{card['id']}", on_click=_apply_card_filters,
                     args=(card,)):
            st.switch_page(_page(card["screen"]))


def _ask_qa(question_key: str) -> None:
    q = (st.session_state.get(question_key) or "").strip()
    if q:
        st.session_state["qa_pending"] = q
        st.session_state.pop("qa_scope_override", None)


def _search_box() -> None:
    st.markdown("#### 직접 확인하기")
    with st.form("s0_qa_form", border=False):
        c1, c2 = st.columns([5, 1], gap="small", vertical_alignment="bottom")
        c1.text_input("공시에 물어보기", key="s0_question", placeholder="예: 에스티팜의 최근 단일판매·공급계약 금액은?",
                      label_visibility="collapsed")
        go = c2.form_submit_button("질문", type="primary", width="stretch", on_click=_ask_qa, args=("s0_question",))
    st.caption("공시 원문에 근거해 답합니다. 질문하면 공시 Q&A 화면으로 이동합니다.")
    if go and st.session_state.get("qa_pending"):
        st.switch_page(_page("qa"))


def render():
    filters = st.session_state["filters"]
    ui.header("요약", "지금 주목할 기회와 위험 요인은 무엇인가?", filters)
    if ui.no_selection(filters, "S0"):
        ui.limits(LIMITS_S0)
        return
    try:
        summary = _load_cards()
    except FileNotFoundError:
        ui.pending("기회·위험 결론 문장과 카드 (근거 뉴스·공시 링크 포함)", "analysis/build_summary_cards.py")
        ui.limits(LIMITS_S0)
        return
    except Exception as e:
        ui.data_error(CARDS_PATH, e)
        ui.limits(LIMITS_S0)
        return

    cards = [c for c in summary["cards"] if c["evidence"]]          # 근거 없는 카드는 보이지 않는다 (N6)
    shown = [c for c in cards if _visible(c, filters)]
    with st.container(border=True):
        st.markdown(f"{summary['conclusion']} :gray-badge[{summary['basis']}]")
        st.caption("근거: 아래 카드의 기사·공시 링크 · 감성 라벨 전체 기사 기준")

    try:
        sent = data.filter_news(filters).merge(data.sentiment_frame(), on="url")
        n_links = data.filter_links(filters).rcept_no.nunique()
        analysed, linked = f"{len(sent):,}건", f"{n_links:,}건"
    except Exception:
        analysed = linked = "—"
    ui.kpis([
        {"label": "▲ 기회 요인", "value": f"{sum(c['type'] == '기회' for c in shown)}개",
         "help": "현재 필터와 겹치는 기회 카드 수"},
        {"label": "▼ 위험 요인", "value": f"{sum(c['type'] == '위험' for c in shown)}개",
         "help": "현재 필터와 겹치는 위험 카드 수"},
        {"label": "분석 기사", "value": analysed, "help": "현재 필터에서 LLM 감성 라벨이 있는 기사 수 (중복 제외)"},
        {"label": "연결 공시", "value": linked, "help": "현재 필터에서 뉴스와 연결된 공시 수 (뉴스-공시 연계 화면과 같음)"},
    ])
    st.divider()

    if not shown:
        with st.container(border=True):
            st.markdown("현재 필터에 해당하는 요약 없음")
            st.button("필터 초기화", key="empty_reset_S0", on_click=flt.reset)
    else:
        left, right = st.columns(2, gap="medium")
        for col, kind, head in ((left, "기회", ":blue-badge[▲ 기회 요인]"), (right, "위험", ":red-badge[▼ 위험 요인]")):
            with col:
                st.markdown(f"#### {head}")
                group = [c for c in shown if c["type"] == kind]
                if not group:
                    st.caption("현재 필터에 해당하는 카드가 없습니다")
                for c in group:
                    _card(c)
    st.divider()
    _search_box()
    ui.limits(LIMITS_S0)
