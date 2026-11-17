"""핵심 이슈·이슈 키워드 추출 프롬프트 (T2).

기사 한 건에서 "무슨 사건을 다루는가"를 이슈 이름·이슈 유형·핵심 키워드로 뽑는다.
감성 분류(sentiment_prompt.py)가 영향의 방향을 붙인다면, 이 프롬프트는 기사를 이슈 단위로
묶을 이름을 붙인다. 프롬프트를 바꾸면 PROMPT_VERSION 을 올린다 (결과 파일에 버전이 함께 저장된다).
LLM 호출 코드는 이 모듈의 SYSTEM_PROMPT, build_user_prompt(), parse_response() 를 쓴다.
"""
import json
import re

PROMPT_VERSION = "issue-v1"
# 이슈 유형. 뉴스-공시 매칭의 event_class 와 이어서 볼 수 있게 사건의 종류로 나눴다.
ISSUE_TYPES = ("정책·규제", "수주·계약", "증설·투자", "M&A·진출", "실적", "기술·모달리티",
               "품질·실사", "기타")
CONFIDENCES = ("high", "medium", "low")
BODY_CHARS = 1500     # 본문은 앞부분만 넣는다 (감성 분류와 같은 기준)
ISSUE_MAX = 30        # 이슈 이름 최대 글자 수
KEYWORD_MAX = 15      # 키워드 하나의 최대 글자 수
KEYWORDS_RANGE = (1, 3)

