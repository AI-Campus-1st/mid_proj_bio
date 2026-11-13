"""수집 공통 설정: 기간, 뉴스 키워드, 후보 기업."""
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"

# 구글 뉴스 RSS 수집(collect_news.py)의 구간 기준일. 이미 받은 구간 기록과 맞물려 있어 바꾸지 않는다.
# 공시 수집과 DB 적재 기간은 아래 DB_START/DB_END(제공 뉴스 기간)를 쓴다.
START = date(2023, 11, 13)
END = date(2026, 11, 12)

# 가이드 2-3의 바이오 산업군 키워드와 카테고리
KEYWORDS = {
    "바이오 규제": "규제 및 정책",
    "바이오 특허": "기술 및 트렌드",
    "바이오 R&D": "기술 및 트렌드",
    "바이오 M&A": "시장 및 경쟁",
    "바이오 투자 유치": "시장 및 경쟁",
}

# 분석 범위: CDMO. (DART 회사명, 분야, 구분)
# 선정 = 분석 대상 5개사, 비교 = 선정 근거 검증용 CDMO 사업 보유 상장사
COMPANIES = [
    ("삼성바이오로직스", "CDMO", "선정"),
    ("에스티팜", "CDMO", "선정"),
    ("SK바이오사이언스", "CDMO", "선정"),
    ("바이넥스", "CDMO", "선정"),
    ("프레스티지바이오로직스", "CDMO", "선정"),
    ("차바이오텍", "CDMO", "비교"),
    ("이엔셀", "CDMO", "비교"),
    ("지씨셀", "CDMO", "비교"),
    ("메디포스트", "CDMO", "비교"),
    ("에이프로젠바이오로직스", "CDMO", "비교"),
    ("진원생명과학", "CDMO", "비교"),
    ("팬젠", "CDMO", "비교"),
    ("코오롱생명과학", "CDMO", "비교"),
    ("경보제약", "CDMO", "비교"),
]

# 뉴스 검색 시 회사명 외에 함께 셀 별칭
NEWS_ALIASES = {}


def load_env(name: str) -> str:
    """.env에서 키를 읽는다 (값은 출력하지 않는다)."""
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(name + "="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(f".env에 {name} 가 없습니다.")


# ---------------------------------------------------------------------------
# 통합 DB(뉴스·공시) 구축용 설정
# ---------------------------------------------------------------------------
# 제공 뉴스(02_BIO_news_3y)의 수집 기간. 통합 DB의 모든 자료는 이 기간으로 맞춘다.
DB_START = date(2023, 10, 19)
DB_END = date(2026, 10, 19)

PROVIDED_NEWS_DIR = ROOT / "02_BIO_news_3y"
DB_PATH = ROOT / "data" / "db" / "bio_cdmo.sqlite"

# 분석 대상 5개사와 뉴스 본문·제목에서 기업을 찾는 정규식.
# - '삼성바이오'는 삼성바이오에피스(별도 법인)와 구분한다.
# - 프레스티지바이오파마(모회사)는 다른 법인이므로 '로직스'까지 일치할 때만 잡는다.
SELECTED = [name for name, _, status in COMPANIES if status == "선정"]
COMPANY_PATTERNS = {
    "삼성바이오로직스": r"삼성바이오로직스|삼성바이오(?!에피스|로직스)|삼바(?![가-힣])",
    "에스티팜": r"에스티팜|ST팜|ST Pharm",
    "SK바이오사이언스": r"SK\s?바이오사이언스|SK바사",
    "바이넥스": r"바이넥스",
    "프레스티지바이오로직스": r"프레스티지바이오로직스|프레스티지로직스",
}
CDMO_PATTERN = r"CDMO|(?<![A-Za-z])CMO(?![A-Za-z])|위탁개발생산|위탁생산|위탁개발"


# ---------------------------------------------------------------------------
# CDMO 세부 업종 키워드 (조에서 정의) — 추가 수집과 재분류에 함께 쓴다
# ---------------------------------------------------------------------------
CDMO_KEYWORDS = {
    "CDMO 규제·정책": "규제 및 정책",
    "CDMO 지정학": "규제 및 정책",
    "CDMO 모달리티": "기술 및 트렌드",
    "CDMO 생산능력": "시장 및 경쟁",
    "CDMO 수주": "시장 및 경쟁",
    "CDMO 경쟁 구도": "시장 및 경쟁",
}

# 키워드별 구글 뉴스 검색어. 키워드 이름 그대로는 기사에 잘 쓰이지 않으므로 주요 이슈 표현으로 검색한다.
CDMO_QUERIES = {
    "CDMO 규제·정책": ["CDMO 특별법", "CDMO 국가바이오위원회", "CDMO GMP", "CDMO FDA 실사",
                    "위탁생산 품질관리 규제"],
    "CDMO 지정학": ["CDMO 생물보안법", "CDMO 의약품 관세", "CDMO 미국 현지 생산"],
    "CDMO 모달리티": ["CDMO ADC", "CDMO 세포유전자치료제", "CDMO mRNA", "CDMO 항체의약품"],
    "CDMO 생산능력": ["CDMO 증설", "CDMO 공장 착공", "CDMO 생산능력", "CDMO 정책금융"],
    "CDMO 수주": ["CDMO 수주", "CDMO 위탁생산 계약", "CDMO 빅파마", "CDMO 실적"],
    "CDMO 경쟁 구도": ["CDMO 인수", "CDMO 진출", "CDMO 론자", "CDMO 우시", "CDMO 경쟁"],
}
CDMO_NEWS_DIR = RAW_DIR / "news_cdmo"
CDMO_OUT_DIR = ROOT / "03_CDMO_news_3y"


# ---------------------------------------------------------------------------
# 해외(영어) 뉴스 보강 — 국내 언론 중심인 뉴스의 "글로벌" 범위를 보완한다
# ---------------------------------------------------------------------------
# 구글 뉴스 미국판(영어)으로 검색한다. 원문(영어)으로 저장하고, 번역은 대시보드에서 한다.
# 키워드 -> {이슈(한국어 라벨): 영어 검색어}
GLOBAL_QUERIES = {
    "CDMO 지정학": {
        "생물보안법": "CDMO BIOSECURE Act",
        "의약품 관세": "CDMO pharmaceutical tariffs",
        "미국 현지 생산": "CDMO US manufacturing",
        "유럽 현지 생산": "CDMO Europe manufacturing",
    },
}
GLOBAL_NEWS_DIR = RAW_DIR / "news_global"

# 영어 기사용 기업 패턴. 영어 기사에만 적용해 한국어 기사의 매핑 결과는 바꾸지 않는다.
COMPANY_PATTERNS_EN = {
    "삼성바이오로직스": r"(?i)Samsung Biologics",
    "에스티팜": r"(?i)ST\s?Pharm",
    "SK바이오사이언스": r"(?i)SK\s?bioscience",
    "바이넥스": r"(?i)Binex",
    "프레스티지바이오로직스": r"(?i)Prestige\s?Biologics",
}
CDMO_PATTERN_EN = (r"(?i)CDMO|(?<![A-Za-z])CMO(?![A-Za-z])"
                   r"|contract (?:development and )?manufactur")
