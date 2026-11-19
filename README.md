# 바이오 CDMO 산업 이슈 대시보드 (중간프로젝트)

뉴스와 DART 공시로 바이오 CDMO 5개사(삼성바이오로직스, SK바이오사이언스, 프레스티지바이오로직스, 에스티팜, 바이넥스)의 이슈를 분석한다.

- 과제 안내: `중간프로젝트_가이드_뉴스공시_산업이슈_대시보드.md`
- 기업 선정 근거: `docs/company_selection.md`
- 데이터 구조: `docs/data_schema.md`
- 텍스트 정제·EDA 결과: `docs/eda_report.md`

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
| `analysis/` | 분석 계층 — 기업 선정용 공시 가중 점수, 뉴스 통합·재분류, 텍스트 정제(`clean_text.py`), EDA(`eda.py`) |
| `rag/` | 공시 RAG — 색인(`build_index.py`), 질의응답(`qa.py`), 평가(`eval_rag.py`) |
| `tests/` | 대시보드 통합 점검 — 7개 화면 × 필터 조합 자동 실행(`check_dashboard_filters.py`, API 호출 없음). 결과는 `docs/07_project-management/TEST_PLAN.md` |
| `dashboard/` | Streamlit 대시보드 — 실행 파일(`app.py`), 공통(`core/`: 화면 부품·필터·데이터 읽기·색), 화면(`views/` S0~S6). 테마는 루트 `.streamlit/config.toml` |
| `data/raw/` | 수집 원본 (JSON, JSONL, zip) |
| `data/processed/` | 분석 산출물 — 기업 선정 점수, EDA 집계표(`eda_*.csv`) |
| `data/db/` | 통합 DB `bio_cdmo.sqlite` (git 제외, 아래 순서로 재생성) |
| `chroma_db/` | 공시 RAG 색인 (git 제외, 약 692MB. 아래 "공시 RAG" 순서로 만들거나 팀원에게 폴더를 받는다) |
| `docs/` | 선정 근거, 스키마 문서, EDA 리포트(차트는 `docs/figures/eda/`) |

## 기술 스택

수집·적재(`collect/`, `db/`)는 표준 라이브러리만 사용한다. 분석·LLM·대시보드 단계는 아래 패키지를 쓴다. 버전은 `requirements.txt` 참고.

| 영역 | 사용 도구 |
|---|---|
| 저장·처리 | SQLite, `pandas`, `numpy`, `SQLAlchemy` |
| EDA·시계열 | `statsmodels`, `ruptures`(변화점 탐지), `scikit-learn`, `kiwipiepy`(한국어 형태소 분석) |
| 시각화 | `matplotlib`, `seaborn`, `plotly` |
| LLM·RAG | `openai`(감성 분류·RAG), `langchain`, `chromadb` |
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
OPENAI_API_KEY=발급받은_OpenAI_API_키
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

7. 통합 DB 생성 — 6번의 통합본과 3번의 공시를 적재. 뉴스 제목·본문을 정제해 `news_clean` 테이블에 함께 싣는다 (규칙은 `analysis/clean_text.py`)

```bash
python db/build_db.py
```

8. EDA — 기사량·공시 추이와 이슈 급증 시점을 집계하고 차트를 만든다 (`data/processed/eda_*.csv`, `docs/figures/eda/`, 해석은 `docs/eda_report.md`). pandas·matplotlib이 필요하다

```bash
python analysis/eda.py
```

기간은 `collect/config.py` 의 `DB_START`, `DB_END` 로 정한다. 값을 바꾸면 `data/raw/dart/list_selected/` 를 비우고 3번부터 다시 실행한다.

## 실행 순서 — 공시 RAG (공시 Q&A)

통합 DB(위 7번)가 있어야 한다. `.env` 의 `OPENAI_API_KEY` 를 쓰며 **API 비용이 든다.** 설계는 `docs/04_ai/NEWS_DISCLOSURE_MATCHING.md` 4절, 평가 결과는 `docs/04_ai/AI_EVALUATION.md` 6절.

