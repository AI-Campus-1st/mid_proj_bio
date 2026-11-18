"""모달리티 태깅 프롬프트 (T3).

기사 한 건이 어떤 모달리티(의약품 종류)를 다루는지 태그를 붙인다. S3 기술·생산 화면의
"기업 × 모달리티 히트맵"과 "모달리티별 언급 추이"에 쓴다 (PRD F3, UI 명세 5-4절).
LLM 호출 코드는 이 모듈의 SYSTEM_PROMPT, build_user_prompt(), parse_response() 를 쓴다.
프롬프트를 바꾸면 PROMPT_VERSION 을 올린다 (결과 파일에 버전이 함께 저장된다).

태그 목록과 근거 (2026-11-18 결정)
  PRD F3 의 5개 (항체, ADC, mRNA, 세포·유전자치료제, 올리고) + 펩타이드 + 백신 + 기타.
  - 펩타이드: 중복 제외 기사 9,142건 중 표현이 나온 기사 약 641건(정규식 근사, 2위).
    GLP-1 비만약 수요와 삼성바이오로직스의 폴리펩타이드 인수 때문에 빠지면 핵심 흐름을 놓친다.
  - 백신: 약 521건. SK바이오사이언스의 주력 사업이라 빠지면 5개사 중 한 행이 거의 빈다.
  - 이중항체(약 81건)는 생산 방식이 항체와 같아 "항체"에, 플라스미드(약 13건)는 유전자치료제
    원료라 "세포·유전자치료제"에 합쳤다. 건수가 작아 따로 두면 히트맵 칸이 거의 비기 때문이다.
  - 오가노이드·엑소좀·저분자 등은 "기타". CDMO 생산 모달리티로 보기 어렵거나 건수가 작다.
  - 생산기술(싱글유즈, 연속공정 등) 태그는 만들지 않는다. 이를 보여 줄 화면이 UI 명세에 없다.
다중 태그: 한 기사가 여러 모달리티를 다루는 경우("ADC·항체 수주")가 흔해 여러 개를 허용한다.
  하나만 고르게 하면 정보가 사라진다. 태그가 없으면(빈 목록) 특정 모달리티를 다루지 않는 기사다.
"""
import json
import re

