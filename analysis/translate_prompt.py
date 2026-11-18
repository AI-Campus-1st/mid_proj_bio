"""영어 기사 제목 번역 프롬프트 (T4, PRD F8).

해외 검색으로 모은 영어 기사(lang='en', 797건, 모두 제목만)의 제목을 한국어로 옮긴다.
화면(S2 등)은 번역 제목을 크게 보여 주고 바로 아래에 원제목을 작게 함께 보여 준다(ui.news_line).
LLM 호출 코드는 이 모듈의 SYSTEM_PROMPT, build_user_prompt(), parse_response() 를 쓴다.
프롬프트를 바꾸면 PROMPT_VERSION 을 올린다 (결과 파일에 버전이 함께 저장된다).

번역 원칙과 근거
  - 의미를 그대로 옮기고 덧붙이거나 줄이지 않는다. 화면에서 원제목과 나란히 보이므로, 다르면 바로 드러난다.
  - 기업·제도명은 제목에 쓰인 이름을 그대로 옮기고, 한글 표기가 확실히 정착된 것만 한글로 쓴다 (Lonza → 론자,
    BIOSECURE Act → 생물보안법). 이슈 추출 프롬프트(issue_prompt.py)와 같은 표기라 국내 기사와 같은 이름으로 읽힌다.
  - 한글 표기가 확실하지 않으면 영문 그대로 둔다. 어설픈 음차는 틀리기 쉽고 오히려 찾기 어렵다.
  - 원어 병기(론자(Lonza))는 하지 않는다. 원제목이 바로 아래 보이므로 병기하면 같은 이름을 두 번 읽게 된다.
  - 숫자·금액·단위는 바꾸지 않고 한국어 단위로만 옮긴다 ($200M → 2억 달러). 원화 환산은 하지 않는다 (환율 기준이 없다).
"""
import json
import re