1. 색인 — 공시 본문을 잘라 임베딩하고 `chroma_db/` 에 저장한다. 청킹·임베딩·적재가 한 번에 일어나며 따로 띄울 서버는 없다. 먼저 `--dry-run` 으로 청크 수와 예상 비용을 확인한다 (전체 864건 → 36,548청크, 약 15분, 가격표 기준 약 $0.58). 중간에 끊기면 같은 명령을 다시 실행한다

```bash
python rag/build_index.py --dry-run
python rag/build_index.py
```

2. 질의응답 — 질문 한 번에 임베딩 1회와 답변 LLM 1회를 호출한다. 근거 공시(공시명·제출일·링크)를 함께 보여 주고, 근거가 없으면 거절한다. 대시보드에서는 `rag/qa.py` 의 `ask()` 를 불러 쓴다

```bash
python rag/qa.py "SK바이오사이언스의 RSV 예방항체 기술도입 계약의 상대방은?"
```

3. 평가 — 질문 20개(`data/eval/rag_questions.csv`)로 검색 정확도와 거절 정확도를 잰다 (`data/eval/rag_eval_result.md`). `--rescore` 는 호출 없이 저장된 결과로 집계만 다시 만든다

```bash
python rag/eval_rag.py
```

## 실행 — 대시보드

저장소 루트에서 실행한다(루트의 `.streamlit/config.toml` 테마를 읽는다). 통합 DB(`data/db/bio_cdmo.sqlite`)가 있어야 하고, 공시 Q&A 화면은 `chroma_db/` 와 `.env` 의 `OPENAI_API_KEY` 도 필요하다. 없으면 그 화면만 "설정 확인" 안내를 띄우고 다른 화면은 동작한다. Q&A는 질문할 때만 API를 호출한다(질문 한 번에 1센트 미만).

```bash
streamlit run dashboard/app.py
```

요약(S0) 화면의 결론 문장과 기회·위험 카드는 `data/processed/summary_cards.json` 을 읽는다. 카드 주제·문구는 `analysis/build_summary_cards.py` 안에 정해 두었고(팀 확인), 근거 기사·건수·기간은 실행할 때 데이터에서 뽑는다(LLM 호출 없음). 감성·이슈 결과나 DB가 바뀌면 다시 만든다.

```bash
python analysis/build_summary_cards.py
```

현재 구현 (2026-11-19):

| 화면 | 구현된 내용 | 준비 중 |
|---|---|---|
| 공통 | 메뉴·사이드바 필터(기간·기업·카테고리)·공통 부품·테마, 차트 아래 표 보기 | |
| S0 요약 | 결론 문장, 지표 4개(기회·위험 기사, 연결 공시, 급증 시점), 기회 5·위험 3 카드, 월별 기회 vs 위험, 공시 Q&A 바로가기, 최근 주요 공시 | |
| S1 이슈·트렌드 | 기사량 추이, 급증 시점 목록과 대표 기사, 부상 이슈(직전 3개월 대비) | |
| S2 규제·정책 | 감성 지표, 정책·규제 타임라인, 월별 기회/위험/중립 기사 수, 언급 기업. 영어 기사는 한국어 번역 제목 | 해외 CDMO 언급 수 |
| S3 기술·생산 | 모달리티별 언급 추이, 기업 × 모달리티 히트맵, 증설 공시 | |
| S4 기업 비교 | 주요 분류별 공시 건수, 기업별 공시 타임라인, 수주 계약 금액 추이 | |
| S5 뉴스-공시 연계 | 연결 지표(연결된 기사·연결 공시·연결 없는 기사 비율), 기업별 기사량과 공시 시점, 이슈별 관련 공시 | |
| S6 공시 Q&A | 질문 → 답변과 근거 공시(공시명·제출일·DART 링크·인용 구절), 근거가 없으면 거절하고 관련 뉴스 표시, 질문 기록 | |

## 기업 선정 근거 재현

`docs/company_selection.md` 7절 참고.

