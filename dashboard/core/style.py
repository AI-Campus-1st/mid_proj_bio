"""DESIGN.md 를 테마(.streamlit/config.toml)로 못 하는 부분만 CSS로 — 카드 면·그림자, 버튼 눌림, 제목 색, S0 결론 띠.

색 값은 theme.TOKENS 에서 가져온다 (값을 이 파일에 따로 두지 않는다). app.py 가 매 실행 inject() 를 부른다.
카드는 ui.card() 로 만든 컨테이너(key "card_N" → class "st-key-card_N")만 고른다.
"""
import streamlit as st

from core import theme

# DESIGN.md 6절: 낮은 알파 그림자 2겹 (카드), 3겹 (뜬 요소)
CARD_SHADOW = "0 0 0.5px rgba(0,0,0,0.14), 0 1px 1px rgba(0,0,0,0.24)"


def inject() -> None:
    mode = theme.current_mode()
    t = theme.TOKENS[mode]
    card_border = "transparent" if mode == "light" else t["border"]   # 밝을 땐 그림자로, 어두울 땐 테두리로 구분
    shadow = CARD_SHADOW if mode == "light" else "none"
    st.html(f"""<style>
/* 글자: DESIGN.md 3절 — 살짝 좁은 자간, 큰 제목은 Starbucks Green */
[data-testid="stMain"] {{ letter-spacing: -0.01em; }}
[data-testid="stMain"] h1 {{ color: {t["heading"]}; }}

/* 카드: 흰 면 · 12px · 엷은 그림자 2겹 (ui.card, 지표) */
[class*="st-key-card_"], [data-testid="stMetric"] {{
  background: {t["bg-subtle"]};
  border-color: {card_border} !important;
  box-shadow: {shadow};
  border-radius: 12px;
}}
[data-testid="stExpander"] details {{ background: {t["bg-subtle"]}; border-radius: 12px; }}

/* 버튼: 알약(테마) + 눌림 scale(0.95), 보조 버튼은 초록 테두리 (DESIGN.md 4절 Primary Outlined) */
button[data-testid^="stBaseButton-primary"], button[data-testid^="stBaseButton-secondary"],
[data-testid="stPopoverButton"] {{ transition: all 0.2s ease; }}
button[data-testid^="stBaseButton-primary"]:active, button[data-testid^="stBaseButton-secondary"]:active,
[data-testid="stPopoverButton"]:active {{ transform: scale(0.95); }}
button[data-testid^="stBaseButton-secondary"]:not(:disabled) {{ border-color: {t["primary"] if mode == "light" else t["link"]}; color: {t["link"]}; }}
button[data-testid^="stBaseButton-primary"] {{ font-weight: 600; }}

/* S0 결론 띠: House Green 면에 흰 글자 (DESIGN.md 4절 Feature Band) */
.st-key-s0_hero {{
  background: {t["band"]};
  border-radius: 12px;
  padding: 1.5rem 1.75rem;
}}
.st-key-s0_hero h1, .st-key-s0_hero h3, .st-key-s0_hero p, .st-key-s0_hero li,
.st-key-s0_hero span {{ color: {t["band-text"]}; }}
.st-key-s0_hero [data-testid="stCaptionContainer"] p {{ color: {t["band-muted"]}; }}
/* 판단 단어: 진녹색 면에서 읽히는 밝은 파랑·빨강·회색 (config.toml 다크 테마 글자색과 같은 값) */
.st-key-s0_verdict_good .stMarkdownColoredText {{ color: #A9CDF5 !important; }}
.st-key-s0_verdict_bad .stMarkdownColoredText {{ color: #F2A0A0 !important; }}
.st-key-s0_verdict_neutral .stMarkdownColoredText {{ color: #D0DAD6 !important; }}
/* 띠 안 기회·위험 줄 머리: 글머리 대신 색으로 구분 (판단 단어와 같은 밝은 파랑·빨강) */
.st-key-s0_hero span.s0-opp {{ color: #A9CDF5; font-weight: 700; margin-right: 0.35rem; }}
.st-key-s0_hero span.s0-risk {{ color: #F2A0A0; font-weight: 700; margin-right: 0.35rem; }}
/* 띠 안 수치 상자: 반투명 테두리 */
.st-key-s0_hero_stats {{ border-color: rgba(255,255,255,0.28) !important; background: rgba(255,255,255,0.05); }}
</style>""")
