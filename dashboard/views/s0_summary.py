"""요약 — F6 (US-01, US-02 / AC-01, AC-02). docs/05_design/UI_SPECIFICATION.md 5-1절.

짜임새 (2026-11-18 개편, 레퍼런스 대시보드의 "큰 숫자 → 카드 → 차트 → 최근 목록" 순서):
  머리: 제목·필터 상태 | 공시 검색창(오른쪽)
  ① 결론 한 줄 + 숫자 부제 (전문은 펼치기)
  ② 지표 4개 + 최근 3개월 증감
  ③ 월별 기회 vs 위험 차트 | ⑥ 공시에 물어보기 카드
  ④ 기회 요인 타일 / ⑤ 위험 요인 타일 (3열)
  ⑦ 최근 주요 공시 표 (행 선택 → 이 공시에 질문)
결론·카드는 analysis/build_summary_cards.py 가 만든 data/processed/summary_cards.json (전체 기간 고정 요약).
필터는 카드를 거르고 지표·차트·표를 다시 센다 (U1 제안대로 — 팀 확인 전). 사용자 CSS 는 쓰지 않는다 (명세 2절).
"""
import json
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import data, filters as flt, theme, ui
from views import s1_trend, s2_policy, s3_tech, s4_compare, s5_linkage, s6_qa

CARDS_PATH = data.PROCESSED / "summary_cards.json"
# 카드의 출처 화면 → app.py 와 같은 함수·url_path (st.switch_page 가 찾는다)
SCREENS = {
    "trend": (s1_trend.render, "이슈·트렌드"), "policy": (s2_policy.render, "규제·정책"),
    "tech": (s3_tech.render, "기술·생산"), "compare": (s4_compare.render, "기업 비교"),
    "linkage": (s5_linkage.render, "뉴스-공시 연계"), "qa": (s6_qa.render, "공시 Q&A"),
}
EXAMPLES = s6_qa.EXAMPLES
WINDOW = pd.Timedelta(days=91)   # 증감 비교 구간: 최근 3개월 vs 직전 3개월
LIMITS_S0 = [
    "결론과 카드는 전체 기간 데이터로 만든 고정 요약입니다. 사이드바 필터는 카드를 거르고 지표·차트·표를 다시 셀 뿐, 결론 문장을 다시 쓰지 않습니다.",
    "결론·카드 문구는 Claude가 데이터(감성 라벨·LLM 이슈 이름·공시)로 초안을 쓰고 팀이 확인했습니다. 근거 기사·건수·기간은 "
    "analysis/build_summary_cards.py 가 데이터에서 뽑습니다.",
    "기회/위험 건수는 LLM 감성 라벨(표본 정확도 85.0%) 기준입니다. 이슈 이름(LLM 추출)은 표본 30건 검수에서 98.7%(층 가중)가 정확했습니다.",
    "증감은 필터 기간 끝에서 최근 3개월과 그 직전 3개월을 비교합니다.",
]


@st.cache_data(show_spinner=False)
def _load_cards() -> dict:
    return json.loads(CARDS_PATH.read_text(encoding="utf-8"))


def _page(screen: str):
    fn, title = SCREENS[screen]
    return st.Page(fn, title=title, url_path=screen)


# ---------------------------------------------------------------- 상태 바꾸기 (콜백)

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


def _ask(question: str) -> None:
    q = (question or "").strip()
    if q:
        st.session_state["qa_pending"] = q
        st.session_state.pop("qa_scope_override", None)


def _ask_from_box() -> None:
    _ask(st.session_state.get("s0_question"))


def _ask_about(row: dict) -> None:
    """L8 — S6 전용 범위만 그 공시의 기업·제출일로 바꾼다 (S4·S5 와 같은 방식, 미결 Q11)."""
    st.session_state["qa_scope_override"] = {"corp_names": [row["corp_name"]], "date_from": row["rcept_date"],
                                             "date_to": row["rcept_date"]}


def _select_disclosure() -> None:
    rows = st.session_state["s0_disc_tbl"]["selection"]["rows"]
    ids = st.session_state.get("_s0_disc_ids", [])
    st.session_state["s0_rcept"] = ids[rows[0]] if rows and rows[0] < len(ids) else None


# ---------------------------------------------------------------- 집계

def _windows(filters: dict) -> tuple:
    end = pd.Timestamp(filters["period"][1])
    return end - WINDOW, end - 2 * WINDOW


def _change(series: pd.Series, filters: dict) -> int:
    """최근 3개월 건수 − 직전 3개월 건수 (series 는 날짜 열)."""
    recent_from, prev_from = _windows(filters)
    recent = int((series > recent_from).sum())
    prev = int(((series > prev_from) & (series <= recent_from)).sum())
    return recent - prev


