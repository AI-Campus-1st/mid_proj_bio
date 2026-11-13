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