# v1 → v2 (2026-11-18): 시험 50건에서 삼성바이오로직스 유상증자 기사 5건이 "기존 항체·mRNA·ADC에 이어
#   펩타이드까지" 같은 배경 나열 때문에 4개 태그를 받았다 (사건의 대상은 펩타이드뿐). 같은 이슈 기사가
#   120건 넘게 있어 히트맵의 삼성 행이 부풀려지므로, "사건의 대상 모달리티만" 규칙을 예시와 함께 분명히 했다.
#   근거 표현도 최대 3개라 4번째 태그의 근거가 잘렸으므로 태그 수만큼 받도록 바꿨다.
PROMPT_VERSION = "modality-v2"
MODALITIES = ("항체", "ADC", "mRNA", "세포·유전자치료제", "올리고", "펩타이드", "백신", "기타")
CONFIDENCES = ("high", "medium", "low")
BODY_CHARS = 1500     # 본문은 앞부분만 넣는다 (감성 분류·이슈 추출과 같은 기준)
EVIDENCE_MAX = len(MODALITIES)   # 태그마다 하나씩 — 태그 수보다 적게 받으면 근거 없는 태그가 생긴다
EVIDENCE_CHARS = 20   # 프롬프트에 적는 근거 표현 길이 — 단어·짧은 구만 받는다 (문장 인용 방지)
# 검증에서 받아 주는 길이. 영어 용어는 같은 뜻도 길어서("cell and gene therapy" 21자, "Plasmid & Viral
# Vector" 22자) 20자로 검증하면 맞는 태그가 실패한다 (전체 실행에서 영어 기사 3건이 계속 실패, 2026-11-18).
# 프롬프트 문구는 그대로 두고 검증만 넓혀, 이미 성공한 4,700여 건을 다시 돌리지 않는다. 30자면 영어 3~4단어 구까지
# 받고 문장 인용은 여전히 막는다.
EVIDENCE_ACCEPT = 30

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "modalities": {"type": "array", "items": {"type": "string", "enum": list(MODALITIES)}},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "string", "enum": list(CONFIDENCES)},
    },
    "required": ["modalities", "evidence", "confidence"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """당신은 글로벌 바이오 CDMO(위탁개발생산) 시장을 분석하는 애널리스트입니다.
뉴스 기사 한 건을 읽고, 이 기사가 다루는 **모달리티(의약품의 종류)** 를 아래 목록에서 모두 고릅니다.
모달리티가 다르면 생산 설비와 공정이 달라서, CDMO가 어떤 모달리티를 하는지가 곧 사업 영역입니다.

[modalities — 아래 중 해당하는 것을 모두. 없으면 빈 목록]
- 항체: 단일클론항체, 항체의약품, 바이오시밀러(항체 바이오시밀러), 이중항체, 항체 신약
- ADC: 항체-약물 접합체. ADC만 다루면 "항체"는 따로 붙이지 않습니다
- mRNA: mRNA 백신·치료제. mRNA 백신은 "백신"이 아니라 "mRNA"로만 붙입니다
- 세포·유전자치료제: CAR-T, 줄기세포, 세포치료제, 유전자치료제, AAV·렌티바이러스 등 바이러스 벡터, 플라스미드 DNA, CGT
- 올리고: 올리고뉴클레오타이드(올리고핵산) 치료제·원료
- 펩타이드: 펩타이드 의약품·원료, GLP-1 계열 비만·당뇨 치료제(펩타이드 주사제). 경구 저분자 GLP-1은 "기타"
- 백신: mRNA가 아닌 백신 (재조합 단백질, 합성항원, 바이러스벡터 백신 등)
- 기타: 위에 없는 구체적인 모달리티 (저분자 합성의약품, 오가노이드, 엑소좀, 마이크로바이옴 등)

[태그를 붙이는 기준]
- 기사에 그 모달리티가 **이름이나 분명한 설명으로 나올 때만** 붙입니다. 기업의 주력 분야를 안다고 추측해서 붙이지 않습니다.
  예: "삼성바이오로직스 수주" 기사에 모달리티가 적혀 있지 않으면 빈 목록입니다.
- "바이오의약품", "신약", "의약품 위탁생산"처럼 종류를 특정하지 않는 말만 있으면 빈 목록입니다.
- **이 기사가 다루는 사건·주제의 대상인 모달리티만** 붙입니다 (그 모달리티의 계약, 생산, 투자, 인수, 개발, 시장 동향).
- 배경 설명으로 나열만 된 모달리티는 붙이지 않습니다.
  예: "기존 항체·mRNA·ADC에 이어 펩타이드까지 포트폴리오를 넓힌다"는 펩타이드 인수 기사 → "펩타이드"만.
  예: 회사 소개 문단의 "항체 의약품 위탁생산 서비스를 제공하는 기업" → 그 기사의 사건이 항체 생산이 아니면 붙이지 않습니다.
- 여러 기업·제품 소식을 모은 기사(업계 소식 모음 등)는 각 소식의 대상 모달리티를 모두 붙입니다.

[evidence — 근거 표현]
- 고른 태그마다 기사에 실제로 나온 표현을 하나씩, 태그 순서대로 씁니다. 각 20자 이내의 단어나 짧은 구로 씁니다 (예: "ADC", "항체-약물 접합체", "GLP-1").
- 태그가 없으면 빈 목록입니다.

[confidence]
- high: 모달리티가 이름으로 분명히 나온다 (또는 분명히 나오지 않는다)
- medium: 설명은 있지만 어느 태그인지 해석이 필요하다
- low: 제목만 있어 판단 근거가 부족하다

[규칙]
- 영어 기사도 같은 기준으로 판단합니다.
- 기사에 적힌 내용만 씁니다. JSON 한 개만 답합니다."""

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
    return "body" if (body or "").strip() else "title"


def parse_response(text: str) -> dict:
    """LLM 응답에서 JSON을 꺼내 검증한다. 형식이 틀리면 ValueError (재시도 대상).

    modalities 는 목록 순서(MODALITIES)로 정렬해 '; ' 로 잇는다. 빈 목록이면 빈 문자열.
    근거 표현은 길이 제한을 넘는 것만 버린다 (태그 판정 자체는 유지한다).
    """
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError(f"JSON 없음: {text[:200]}")
    d = json.loads(m.group(0))
    mods = d.get("modalities")
    if not isinstance(mods, list):
        raise ValueError("modalities 가 목록이 아님")
    bad = [x for x in mods if x not in MODALITIES]
    if bad:
        raise ValueError(f"잘못된 모달리티: {bad}")
    mods = [x for x in MODALITIES if x in set(mods)]
    if d.get("confidence") not in CONFIDENCES:
        raise ValueError(f"잘못된 confidence: {d.get('confidence')}")
    ev = d.get("evidence")
    if not isinstance(ev, list):
        raise ValueError("evidence 가 목록이 아님")
    seen, clean = set(), []
    for e in ev:
        e = " ".join(str(e).replace(";", ",").split())
        if e and e not in seen and len(e) <= EVIDENCE_ACCEPT:
            seen.add(e)
            clean.append(e)
    if mods and not clean:
        raise ValueError(f"태그 {mods} 에 근거 표현이 없음: {ev}")
    return {"modalities": "; ".join(mods), "evidence": "; ".join(clean[:EVIDENCE_MAX]),
            "confidence": d["confidence"]}
