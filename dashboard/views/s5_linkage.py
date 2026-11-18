"""뉴스-공시 연계 — F5 (US-14, US-15 / AC-14, AC-15). docs/05_design/UI_SPECIFICATION.md 5-6절.

기업별 주간 기사량과 공시 시점을 한 차트(위아래 두 칸)에 두고, 임시 이슈(키워드 × 기업 × 월)마다
규칙 매칭(news_disclosure_links.csv)으로 이어진 공시를 직접 → 후속 순서로 보여 준다.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from core import data, theme, ui
from views import s6_qa

# 공시 표식에 쓰는 분류 (주요 4분류 + 실적·임상·허가·기술계약·리스크, 5-6절 S5-C1)
MARK_EVENTS = data.MAIN_EVENTS + ["실적", "임상·허가·기술계약", "리스크"]
LIMITS_S5 = [
    "뉴스-공시 연결은 규칙(같은 기업 + 날짜 창 + 키워드↔공시 분류)으로 만들었고 내용을 읽지 않습니다. 직접 창은 기사 "
    "발행일 ±3일, 후속 창은 4~90일 뒤 공시입니다.",
    "표본 50쌍 검수(2026-11-18): 직접·당일 연결은 15쌍 중 10쌍이 같은 사건, 직접·±1~3일은 15쌍 중 2쌍, "
    "후속 창은 20쌍 중 같은 사건 0쌍·관련 13쌍입니다. 후속 연결은 '이후 사업 활동'으로 읽으세요.",
    "5개사가 언급되지 않은 기사(해외 CDMO, 정책 기사 대부분)는 공시와 연결되지 않습니다.",
    "연결의 91%가 삼성바이오로직스입니다.",
]
ISSUE_NOTE = "이슈 단위 집계 전이라 키워드 × 기업 × 월로 묶었습니다"
CAUSAL_NOTES = ["※ 후속 창 연결은 선후 관계이며 인과가 아님", "※ 수집 끝 90일 이내 기사는 \"후속 확인 불가\""]


def _qa_page():
    """L8 이동 대상. app.py 의 S6 와 같은 함수·url_path 여야 st.switch_page 가 찾는다 (S4 와 같은 방식)."""
    return st.Page(s6_qa.render, title="공시 Q&A", url_path="qa")


def _go_qa(corp: str, rcept_date: str) -> None:
    """L8 — S6 전용 범위만 바꾸고 사이드바 필터는 그대로 둔다 (미결 Q11 임시 동작)."""
    st.session_state["qa_scope_override"] = {"corp_names": [corp], "date_from": rcept_date, "date_to": rcept_date}


# ---------------------------------------------------------------- S5-C1 기사량 vs 공시 시점

def _pick_disclosure(key: str) -> None:
    for p in st.session_state[key]["selection"]["points"]:
        cd = p.get("customdata")
        rno = cd[0] if isinstance(cd, (list, tuple)) and cd else cd
        if isinstance(rno, str) and len(rno) == 14:
            st.session_state["s5_rcept"] = rno
            return


def _volume_vs_disclosures(filters: dict, fkey: int) -> None:
    st.markdown("#### 기업별 기사량과 공시 시점")
    companies = filters["companies"]
    if st.session_state.get("s5_company") not in companies:   # 위젯을 그리기 전에 고친다 (4-4절)
        st.session_state["s5_company"] = companies[0]
    corp = st.selectbox("기업", companies, key="s5_company")

    news = data.filter_news({**filters, "companies": [corp]})          # 기업명이 제목·본문에 있는 기사 (R2)
    events = [c for c in MARK_EVENTS if c in data.keyword_events(filters)] if filters["keywords"] else []
    disc = data.filter_disclosures({**filters, "companies": [corp]}, events)
    if news.empty and disc.empty:
        ui.empty("기사/공시", "S5-C1")
        return

    mode = theme.current_mode()
    t = theme.TOKENS[mode]
    s, e = (pd.Timestamp(x) for x in filters["period"])
    weeks = pd.date_range(s.to_period("W-SUN").start_time, e.to_period("W-SUN").start_time, freq="W-MON")
    vol = news.date.dt.to_period("W-SUN").dt.start_time.value_counts().reindex(weeks, fill_value=0).sort_index()

    order = [c for c in MARK_EVENTS if c in set(disc.event_class)]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.72, 0.28], vertical_spacing=0.06)
    fig.add_trace(go.Bar(x=vol.index, y=vol.values, name="기사 수", marker_color=t["series-volume"],
                         unselected=dict(marker=dict(opacity=1)),
                         hovertemplate="%{x|%Y-%m-%d} 주 · %{y:,}건<extra></extra>"), row=1, col=1)
    neutral = theme.SENTIMENT_COLOR[mode]["중립"]
    for cls in order:
        g = disc[disc.event_class == cls]
        color = theme.event_color(cls, mode) if cls in data.MAIN_EVENTS else neutral
        fig.add_trace(go.Scatter(
            x=g.date, y=[cls] * len(g), mode="markers", name=cls,
            marker=dict(symbol=["triangle-down-open" if a else "triangle-down" for a in g.is_amended], size=10,
                        color=color, line=dict(width=1.5, color=color)),
            customdata=g[["rcept_no", "report_nm"]].to_numpy(),
            hovertemplate="%{x|%Y-%m-%d}<br>%{customdata[1]}<br>" + cls + "<extra></extra>"), row=2, col=1)
    theme.style(fig, "bar", height=420)
    fig.update_layout(showlegend=False, hovermode="closest")
    fig.update_yaxes(title_text=None, row=1, col=1)
    fig.update_yaxes(categoryorder="array", categoryarray=list(reversed(order)), showgrid=False, row=2, col=1)
    fig.update_xaxes(tickformat="%Y-%m", row=2, col=1)
    key = f"s5_chart_{fkey}_{corp}"
    theme.show(fig, key=key, alt=f"{corp} 주별 기사 수(위)와 공시 접수일(아래 ▼, 속 빈 표식은 정정)",
               on_select=lambda: _pick_disclosure(key), selection_mode="points")
    st.caption("위: 기업명이 제목·본문에 나온 주별 기사 수. 아래: 공시 접수일(▼, 속 빈 표식은 정정). ▼을 누르면 아래에 공시가 보입니다.")

    sel = disc[disc.rcept_no == st.session_state.get("s5_rcept")]
    if not sel.empty:
        row = sel.iloc[0].to_dict()
        with st.container(border=True):
            ui.disclosure_line(row)
            if st.button("이 공시에 질문 →", key="s5_ask_chart", on_click=_go_qa,
                         args=(row["corp_name"], row["rcept_date"])):
                st.switch_page(_qa_page())


# ---------------------------------------------------------------- S5-C2 이슈 ↔ 관련 공시

def _issues(links: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """임시 이슈 = 키워드(선택한 것만) × 기업 × 기사 발행 월. 연결 기사·공시 수."""
    sel = set(filters["keywords"])
    ex = links.explode("keywords")
    ex = ex[ex.keywords.isin(sel)]
    ex = ex.assign(month=ex.published_date.str[:7])
    g = ex.groupby(["keywords", "corp_name", "month"]).agg(articles=("url", "nunique"),
                                                           disclosures=("rcept_no", "nunique")).reset_index()
    g["issue"] = g.keywords + " · " + g.corp_name + " · " + g.month
    return g.sort_values(["articles", "disclosures", "month"], ascending=[False, False, False]).reset_index(drop=True)


def _select_issue() -> None:
    rows = st.session_state["s5_issue_tbl"]["selection"]["rows"]
    ids = st.session_state.get("_s5_issue_ids", [])
    st.session_state["s5_issue"] = ids[rows[0]] if rows and rows[0] < len(ids) else None


def _related(links: pd.DataFrame, issue: str) -> pd.DataFrame:
    """선택 이슈의 공시를 rcept_no 로 묶고 직접 → 후속, class_weight 내림차순, |day_gap| 오름차순 (3-5절)."""
    kw, corp, month = issue.split(" · ")
    sub = links[(links.corp_name == corp) & (links.published_date.str[:7] == month)
                & links.keywords.map(lambda ks: kw in ks)]
    sub = sub.assign(direct=(sub.window == "direct"), gap_abs=sub.day_gap.abs())
    rows = []
    for rno, g in sub.groupby("rcept_no"):
        d = g[g.direct]
        best = (d if not d.empty else g).sort_values("gap_abs").iloc[0]
        rows.append({**best[["rcept_no", "rcept_date", "report_nm", "event_class", "class_weight",
                             "is_amended", "corp_name"]].to_dict(),
                     "direct": not d.empty, "day_gap": int(best.day_gap), "gap_abs": int(best.gap_abs),
                     "n_articles": g.url.nunique(),
                     "low_conf": bool((g.kw_low_confidence == 1).all()),
                     "follow_cut": bool((g.follow_cut == 1).any())})
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["direct", "class_weight", "gap_abs"], ascending=[False, False, True])
    return out, sub


def _related_list(links: pd.DataFrame, issue: str | None) -> None:
    st.markdown("#### 관련 공시")
    if not issue:
        st.caption("왼쪽에서 이슈를 고르면 관련 공시가 보입니다")
        return
    rel, sub = _related(links, issue)
    if rel.empty:
        st.caption("왼쪽에서 이슈를 고르면 관련 공시가 보입니다")
        return
    st.caption(f"**{issue}** — 공시 {len(rel):,}건 · 연결 기사 {sub.url.nunique():,}건")
    for i, r in enumerate(rel.itertuples()):
        badge = ":blue-badge[직접]" if r.direct else f":gray-badge[후속 +{r.day_gap}일]"
        extra = (" :gray-badge[정정]" if r.is_amended else "") + \
                (" :gray-badge[검색어 근거]" if r.low_conf else "") + \
                (" :gray-badge[후속 확인 불가]" if r.follow_cut else "")
        url = ui.dart_url(r.rcept_no)
        c1, c2 = st.columns([5, 1.4], gap="small", vertical_alignment="center")
        c1.markdown(f"{badge} {r.rcept_date} · {r.report_nm} · :gray-badge[{r.event_class}]{extra} · [DART]({url})"
                    f"  \n<small>연결 기사 {r.n_articles}건</small>", unsafe_allow_html=True)
        if c2.button("이 공시에 질문 →", key=f"s5_ask_{i}", on_click=_go_qa, args=(r.corp_name, r.rcept_date)):
            st.switch_page(_qa_page())
    for note in CAUSAL_NOTES:
        st.caption(note)
    with st.expander(f"이 이슈의 기사 {sub.url.nunique():,}건"):
        news = data.news_frame()
        arts = news[news.url.isin(sub.url.unique())].sort_values("published_date", ascending=False)
        for _, a in arts.iterrows():
            ui.news_line(a.to_dict())


def _issue_table(links: pd.DataFrame, filters: dict) -> None:
    # 명세는 [2, 3] 이지만 1024px 화면에서 표가 200px 남짓이라 열이 잘려 1:1 로 둔다
    left, right = st.columns([1, 1], gap="medium")
    issues = _issues(links, filters)
    with left:
        st.markdown("#### 이슈")
        st.caption(ISSUE_NOTE)
        if issues.empty:
            ui.empty("기사/공시", "S5-C2")
        else:
            st.session_state["_s5_issue_ids"] = issues.issue.tolist()
            view = issues.rename(columns={"issue": "이슈", "articles": "연결 기사", "disclosures": "연결 공시"})
            st.dataframe(view[["이슈", "연결 기사", "연결 공시"]], hide_index=True, width="stretch", height=420,
                         key="s5_issue_tbl", on_select=_select_issue, selection_mode="single-row",
                         column_config={"이슈": st.column_config.TextColumn(width="medium"),
                                        "연결 기사": st.column_config.NumberColumn(width="small"),
                                        "연결 공시": st.column_config.NumberColumn(width="small")})
    with right:
        issue = st.session_state.get("s5_issue")
        _related_list(links, issue if issue in set(issues.issue) else None)


# ---------------------------------------------------------------- 화면

def render():
    filters = st.session_state["filters"]
    ui.header("뉴스-공시 연계", "뉴스의 변화가 공시로 확인되는가?", filters)
    if not filters["companies"]:
        ui.empty("기사/공시", "S5")
        ui.limits(LIMITS_S5)
        return
    try:
        with st.spinner("데이터를 불러오는 중"):
            links = data.filter_links(filters)
    except Exception as e:
        ui.data_error(data.LINKS_PATH, e)
        ui.limits(LIMITS_S5)
        return

    ui.kpis([
        {"label": "연결된 기사", "value": f"{links.url.nunique():,}건", "help": "공시와 하나 이상 연결된 기사 (고유 URL)"},
        {"label": "연결 공시", "value": f"{links.rcept_no.nunique():,}건", "help": "기사와 연결된 공시 (고유 접수번호)"},
        {"label": "연결 없는 기사 비율", "value": "준비 중",
         "help": "매칭 대상 기사 수(분모)가 결과 파일에 없어 계산 전입니다 (미결 Q12)"},
    ])
    st.divider()
    fkey = abs(hash((str(filters["period"]), tuple(filters["companies"]), tuple(filters["keywords"]))))
    _volume_vs_disclosures(filters, fkey)
    st.divider()
    _issue_table(links, filters)
    ui.limits(LIMITS_S5)