def _kpis(sent: pd.DataFrame, links: pd.DataFrame, spikes: pd.DataFrame, filters: dict) -> None:
    opp, risk = sent[sent.label == "기회"], sent[sent.label == "위험"]
    linked = links.drop_duplicates("rcept_no")
    recent_from, _ = _windows(filters)
    n_recent_spikes = int((spikes.peak > recent_from).sum())
    ui.kpis([
        {"label": "▲ 기회 기사", "value": f"{len(opp):,}건", "delta": f"{_change(opp.date, filters):+,}건 최근 3개월",
         "help": "LLM 감성 라벨 '기회' 기사 수 (중복 제외). 증감은 최근 3개월 − 직전 3개월"},
        {"label": "▼ 위험 기사", "value": f"{len(risk):,}건", "delta": f"{_change(risk.date, filters):+,}건 최근 3개월",
         "delta_color": "inverse", "help": "LLM 감성 라벨 '위험' 기사 수. 늘면 빨간색"},
        {"label": "연결 공시", "value": f"{len(linked):,}건",
         "delta": f"{_change(pd.to_datetime(linked.rcept_date), filters):+,}건 최근 3개월",
         "help": "뉴스와 연결된 공시 수 (뉴스-공시 연계 화면과 같음)"},
        {"label": "급증 시점", "value": f"{len(spikes):,}회", "delta": f"최근 3개월 {n_recent_spikes}회",
         "delta_color": "off", "help": "주별 기사량 z ≥ 3 (이슈·트렌드 화면과 같음)"},
    ])


# ---------------------------------------------------------------- 그리기

def _header(filters: dict) -> None:
    left, right = st.columns([3, 1.4], gap="medium", vertical_alignment="bottom")
    with left:
        st.title("요약")
        st.caption(f"현재 필터: {flt.status_line(filters)}")
    with right:
        with st.form("s0_qa_form", border=False):
            c1, c2 = st.columns([4, 1.2], gap="small", vertical_alignment="bottom")
            c1.text_input("공시에 물어보기", key="s0_question", placeholder="공시에 물어보기…",
                          label_visibility="collapsed")
            go_ = c2.form_submit_button("질문", type="primary", width="stretch", on_click=_ask_from_box)
        if go_ and st.session_state.get("qa_pending"):
            st.switch_page(_page("qa"))


def _hero(summary: dict) -> None:
    counts = summary.get("label_counts", {})
    opp, risk = counts.get("기회", 0), counts.get("위험", 0)
    total = sum(counts.values())
    ratio = round(opp / risk) if risk else None
    lean = "기회 우위" if risk and opp >= 2 * risk else "위험 우위" if opp and risk >= 2 * opp else "기회·위험 혼재"
    st.subheader(f"지금 CDMO 시장은 \"{lean}\"")
    parts = [f"기회 기사가 위험의 {ratio}배" if ratio else None, f"기사 {total:,}건 분석",
             f":gray-badge[{summary['basis']}]"]
    st.markdown(" · ".join(p for p in parts if p))
    with st.expander("결론 전문"):
        st.markdown(summary["conclusion"])
        st.caption("근거: 아래 기회·위험 요인의 기사·공시 링크 · 감성 라벨 전체 기사 기준")


def _tile(card: dict) -> None:
    t = card["tags"]
    news = [e for e in card["evidence"] if e["kind"] == "기사"]
    discs = [e for e in card["evidence"] if e["kind"] == "공시"]
    with st.container(border=True):
        st.markdown(f"**{card['title']}**")
        st.caption(f"기사 {card['n_articles']:,}건 · {', '.join(t['companies']) or '산업 전체'} · "
                   f"{t['start'][:7]} ~ {t['end'][:7]}")
        c1, c2 = st.columns(2, gap="small")
        with c1.popover(f"근거 {len(news) + len(discs)}", width="stretch"):
            st.caption(card["desc"])
            lines = [f"- {e['date']} · [{e['title']}]({e['url']}) · {e['press']}" for e in news]
            lines += [f"- {e['date']} · :gray-badge[공시] [{e['title']}]({e['url']})" for e in discs]
            st.markdown("\n".join(lines))
        _, title = SCREENS[card["screen"]]
        if c2.button("자세히 →", key=f"s0_detail_{card['id']}", width="stretch", on_click=_apply_card_filters,
                     args=(card,), help=f"{title} 화면으로 이동하며 카드의 기간·기업·키워드를 필터로 넣습니다"):
            st.switch_page(_page(card["screen"]))


def _tiles(cards: list, kind: str) -> None:
    head = ":blue-badge[▲ 기회 요인]" if kind == "기회" else ":red-badge[▼ 위험 요인]"
    group = [c for c in cards if c["type"] == kind]
    st.markdown(f"#### {head} {len(group)}")
    if not group:
        st.caption("현재 필터에 해당하는 요인이 없습니다")
        return
    for i in range(0, len(group), 3):
        cols = st.columns(3, gap="small")
        for col, card in zip(cols, group[i:i + 3]):
            with col:
                _tile(card)


