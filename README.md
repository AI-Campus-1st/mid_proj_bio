# 바이오 CDMO 산업 이슈 대시보드 (중간프로젝트)

뉴스와 DART 공시로 바이오 CDMO 5개사(삼성바이오로직스, SK바이오사이언스, 프레스티지바이오로직스, 에스티팜, 바이넥스)의 이슈를 분석한다.

- 과제 안내: `중간프로젝트_가이드_뉴스공시_산업이슈_대시보드.md`
- 기업 선정 근거: `docs/기업선정_근거.md`
- 데이터 구조: `docs/데이터_스키마.md`

> **대시보드가 답해야 하는 질문**
> "이 산업에서 지금 무슨 일이 일어나고 있으며, 그 판단의 근거는 무엇인가."

## 수행 단계

| 단계 | 수행 내용 |
|---|---|
| 데이터 수집·DB화 | DART OpenAPI 기반 공시 수집, 뉴스·공시 통합 저장 |
| EDA·시계열 분석 | 기사량 추이, 이슈 급증 시점 탐지 |
| LLM·RAG | 이슈 추출·감성 분류, 공시 문서 질의응답 |
| 스토리텔링 시각화 | 의사결정 관점의 대시보드 구성 |

## 디렉터리

| 경로 | 내용 |
|---|---|
| `02_BIO_news_3y/` | 제공 뉴스 CSV (2023-10-19 ~ 2026-10-19) |
| `03_CDMO_news_3y/` | CDMO 키워드로 재분류한 뉴스 통합본 (제공 + 추가 수집) |
| `collect/` | 수집 계층 — DART 공시, 추가 뉴스. 응답 원본을 `data/raw/` 에 저장 |
| `db/` | 적재 계층 — 통합 스키마(`schema.sql`)와 DB 구축(`build_db.py`) |
| `analysis/` | 분석 계층 — 기업 선정용 공시 가중 점수 |
| `data/raw/` | 수집 원본 (JSON, JSONL, zip) |
| `data/db/` | 통합 DB `bio_cdmo.sqlite` (git 제외, 아래 순서로 재생성) |
| `docs/` | 선정 근거, 스키마 문서 |

## 기술 스택

수집·적재(`collect/`, `db/`)는 표준 라이브러리만 사용한다. 분석·LLM·대시보드 단계는 아래 패키지를 쓴다. 버전은 `requirements.txt` 참고.

| 영역 | 사용 도구 |
|---|---|
| 저장·처리 | SQLite, `pandas`, `numpy`, `SQLAlchemy` |
| EDA·시계열 | `statsmodels`, `ruptures`(변화점 탐지), `scikit-learn`, `kiwipiepy`(한국어 형태소 분석) |
| 시각화 | `matplotlib`, `seaborn`, `plotly` |
| LLM·RAG | `anthropic`(Claude), `langchain`, `chromadb` |
| 대시보드 | `streamlit` |

## 준비

- Python 3.10 이상 (`requirements.txt` 는 3.12 기준으로 고정).
- 가상환경을 만들고 패키지를 설치한다.

```bash
python -m venv .venv
```

```bash
.\.venv\Scripts\Activate.ps1
```

(macOS / Linux: `source .venv/bin/activate`)

```bash
pip install -r requirements.txt
```

- `.env.example` 을 복사해 프로젝트 루트에 `.env` 를 만들고 키를 넣는다. (`.gitignore` 등록됨)

```
DART_OPEN_API=발급받은_DART_인증키
ANTHROPIC_API_KEY=발급받은_Anthropic_API_키
```

## 실행 순서 — 통합 DB 구축

모든 수집 스크립트는 받은 파일을 건너뛰므로 중간에 끊겨도 다시 실행하면 이어서 받는다.

1. 기업 코드와 후보 14개사 공시 목록 (기업 선정 단계에서 실행, `companies.json` 생성)

```bash
python collect/collect_dart_list.py
```

2. 5개사 기업명 뉴스 (구글 뉴스 RSS)

```bash
python collect/collect_news.py company
```

```bash
python collect/collect_news_selected.py
```

3. 5개사 공시 목록과 원문 (제공 뉴스와 같은 기간)

```bash
python collect/collect_dart_selected.py
```

4. CDMO 키워드 뉴스 추가 수집 (구글 뉴스 RSS, 20~30분)

```bash
python collect/collect_news_cdmo.py
```

5. 해외(영어) 뉴스 추가 수집 — CDMO 지정학 이슈를 구글 뉴스 미국판으로 검색 (`data/raw/news_global/`, 영어 원문 저장)

```bash
python collect/collect_news_global.py
```

6. 뉴스 통합본 생성 — 제공·팀원 수집(`data/raw/cdmo_*.csv`)·구글 뉴스 수집분(해외 포함)을 합치고 CDMO 키워드로 재분류 (`03_CDMO_news_3y/`, 설명은 `docs/news_sort.md`)

```bash
python analysis/build_cdmo_news.py
```

7. 통합 DB 생성 — 6번의 통합본과 3번의 공시를 적재

```bash
python db/build_db.py
```

기간은 `collect/config.py` 의 `DB_START`, `DB_END` 로 정한다. 값을 바꾸면 `data/raw/dart/list_selected/` 를 비우고 3번부터 다시 실행한다.

## 기업 선정 근거 재현

`docs/기업선정_근거.md` 7절 참고.

## 브랜치 전략 (Gitflow)

| 브랜치 | 용도 |
|---|---|
| `main` | 운영 배포본 |
| `develop` | 개발 통합본 |
| `feature/<이름>` | 기능 작업 — `develop` 에서 분기, `develop` 으로 Pull Request |
| `release/<버전>` | 출시 준비 — `develop` 에서 분기, `main` 으로 Pull Request 후 `develop` 에도 반영 |
| `hotfix/<이름>` | 긴급 수정 — `main` 에서 분기, `main` 으로 Pull Request 후 `develop` 에도 반영 |

`main` 과 `develop` 에는 직접 커밋하지 않고 Pull Request 로만 반영한다. 머지는 사람이 한다.