# v1 → v2 (2026-11-18): 시험 20건에서 "Fujifilm Biotechnologies"(2025년 바꾼 새 이름)가 예시 때문에 옛 이름
#   "후지필름 다이오신스"로 바뀌었다. 예시를 빼고 "제목의 이름을 그대로, 다른 이름으로 바꾸지 않음" 규칙을 넣었다.
#   작은 기업은 영문 그대로·음차가 섞여(Agappe / 아쿰스) "한글 표기가 확실할 때만 한글" 로 분명히 했다.
# v2 → v3 (2026-11-18): v2 는 "한글 표기가 확실할 때만 한글" 판단을 기사마다 달리 해, 같은 회사가 기사마다
#   "후지필름"/"Fujifilm" 으로 섞이고 Regeneron·Dr Reddy's 같은 알려진 회사도 영문으로 남았다. 판단을 모델에 맡기지 않고
#   표기 목록(NAME_KO)을 주어, 목록에 있으면 그 표기, 없으면 영문 그대로 쓰게 했다.
#   v3 시험 20건에서 통화가 없는 금액(4.3 billion)에 '달러'를 붙여 '원제목에 없는 통화·단위는 붙이지 않음' 규칙을
#   더했다 (v3 결과가 본 결과 파일에 쓰이기 전이라 버전은 그대로).
PROMPT_VERSION = "translate-v3"
# 영어 기사 797건 제목에 4번 이상 나온 기업·제도명 중 국내 언론 표기가 확실한 것 (2026-11-18 빈도 집계).
# 표기가 확실하지 않은 이름(Bora Pharmaceuticals, Recipharm, CordenPharma, National Resilience, PCI Pharma Services 등)은
# 넣지 않는다 — 틀린 음차보다 영문이 낫다. 빈도가 낮아도 국내 기업·대형 제약사는 같은 이유로 넣었다.
NAME_KO = {
    "Samsung Biologics": "삼성바이오로직스", "Samsung Bioepis": "삼성바이오에피스", "Celltrion": "셀트리온",
    "SK pharmteco": "SK팜테코", "SK bioscience": "SK바이오사이언스", "Lotte Biologics": "롯데바이오로직스",
    "ST Pharm": "에스티팜", "Lonza": "론자", "WuXi AppTec": "우시앱텍", "WuXi Biologics": "우시바이오로직스",
    "Catalent": "캐털런트", "Thermo Fisher": "써모피셔", "Fujifilm": "후지필름",
    "Fujifilm Diosynth Biotechnologies": "후지필름 다이오신스 바이오테크놀로지스",
    "Fujifilm Biotechnologies": "후지필름 바이오테크놀로지스", "AGC Biologics": "AGC바이오로직스",
    "Eli Lilly": "일라이 릴리", "Lilly": "릴리", "Novo Nordisk": "노보 노디스크", "Pfizer": "화이자",
    "Johnson & Johnson": "존슨앤드존슨", "J&J": "존슨앤드존슨", "AstraZeneca": "아스트라제네카", "Roche": "로슈",
    "Novartis": "노바티스", "Sanofi": "사노피", "Merck": "머크", "GSK": "GSK", "Bayer": "바이엘",
    "Regeneron": "리제네론", "Vertex": "버텍스", "Dr Reddy's": "닥터레디스", "Zydus": "자이더스",
    "BIOSECURE Act": "생물보안법", "Biosecure Act": "생물보안법",
}
GLOSSARY = "\n".join(f"  {en} → {ko}" for en, ko in NAME_KO.items())
TITLE_MAX = 150   # 원제목 최대 246자. 한국어가 보통 더 짧아, 이보다 길면 설명을 덧붙였을 가능성이 크다

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {"title_ko": {"type": "string"}},
    "required": ["title_ko"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = f"""당신은 바이오 CDMO(위탁개발생산) 산업 뉴스를 한국어로 옮기는 번역가입니다.
영어 기사 제목 한 줄을 한국어 뉴스 제목으로 번역합니다.

[원칙]
- 의미를 그대로 옮깁니다. 내용을 덧붙이거나 줄이지 않고, 설명·해석을 넣지 않습니다.
- 한국어 뉴스 제목처럼 간결하게 씁니다 (명사형 종결이나 "~한다/~했다" 모두 가능).
- 기업·기관·제도명은 제목에 쓰인 이름을 그대로 옮깁니다. 옛 이름이나 모회사 이름 등 다른 이름으로 바꾸지 않습니다.
- 아래 [표기 목록]에 있는 이름은 반드시 목록의 한글 표기로 씁니다 (대소문자·띄어쓰기·'s 차이는 같은 이름으로 봅니다).
  목록에 긴 이름과 짧은 이름이 둘 다 있으면 제목에 쓰인 쪽을 씁니다 (Fujifilm Biotechnologies → 후지필름 바이오테크놀로지스).
- [표기 목록]에 없는 기업·제품·인물 이름은 영문 그대로 둡니다. 음차하지 않습니다 (예: Agappe, Bora Pharmaceuticals 는 영문 그대로).
- 나라·지역 이름(China, India, North Carolina 등)과 일반 명사는 한국어로 옮깁니다.

[표기 목록]
{GLOSSARY}

- FDA, EU, GMP, CDMO, API, ADC 같은 약어는 그대로 둡니다.
- 원어를 괄호로 함께 쓰지 않습니다 (원제목이 화면에 함께 표시됩니다).
- 숫자·금액·단위는 값을 바꾸지 않고 한국어 단위로만 옮깁니다 ($200M → 2억 달러, €50M → 5,000만 유로). 원화로 환산하지 않습니다.
- 원제목에 없는 통화·단위는 붙이지 않습니다 (a turnover of 4.3 billion → 매출 43억. '달러'를 붙이지 않습니다).
- "Exclusive:", "UPDATE:" 같은 머리말은 [단독], [업데이트]처럼 옮깁니다.
- JSON 한 개만 답합니다: {{"title_ko": "..."}}"""

USER_TEMPLATE = "원제목: {title}"


def build_user_prompt(title: str) -> str:
    return USER_TEMPLATE.format(title=" ".join(title.split()))


def parse_response(text: str, title: str = "") -> str:
    """LLM 응답에서 번역 제목을 꺼내 검증한다. 형식이 틀리면 ValueError (재시도 대상).

    한글이 없으면 실패다. 단, 원제목과 똑같이 돌려준 경우는 통과시킨다 — 제목이 회사·사람 이름뿐이면
    ("Halix", "APL", "3PBIOVIAN") 옮길 말이 없고, 프롬프트도 한글 표기가 확실하지 않은 이름은 영문 그대로 두게 한다.
    (전체 실행에서 이런 제목 4건이 한글 검증에 걸려 계속 실패, 2026-11-18. 검증만 바꿔 프롬프트 버전은 그대로)
    """
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError(f"JSON 없음: {text[:200]}")
    t = " ".join(str(json.loads(m.group(0)).get("title_ko", "")).split())
    if not t:
        raise ValueError("title_ko 없음")
    if not re.search(r"[가-힣]", t) and t != " ".join(title.split()):
        raise ValueError(f"한글이 없음: {t}")
    if len(t) > TITLE_MAX:
        raise ValueError(f"{TITLE_MAX}자를 넘음 ({len(t)}자): {t[:80]}")
    return t