def _trend_chart(sent: pd.DataFrame, filters: dict) -> None:
    mode = theme.current_mode()
    with st.container(border=True):
        st.markdown("#### 월별 기회 vs 위험")
        if sent.empty:
            st.caption("현재 필터에 해당하는 기사가 없습니다")
            return
        s, e = (pd.Timestamp(x) for x in filters["period"])
        months = pd.date_range(s.to_period("M").start_time, e.to_period("M").start_time, freq="MS")
        table = (sent.assign(m=sent.date.dt.to_period("M").dt.start_time)
                 .pivot_table(index="m", columns="label", values="news_id", aggfunc="count", fill_value=0)
                 .reindex(index=months, columns=["기회", "위험"], fill_value=0))
        fig = go.Figure([go.Bar(x=table.index, y=table[lb], name=lb,
                                marker_color=theme.SENTIMENT_COLOR[mode][lb],
                                hovertemplate="<b>%{fullData.name}</b> %{y:,}건<extra></extra>")
                         for lb in ("기회", "위험")])
        fig.update_layout(barmode="group")
        theme.style(fig, "time", height="sub")
        fig.update_layout(showlegend=True, legend_traceorder="normal")
        fig.update_xaxes(hoverformat="%Y-%m")
        key = f"s0_trend_{abs(hash((str(filters['period']), tuple(filters['companies']), tuple(filters['keywords']))))}"
        theme.show(fig, key=key, alt="월별 기회·위험 기사 수 (LLM 감성 라벨, 중복 제외)")
        out = table.copy()
        out.index = out.index.strftime("%Y-%m")
        ui.table_view(out.rename_axis("월").reset_index(), "월별 기회·위험 기사 수")


def _qa_card() -> None:
    with st.container(border=True):
        st.markdown("#### 공시에 물어보기")
        st.caption("5개사 공시 원문에서 근거를 찾아 답합니다. 근거가 없으면 답하지 않습니다.")
        for i, q in enumerate(EXAMPLES):
            if st.button(q, key=f"s0_example_{i}", width="stretch", on_click=_ask, args=(q,)):
                st.switch_page(_page("qa"))


def _recent_disclosures(filters: dict, links: pd.DataFrame) -> None:
    st.markdown("#### 최근 주요 공시")
    events = [c for c in data.MAIN_EVENTS if c in data.keyword_events(filters)]
    disc = data.filter_disclosures(filters, events)
    disc = disc[disc.is_amended == 0].sort_values(["rcept_date", "rcept_no"], ascending=False).head(10)
    if disc.empty:
        ui.empty("공시", "S0-recent")
        return
    n_news = links.groupby("rcept_no").url.nunique()
    st.session_state["_s0_disc_ids"] = disc.rcept_no.tolist()
    view = pd.DataFrame({
        "제출일": disc.rcept_date, "기업": disc.corp_name, "공시명": disc.report_nm, "분류": disc.event_class,
        "연결 기사": disc.rcept_no.map(n_news).fillna(0).astype(int), "DART": disc.url,
    })
    st.dataframe(view, hide_index=True, width="stretch", key="s0_disc_tbl", on_select=_select_disclosure,
                 selection_mode="single-row",
                 column_config={"공시명": st.column_config.TextColumn(width="large"),
                                "연결 기사": st.column_config.NumberColumn(help="이 공시와 연결된 뉴스 기사 수"),
                                "DART": st.column_config.LinkColumn("DART", display_text="원문")})
    st.caption(f"수주·증설·M&A·자금조달 공시 중 최근 {len(view)}건 (정정 제외). 행을 고르면 그 공시에 질문할 수 있습니다.")
    sel = disc[disc.rcept_no == st.session_state.get("s0_rcept")]
    if not sel.empty:
        row = sel.iloc[0].to_dict()
        if st.button(f"이 공시에 질문 → {row['report_nm']}", key="s0_ask_disc", on_click=_ask_about, args=(row,)):
            st.switch_page(_page("qa"))


def render():
    filters = st.session_state["filters"]
    _header(filters)
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

    _hero(summary)
    try:
        with st.spinner("데이터를 불러오는 중"):
            sent = data.filter_news(filters).merge(data.sentiment_frame(), on="url")
            links = data.filter_links(filters)
            spikes = data.filter_spikes(filters)
    except Exception as e:
        ui.data_error(data.DB_PATH, e)
        ui.limits(LIMITS_S0)
        return

    cards = [c for c in summary["cards"] if c["evidence"] and _visible(c, filters)]   # 근거 없는 카드 제외 (N6)
    # 본문 폭이 사이드바 때문에 1,000px 안팎이라, 좌우로 길게 나누지 않고 위에서 아래로 쌓는다:
    # 지표 한 줄 → 차트(넓게) + Q&A 카드 → 기회·위험 타일(전체 폭, 3열) → 최근 공시
    _kpis(sent, links, spikes, filters)
    left, right = st.columns([2, 1], gap="medium")
    with left:
        _trend_chart(sent, filters)
    with right:
        _qa_card()
    if not cards:
        with st.container(border=True):
            st.markdown("현재 필터에 해당하는 요약 없음")
            st.button("필터 초기화", key="empty_reset_S0_cards", on_click=flt.reset)
    else:
        _tiles(cards, "기회")
        _tiles(cards, "위험")
    st.divider()
    _recent_disclosures(filters, links)
    ui.limits(LIMITS_S0)