# 구조화 출력 스키마 — 응답이 이 형식의 JSON으로 강제된다
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "issue": {"type": "string"},
        "issue_type": {"type": "string", "enum": list(ISSUE_TYPES)},
        "keywords": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "string", "enum": list(CONFIDENCES)},
    },
    "required": ["issue", "issue_type", "keywords", "confidence"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = f"""당신은 글로벌 바이오 CDMO(위탁개발생산) 시장을 분석하는 애널리스트입니다.
뉴스 기사 한 건을 읽고, 이 기사가 다루는 **핵심 이슈 하나**와 그 이슈를 나타내는 **키워드**를 뽑습니다.
여러 기사를 같은 이슈끼리 묶는 데 쓰므로, 같은 사건을 다룬 기사에는 같은 이슈 이름이 붙어야 합니다.

[issue — 이슈 이름]
- 한국어 명사구, {ISSUE_MAX}자 이내. "주체 + 사건" 형태로 씁니다.
  예: "미국 생물보안법", "미국 의약품 관세", "삼성바이오로직스 5공장 증설", "론자 미국 공장 인수",
      "셀트리온 CDMO 진출", "FDA 실사 지적", "ADC 위탁생산 수요"
- 날짜, 금액, 수식어("대규모", "역대 최대", "본격")는 넣지 않습니다.
- 기업명은 널리 쓰는 한글 이름으로 통일합니다 (삼바 → 삼성바이오로직스, Lonza → 론자, WuXi → 우시).
- 정책·법안은 정식 통칭으로 씁니다 (BIOSECURE Act → 미국 생물보안법).
- 개별 계약 한 건 한 건을 구분하지 않습니다. 같은 기업의 수주 소식은 "기업명 수주"로 묶습니다.
- 기사가 여러 사건을 다루면 제목이 강조하는 사건 하나를 고릅니다.
- 영어 기사도 이슈 이름과 키워드는 한국어로 씁니다.

[issue_type — 이슈 유형] 아래 중 하나
- 정책·규제: 법안, 관세, 지원 정책, 정부 계획, 규제 변화
- 수주·계약: 위탁생산·개발 계약, 수주, 고객 확보
- 증설·투자: 공장 신설·증설, 설비 투자, 투자 유치·자금 조달
- M&A·진출: 인수합병, 지분 투자, 신규 사업 진출, 분할·구조 개편
- 실적: 매출·이익 발표, 실적 전망
- 기술·모달리티: ADC, 세포·유전자치료제, mRNA 등 기술과 생산 방식
- 품질·실사: GMP, FDA 실사·경고, 품질 문제, 인허가
- 기타: 위에 해당하지 않거나 CDMO와 관련이 약한 기사 (인사, 행사, 일반 산업 동향)

[keywords — 핵심 키워드]
- {KEYWORDS_RANGE[0]}~{KEYWORDS_RANGE[1]}개, 각각 {KEYWORD_MAX}자 이내의 명사.
- 기사에서 이 이슈를 가장 잘 나타내는 말을 고릅니다 (기업명, 정책명, 기술명, 사건의 종류).
- "CDMO", "바이오", "기업"처럼 거의 모든 기사에 나오는 말은 넣지 않습니다.

[confidence]
- high: 제목·본문에 이슈가 분명히 드러난다
- medium: 이슈는 짐작되지만 표현이 모호하다
- low: 제목만 있고 그것만으로는 어떤 사건인지 알기 어렵다

[규칙]
- 제목만 주어지면 제목만으로 판단합니다. 추측해서 사건을 만들어 내지 않습니다.
- 기사에 적힌 내용만 씁니다. 기사에 없는 기업·정책 이름을 넣지 않습니다.
- JSON 한 개만 답합니다."""

USER_TEMPLATE = """[기사]
언어: {lang}
발행일: {date}
매체: {press}
분류 키워드: {keyword}
제목: {title}
본문: {body}"""


def build_user_prompt(title: str, body: str | None, lang: str, date: str, press: str,
                      keyword: str | None) -> str:
    """기사 한 건의 사용자 프롬프트. 본문이 없으면 '(없음 — 제목만으로 판단)' 으로 표시한다."""
    body = (body or "").strip()
    body = body[:BODY_CHARS] + ("…" if len(body) > BODY_CHARS else "") if body else "(없음 — 제목만으로 판단)"
    return USER_TEMPLATE.format(lang=lang, date=date, press=press or "-", keyword=keyword or "-",
                                title=title, body=body)


def input_basis(body: str | None) -> str:
    return "body" if (body or "").strip() else "title"


def normalize_issue(issue: str) -> str:
    """이슈 이름의 표기 차이를 줄인 묶음 키 (공백·문장부호 제거, 영문 소문자)."""
    return re.sub(r"[^0-9a-z가-힣]", "", issue.lower())


def parse_response(text: str) -> dict:
    """LLM 응답에서 JSON을 꺼내 검증한다. 형식이 틀리면 ValueError (재시도 대상)."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError(f"JSON 없음: {text[:200]}")
    d = json.loads(m.group(0))
    issue = " ".join(str(d.get("issue", "")).split())
    if not issue:
        raise ValueError("issue 없음")
    if len(issue) > ISSUE_MAX:
        raise ValueError(f"issue 가 {ISSUE_MAX}자를 넘음: {issue}")
    if d.get("issue_type") not in ISSUE_TYPES:
        raise ValueError(f"잘못된 issue_type: {d.get('issue_type')}")
    if d.get("confidence") not in CONFIDENCES:
        raise ValueError(f"잘못된 confidence: {d.get('confidence')}")
    kws = d.get("keywords")
    if not isinstance(kws, list):
        raise ValueError("keywords 가 목록이 아님")
    seen, clean = set(), []
    for k in kws:
        k = " ".join(str(k).split())
        if k and k not in seen:
            seen.add(k)
            clean.append(k)
    lo, hi = KEYWORDS_RANGE
    if not lo <= len(clean) <= hi:
        raise ValueError(f"keywords 는 {lo}~{hi}개여야 함: {clean}")
    # 길이 제한을 넘는 키워드(긴 행사·기관 이름 등)는 그 키워드만 버린다. 하나 때문에 기사 전체를
    # 실패로 처리하지 않는다. 남는 키워드가 없을 때만 실패다.
    short = [k for k in clean if len(k) <= KEYWORD_MAX]
    if not short:
        raise ValueError(f"keyword 가 모두 {KEYWORD_MAX}자를 넘음: {clean}")
    clean = short
    if any(";" in k for k in clean):
        raise ValueError(f"keyword 에 ';' 가 있음: {clean}")
    return {"issue": issue, "issue_type": d["issue_type"], "keywords": "; ".join(clean),
            "confidence": d["confidence"]}
