"""색 토큰과 Plotly 스타일 — docs/05_design/UI_SPECIFICATION.md 2-1·2-2·2-5·2-7절.

모든 차트는 style() 로 꾸미고 show() 로 그린다. 시각 값은 이 파일과 .streamlit/config.toml 에만 둔다.
"""
import streamlit as st

# 화면 색 (DESIGN.md — 크림 캔버스 · 초록 4단계). 데이터 색(기업·감성·범주 슬롯)은 아래 그대로 (UI_SPECIFICATION 2-1절).
TOKENS = {
    "light": {"bg": "#F2F0EB", "bg-subtle": "#FFFFFF", "text": "#1E1E1E", "text-muted": "#5C5A55",
              "border": "#D6DBDE", "grid": "#E3E0D8", "primary": "#00754A", "link": "#00754A",
              "series-volume": "#1F4E79",
              "heading": "#006241", "band": "#1E3932", "band-text": "#FFFFFF", "band-muted": "#D4E9E2"},
    "dark": {"bg": "#1E3932", "bg-subtle": "#2B5148", "text": "#F2F0EB", "text-muted": "#B9C8C2",
             "border": "#3E6359", "grid": "#2F5047", "primary": "#00754A", "link": "#D4E9E2",
             "series-volume": "#6FA8DC",
             "heading": "#D4E9E2", "band": "#0F241F", "band-text": "#FFFFFF", "band-muted": "#B9C8C2"},
}

# 기업 색 (고정 매핑, IA 4-1절 순서)
COMPANY_COLOR = {
    "light": {"삼성바이오로직스": "#513BB2", "SK바이오사이언스": "#049A78", "프레스티지바이오로직스": "#9A1B71",
              "에스티팜": "#A06B01", "바이넥스": "#AF54D3"},
    "dark": {"삼성바이오로직스": "#6148D1", "SK바이오사이언스": "#12AF7D", "프레스티지바이오로직스": "#B6127D",
             "에스티팜": "#946823", "바이넥스": "#B37BCC"},
}

SENTIMENT_COLOR = {
    "light": {"기회": "#2A78D6", "위험": "#E34948", "중립": "#858C97"},
    "dark": {"기회": "#3987E5", "위험": "#E66767", "중립": "#5F6673"},
}

_SLOTS = {
    "light": ["#716DF6", "#A20519", "#11598F", "#B0698C", "#C68206"],
    "dark": ["#737AFC", "#BA2B2E", "#0A67A9", "#EA589A", "#D79628"],
}
ORIGIN_COLOR = {m: dict(zip(["제공", "팀원수집", "기업명검색", "CDMO검색", "해외검색"], s)) for m, s in _SLOTS.items()}
EVENT_COLOR = {m: {"수주": s[0], "증설": s[1], "M&A·구조개편": s[2], "자금조달": s[3]} for m, s in _SLOTS.items()}
KEYWORD_COLOR = {m: {"CDMO 모달리티": s[0], "CDMO 생산능력": s[2]} for m, s in _SLOTS.items()}

FONT_FAMILY = '"Noto Sans KR", "Malgun Gothic", "Apple SD Gothic Neo", sans-serif'
HEIGHT = {"main": 360, "sub": 280, "small": 200}
PLOTLY_CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]}


def current_mode() -> str:
    """현재 테마 "light"/"dark". 값이 없으면 light (첫 접속 직후엔 틀릴 수 있음 — 미결 Q15)."""
    try:
        mode = st.context.theme.type
    except Exception:
        mode = None
    return mode if mode in ("light", "dark") else "light"


def event_color(event_class: str, mode: str | None = None) -> str:
    mode = mode or current_mode()
    return EVENT_COLOR[mode].get(event_class, SENTIMENT_COLOR[mode]["중립"])


def style(fig, kind: str = "bar", height: str = "main"):
    """2-7절 레이아웃 적용. kind = time / bar / scatter / heatmap."""
    t = TOKENS[current_mode()]
    axis = dict(showline=True, linewidth=1, linecolor=t["border"], zeroline=False,
                tickfont=dict(size=12, color=t["text-muted"]))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",   # 캔버스·카드 어느 쪽에 놓여도 바탕을 따른다
        font=dict(family=FONT_FAMILY, size=12, color=t["text"]),
        height=HEIGHT.get(height, height) if isinstance(height, str) else height,
        margin=dict(l=8, r=8, t=8, b=8),
        showlegend=len(fig.data) >= 2,
        legend=dict(orientation="h", x=0, xanchor="left", y=1.02, yanchor="bottom", title_text=""),
        hovermode="x unified" if kind == "time" else "closest",
        hoverlabel=dict(bgcolor=t["bg-subtle"], bordercolor=t["border"], font=dict(size=13, color=t["text"])),
        bargap=0.25, bargroupgap=0.1,
    )
    if kind != "heatmap":
        fig.update_xaxes(showgrid=False, **axis)
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor=t["grid"], **axis)
    if kind == "time":
        fig.update_xaxes(tickformat="%Y-%m")
    return fig


def show(fig, *, key: str, alt: str, on_select="ignore", selection_mode="points"):
    """모든 차트는 이 함수로만 그린다. key 에 적용 필터 해시를 넣으면 필터가 바뀔 때 확대 상태가 풀린다."""
    fig.update_layout(uirevision=key)
    return st.plotly_chart(fig, theme="streamlit", width="stretch", key=key, alt=alt,
                           on_select=on_select, selection_mode=selection_mode, config=PLOTLY_CONFIG)
