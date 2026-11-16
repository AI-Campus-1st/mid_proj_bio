"""감성(영향) 분류 프롬프트 — 국내 CDMO 산업 관점의 기회 / 위험 / 중립.

라벨 정의와 판단 규칙은 docs/04_ai/AI_CLASSIFICATION.md 2절과 같다. 프롬프트를 바꾸면
PROMPT_VERSION 을 올리고, 문서의 변경 기록에 남긴다. (결과 파일에 버전이 함께 저장된다)
LLM 호출 코드는 이 모듈의 SYSTEM_PROMPT, build_user_prompt(), parse_response() 를 쓴다.
"""
import json
import re

PROMPT_VERSION = "sentiment-v1"
LABELS = ("기회", "위험", "중립")
CONFIDENCES = ("high", "medium", "low")
BODY_CHARS = 1500  # 본문은 앞부분만 넣는다 (호출량·비용 절감, 기사 핵심은 대개 앞부분에 있다)

SYSTEM_PROMPT = """당신은 국내 바이오 CDMO(위탁개발생산) 기업의 사업전략팀 애널리스트입니다.
뉴스 기사 한 건을 읽고, 이 기사가 **국내 CDMO 산업**(삼성바이오로직스, SK바이오사이언스,
프레스티지바이오로직스, 에스티팜, 바이넥스 등)에 주는 영향을 기회 / 위험 / 중립 중 하나로 분류합니다.

[라벨]
- 기회: 국내 CDMO의 수주·매출·생산능력·경쟁력에 유리한 사건이나 흐름
  (대형 수주·계약, 증설·신공장, 실적 개선, 국내 지원 정책, 해외 경쟁사 견제 규제, 신규 수요 확대 등)
- 위험: 국내 CDMO에 불리한 사건이나 흐름
  (관세·규제 부담, FDA 경고·실사 지적, 계약 해지·지연, 실적 악화, 해외 경쟁사의 확장·가격 공세, 소송·자금난 등)
- 중립: 영향 방향을 판단할 수 없거나 단순 사실 전달
  (인사·행사·일정 안내, 기회와 위험이 비슷하게 섞인 경우, CDMO와의 관련이 약한 경우)

[판단 규칙]
1. 기사의 어조(좋다/나쁘다)가 아니라 국내 CDMO 산업에 미치는 **영향 방향**으로 판단합니다.
   예: "미국 생물보안법으로 중국 CDMO 퇴출 위기"는 어조는 부정적이지만 국내 CDMO에는 기회입니다.
2. 해외 경쟁사(론자, 우시, 후지필름, 캐털런트 등)의 성장·증설은 위험, 해외 경쟁사의 악재는 기회로 봅니다.
3. 국내 CDMO 한 곳의 호재(수주·증설)는 기회, 악재는 위험으로 봅니다.
4. 기회와 위험이 함께 있으면 제목이 말하는 핵심 사건을 기준으로 합니다. 그래도 정할 수 없으면 중립입니다.
5. 제목만 주어지면 제목만으로 판단합니다. 추측이 필요하면 중립을 고르고 확신도를 low로 둡니다.
6. 영어 기사도 같은 기준으로 판단하고, 이유는 한국어로 씁니다.

[출력]
아래 JSON 한 줄만 출력합니다. 다른 문장은 쓰지 않습니다.
{"label": "기회|위험|중립", "reason": "판단 이유 한 문장(한국어)", "confidence": "high|medium|low"}"""

USER_TEMPLATE = """[기사]
언어: {lang}
발행일: {date}
매체: {press}
제목: {title}
본문: {body}"""


def build_user_prompt(title: str, body: str | None, lang: str, date: str, press: str) -> str:
    """기사 한 건의 사용자 프롬프트. 본문이 없으면 '(없음 — 제목만으로 판단)' 으로 표시한다."""
    body = (body or "").strip()
    body = body[:BODY_CHARS] + ("…" if len(body) > BODY_CHARS else "") if body else "(없음 — 제목만으로 판단)"
    return USER_TEMPLATE.format(lang=lang, date=date, press=press or "-", title=title, body=body)


def input_basis(body: str | None) -> str:
    """판단 근거 범위: 본문 앞부분이 있으면 'title+body', 없으면 'title'."""
    return "title+body" if (body or "").strip() else "title"


def parse_response(text: str) -> dict:
    """LLM 응답에서 JSON을 꺼내 검증한다. 형식이 틀리면 ValueError (재시도 대상)."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError(f"JSON 없음: {text[:200]}")
    d = json.loads(m.group(0))
    if d.get("label") not in LABELS:
        raise ValueError(f"잘못된 label: {d.get('label')}")
    if d.get("confidence") not in CONFIDENCES:
        raise ValueError(f"잘못된 confidence: {d.get('confidence')}")
    if not str(d.get("reason", "")).strip():
        raise ValueError("reason 없음")
    return {"label": d["label"], "reason": str(d["reason"]).strip(), "confidence": d["confidence"]}
