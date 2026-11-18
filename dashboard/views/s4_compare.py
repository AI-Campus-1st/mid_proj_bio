"""기업 비교 — F4 (US-11, US-12, US-13 / AC-11, AC-12, AC-13). docs/05_design/UI_SPECIFICATION.md 5-5절.

주요 4분류 공시 건수, 기업별 공시 타임라인, 수주 계약 금액 추이.
금액은 analysis/extract_contract_amounts.py 가 공시 원문에서 정규식으로 뽑은 data/processed/contract_amounts.csv 를 쓴다.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import data, theme, ui
from views import s6_qa

LIMITS_S4 = [
    "공시 건수는 금액이 아닙니다. 건수는 정정 공시를 빼고 셉니다.",
    "프레스티지바이오로직스는 매출 규모가 작아(125억 원) 소규모 계약도 공시 대상이 됩니다.",
    "계약 금액은 공시 원문의 '계약금액' 칸을 정규식으로 읽었습니다(LLM 아님). 정정 공시가 있으면 가장 최근 정정본 금액을 씁니다.",
    "계약 금액은 계약 기간 전체의 금액이며 한 해 매출이 아닙니다.",
]
CAUSAL_NOTE = "※ 정책 이후 사업 활동이며 인과가 아님"


def _qa_page():
    """L8 이동 대상. app.py 의 S6 와 같은 함수·url_path 여야 st.switch_page 가 찾는다."""
    return st.Page(s6_qa.render, title="공시 Q&A", url_path="qa")


# ---------------------------------------------------------------- 지표·막대

def _kpis(disc: pd.DataFrame, allowed: set) -> None:
    base = disc[disc.is_amended == 0]
    items = []
    for cls in data.MAIN_EVENTS:
        label = "M&A" if cls == "M&A·구조개편" else cls
        if cls in allowed:
            items.append({"label": f"{label} 공시", "value": f"{int((base.event_class == cls).sum()):,}건",
                          "help": "정정 공시 제외 · 공시 건수는 금액이 아닙니다"})
        else:
            items.append({"label": f"{label} 공시", "value": "—", "help": "선택한 카테고리에 해당하지 않는 분류"})
    ui.kpis(items)


def _class_bar(disc: pd.DataFrame, companies: list, classes: list, key: str) -> None:
    """x = 분류, 색 = 기업. 기업 색 고정 규칙을 지키고 같은 분류 안에서 기업을 비교한다 (5-5절)."""
    mode = theme.current_mode()
    base = disc[(disc.is_amended == 0) & disc.event_class.isin(classes)]
    table = (base.pivot_table(index="event_class", columns="corp_name", values="rcept_no", aggfunc="count",
                              fill_value=0).reindex(index=classes, columns=companies, fill_value=0))
    fig = go.Figure()
    for corp in companies:
        fig.add_trace(go.Bar(x=classes, y=table[corp], name=corp, marker_color=theme.COMPANY_COLOR[mode][corp],
                             hovertemplate=f"<b>{corp}</b><br>%{{x}} · %{{y:,}}건<extra></extra>"))
    fig.update_layout(barmode="group")
    theme.style(fig, "bar")
    fig.update_layout(showlegend=True)
    theme.show(fig, key=key, alt="기업별 주요 공시 분류 건수 (정정 제외)")
    ui.table_view(table.reset_index().rename(columns={"event_class": "분류"}), "주요 분류별 공시 건수 (정정 제외)")


# ---------------------------------------------------------------- 타임라인 (L7·L8)

def _pick_point(key: str) -> None:
    pts = st.session_state[key]["selection"]["points"]
    for p in pts:
        cd = p.get("customdata")
        rno = cd[0] if isinstance(cd, (list, tuple)) and cd else cd
        if isinstance(rno, str):
            st.session_state["s4_rcept"] = rno
            return


def _go_qa(row: dict) -> None:
    """L8 — S6 전용 범위만 바꾸고 사이드바 필터는 그대로 둔다 (미결 Q11 임시 동작)."""
    st.session_state["qa_scope_override"] = {"corp_names": [row["corp_name"]], "date_from": row["rcept_date"],
                                             "date_to": row["rcept_date"]}


def _timeline(disc: pd.DataFrame, companies: list, fkey: int) -> None:
    if st.session_state.get("s4_company") not in companies:   # 위젯을 그리기 전에 고친다 (4-4절)
        st.session_state["s4_company"] = companies[0]
    corp = st.selectbox("기업", companies, key="s4_company")
    d = disc[disc.corp_name == corp].sort_values("date")
    if d.empty:
        ui.empty("공시", "S4-C2")
        return
    mode = theme.current_mode()
    neutral = theme.SENTIMENT_COLOR[mode]["중립"]
    order = [c for c in data.MAIN_EVENTS if c in set(d.event_class)] + \
        sorted(c for c in set(d.event_class) if c not in data.MAIN_EVENTS)
    fig = go.Figure()
    for cls in order:
        g = d[d.event_class == cls]
        color = theme.event_color(cls, mode) if cls in data.MAIN_EVENTS else neutral
        fig.add_trace(go.Scatter(
            x=g.date, y=g.event_class, mode="markers", name=cls,
            marker=dict(size=10, color=color, symbol=["circle-open" if a else "circle" for a in g.is_amended],
                        line=dict(width=2, color=color)),
            customdata=g[["rcept_no", "report_nm"]].to_numpy(),
            hovertemplate="%{x|%Y-%m-%d}<br>%{customdata[1]}<extra></extra>"))
    theme.style(fig, "scatter")
    fig.update_layout(showlegend=False)
    fig.update_yaxes(categoryorder="array", categoryarray=list(reversed(order)), showgrid=False)
    fig.update_xaxes(tickformat="%Y-%m")
    key = f"s4_tl_{fkey}_{corp}"
    theme.show(fig, key=key, alt=f"{corp} 공시 타임라인 (속 빈 원은 정정 공시)",
               on_select=lambda: _pick_point(key), selection_mode="points")
    st.caption("점을 누르면 아래에 공시가 보입니다. 속 빈 원은 정정 공시입니다.")

    sel = d[d.rcept_no == st.session_state.get("s4_rcept")]
    if sel.empty:
        return
    row = sel.iloc[0].to_dict()
    with st.container(border=True):
        ui.disclosure_line(row)
        if st.button("이 공시에 질문 →", key="s4_ask", on_click=_go_qa, args=(row,)):
            st.switch_page(_qa_page())


# ---------------------------------------------------------------- 수주 금액 (S4-C3)

def _amounts(filters: dict, fkey: int) -> None:
    orig, amended = data.contract_amounts()
    s, e = (pd.Timestamp(x) for x in filters["period"])
    in_scope = (orig.date >= s) & (orig.date <= e) & orig.corp_name.isin(filters["companies"])
    o = orig[in_scope]
    contracts = o[o.amount.notna() & ~o.report_nm.str.contains("해지")]
    missing = o[o.amount.isna()]
    if contracts.empty and missing.empty:
        ui.empty("공시", "S4-C3")
        return
    mode = theme.current_mode()
    fig = go.Figure()
    for corp in [c for c in filters["companies"] if c in set(contracts.corp_name)]:
        g = contracts[contracts.corp_name == corp]
        changed = [f"<br>최초 {fa / 1e8:,.0f}억 → 정정 {n}회 (최근 {d})" if n else ""
                   for fa, n, d in zip(g.first_amount, g.n_amended, g.latest_amend_date)]
        fig.add_trace(go.Scatter(
            x=g.date, y=g.amount / 1e8, mode="markers", name=corp,
            marker=dict(size=10, color=theme.COMPANY_COLOR[mode][corp]),
            customdata=list(zip(g.report_nm, g.counterparty.replace("", "-"), changed)),
            hovertemplate=(f"<b>{corp}</b> · %{{x|%Y-%m-%d}}<br>%{{y:,.0f}}억 원<br>상대방: %{{customdata[1]}}"
                           "%{customdata[2]}<extra></extra>")))
    theme.style(fig, "scatter")
    fig.update_layout(showlegend=True)
    # 금액이 수억~2조 원으로 세 자릿수 넘게 차이 나서, 선형 축이면 프레스티지·바이넥스 계약이 바닥에 붙는다
    fig.update_yaxes(type="log", title_text="계약 금액 (억 원, 로그 축)", tickformat=",")
    fig.update_xaxes(tickformat="%Y-%m")
    theme.show(fig, key=f"s4_amt_{fkey}", alt="수주 계약 금액 추이 (억 원, 로그 축, 최신 정정본 기준)")
    total = contracts.groupby("corp_name").amount.agg(["count", "sum"]).reindex(
        [c for c in filters["companies"] if c in set(contracts.corp_name)])
    st.caption("기간 합계: " + " · ".join(f"{c} {int(r['count'])}건 {r['sum'] / 1e8:,.0f}억 원"
                                         for c, r in total.iterrows()))
    view = contracts.sort_values("date", ascending=False)
    ui.table_view(pd.DataFrame({
        "제출일": view.rcept_date, "기업": view.corp_name, "공시명": view.report_nm,
        "금액(억 원)": (view.amount / 1e8).round(1), "최초 금액(억 원)": (view.first_amount / 1e8).round(1),
        "정정 횟수": view.n_amended, "상대방": view.counterparty}), "수주 원공시별 금액 (최신 정정본 기준)")

    if not missing.empty:
        st.markdown(f"**금액을 추출하지 못한 수주 공시 {len(missing)}건**")
        st.dataframe(pd.DataFrame({"제출일": missing.rcept_date, "기업": missing.corp_name,
                                   "공시명": missing.report_nm, "이유": missing.note,
                                   "DART": missing.rcept_no.map(ui.dart_url)}),
                     hide_index=True, width="stretch", alt="금액을 추출하지 못한 수주 공시",
                     column_config={"DART": st.column_config.LinkColumn("DART", display_text="DART")})
    old = amended[~amended.matched & (amended.date >= s) & (amended.date <= e)
                  & amended.corp_name.isin(filters["companies"])]
    if not old.empty:
        with st.expander(f"원공시에 연결하지 못한 정정 공시 {len(old)}건 (차트에 없음)"):
            st.caption("차트의 점은 원공시 제출일이라, 원공시를 DB에서 찾지 못한 정정은 붙일 수 없습니다. "
                       "대부분 원공시가 수집 기간(2023-10-19) 전인 계약(2017~2023년)의 금액 증액·기간 연장입니다.")
            st.dataframe(pd.DataFrame({"제출일": old.rcept_date, "기업": old.corp_name, "원공시 제출일": old.original_date,
                                       "정정 후 금액(억 원)": (old.amount / 1e8).round(1),
                                       "DART": old.rcept_no.map(ui.dart_url)}).sort_values("제출일", ascending=False),
                         hide_index=True, width="stretch", alt="기간 이전 계약의 정정 공시",
                         column_config={"DART": st.column_config.LinkColumn("DART", display_text="DART")})


# ---------------------------------------------------------------- 화면

def render():
    filters = st.session_state["filters"]
    ui.header("기업 비교", "경쟁사의 수주·증설·투자는 어떻게 변하는가?", filters)
    companies = filters["companies"]
    allowed = data.keyword_events(filters)
    if not companies or not allowed:
        ui.empty("공시", "S4-all")
        ui.limits(LIMITS_S4)
        return
    try:
        with st.spinner("데이터를 불러오는 중"):
            disc = data.filter_disclosures(filters, allowed)
    except FileNotFoundError as e:
        ui.data_error(e.args[0] if e.args else data.DB_PATH, e)
        ui.limits(LIMITS_S4)
        return

    if {"CDMO 규제·정책", "CDMO 지정학"} & set(filters["keywords"]):
        st.caption(CAUSAL_NOTE)
    _kpis(disc, allowed)
    st.divider()

    fkey = abs(hash((str(filters["period"]), tuple(companies), tuple(filters["keywords"]))))
    classes = [c for c in data.MAIN_EVENTS if c in allowed]
    st.markdown("#### 주요 공시 분류별 건수")
    if disc[disc.is_amended == 0].event_class.isin(classes).sum() == 0:
        ui.empty("공시", "S4-C1")
    else:
        _class_bar(disc, companies, classes, key=f"s4_bar_{fkey}")

    tab_names = ["기업별 타임라인"] + (["수주 금액 추이"] if "수주" in allowed else [])
    tabs = st.tabs(tab_names)
    with tabs[0]:
        _timeline(disc, companies, fkey)
    if len(tabs) > 1:
        with tabs[1]:
            try:
                _amounts(filters, fkey)
            except FileNotFoundError as e:
                ui.data_error(data.AMOUNTS_PATH, e)
    ui.limits(LIMITS_S4)
