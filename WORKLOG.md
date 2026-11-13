# 작업 기록

프로젝트 환경 구성부터 해외 뉴스 보강까지 진행한 작업을 순서대로 정리한다. (2026-11-13 기준)

- **저장소:** [AI-Campus-1st/mid_proj_bio](https://github.com/AI-Campus-1st/mid_proj_bio)
- **브랜치 운영:** Gitflow (`main` 운영 배포본, `develop` 개발 통합본, 작업은 `feature/*` → `develop` Pull Request)

---

## 요약

| # | 작업 | 결과물 | Pull Request |
|---|---|---|---|
| 1 | Python 개발 환경 구성 | `requirements.txt`, `.env.example`, `.gitignore` | [#1](https://github.com/AI-Campus-1st/mid_proj_bio/pull/1) |
| 2 | 팀 저장소 연결과 Gitflow 구성 | `develop` 브랜치, README 브랜치 전략 | [#1](https://github.com/AI-Campus-1st/mid_proj_bio/pull/1) |
| 3 | README 통합 | `README.md` | [#1](https://github.com/AI-Campus-1st/mid_proj_bio/pull/1) |
| 4 | 대시보드 사용자·핵심 질문 정의 | `docs/대시보드_사용자_핵심질문.md` | [#2](https://github.com/AI-Campus-1st/mid_proj_bio/pull/2) |
| 5 | 해외(영어) 뉴스 보강 — CDMO 지정학 | 수집 스크립트, 통합본·DB 확장 | [#4](https://github.com/AI-Campus-1st/mid_proj_bio/pull/4) |

모든 PR은 `develop` 에 머지되었고, #1·#2는 [#3](https://github.com/AI-Campus-1st/mid_proj_bio/pull/3)으로 `main` 에도 반영되었다. #4는 `develop` 에만 있다.

---

## 1. Python 개발 환경 구성

과제 4단계(수집·DB화 → EDA·시계열 → LLM·RAG → 시각화)에 필요한 패키지를 정리했다.

- **가상환경:** Python 3.12, 프로젝트 루트의 `.venv/` (Git 제외)
- **`requirements.txt`:** 설치한 버전으로 고정

| 영역 | 패키지 |
|---|---|
| 수집 | `requests`, `beautifulsoup4`, `lxml`, `feedparser`, `OpenDartReader`, `python-dotenv` |
| 저장·처리 | `pandas`, `numpy`, `SQLAlchemy`, `openpyxl` |
| EDA·시계열 | `statsmodels`, `ruptures`(변화점 탐지), `scikit-learn`, `kiwipiepy`(한국어 형태소 분석) |
| 시각화 | `matplotlib`, `seaborn`, `plotly` |
| LLM·RAG | `anthropic`, `langchain`, `langchain-anthropic`, `langchain-chroma`, `langchain-text-splitters`, `chromadb` |
| 대시보드 | `streamlit` |
| 개발 | `jupyter`, `ipykernel` |

- **`.env.example`:** `DART_OPEN_API`(팀 코드의 키 이름), `ANTHROPIC_API_KEY`
- **`.gitignore`:** 팀 규칙(`.env`, `data/db/`, `data/raw/dart/document/`)을 유지하고 가상환경, `.env.*`, 벡터 DB(`chroma_db/`), Jupyter·IDE 파일을 추가했다. 팀이 커밋하는 `data/raw/` 는 제외하지 않았다.

수집·적재 코드(`collect/`, `db/`)는 기존대로 표준 라이브러리만 쓴다. `requirements.txt` 는 분석 이후 단계용이다.

---

## 2. 팀 저장소 연결과 Gitflow 구성

- 처음에는 개인 저장소에 연결되어 있어, 원격 `origin` 을 팀 저장소로 바꿨다.
- 팀 저장소에는 `main` 만 있어 `main` 에서 `develop` 을 만들었다.
- README에 브랜치 전략을 적었다.

| 브랜치 | 용도 |
|---|---|
| `main` | 운영 배포본 |
| `develop` | 개발 통합본 |
| `feature/<이름>` | `develop` 에서 분기 → `develop` 으로 PR |
| `release/<버전>` | `develop` 에서 분기 → `main` 으로 PR, 머지 후 `develop` 에도 반영 |
| `hotfix/<이름>` | `main` 에서 분기 → `main` 으로 PR, 머지 후 `develop` 에도 반영 |

`main`·`develop` 에는 직접 커밋하지 않고 PR로만 반영하며, 머지는 사람이 한다.

> **참고:** PR #3(`develop` → `main`) 머지 후 원격 `develop` 이 삭제되어 있어 `main` 과 같은 위치로 다시 만들었다. `develop` 은 계속 쓰는 브랜치이므로 PR 머지 화면에서 "Delete branch" 를 누르지 않도록 주의한다. (저장소 설정의 자동 삭제는 꺼져 있다.)

---

## 3. README 통합

팀원이 작성한 README를 기본으로 두고 아래 내용을 더했다.

- 대시보드가 답해야 하는 질문, 수행 4단계
- 기술 스택, 가상환경 설치와 `.env` 설정 방법
- Gitflow 브랜치 전략
- 실행 순서에 해외 뉴스 수집 단계 (5번에서 추가)

---

## 4. 대시보드 사용자·핵심 질문 정의

`docs/대시보드_사용자_핵심질문.md` — 대시보드가 페르소나와 핵심 질문을 반영하는지 확인하는 기준 문서이다.

- **사용자:** 바이오 CDMO 기업의 사업전략·기획 담당자 (예시: 중견 CDMO 사업전략팀 과장)
- **Core Question:** 글로벌 바이오 CDMO 산업에서 지금 어떤 변화가 발생하고 있으며, 이 변화가 우리 기업의 사업 기회와 경쟁력에 어떤 영향을 미치는가?
- **구성:**
  - Pain Point 4개와 이를 해소하는 기능
  - 영역별 핵심 질문 5개 ↔ Supporting Questions 5개 ↔ 대시보드 기능 연결
  - 기능 ①~⑥(핵심 이슈, 규제·정책, 기술·생산능력, 기업 비교, 뉴스-공시 연계, 기회·위험 요약)의 화면·분석 방법·사용 데이터
  - 사용 시나리오(미국 공급망 정책)를 단계별로 기능에 대응
  - 구현 후 확인할 반영 점검표
  - 데이터 한계와 보완 방향

대시보드는 아직 구현 전이므로 점검표는 구현 후 체크한다.

---

## 5. 해외(영어) 뉴스 보강 — CDMO 지정학

### 배경

뉴스가 국내 언론 중심이라 Core Question의 "글로벌" 범위를 충분히 다루지 못한다(문서 4의 한계). 지정학 이슈는 미국·유럽 정책에서 출발하므로, 같은 이슈를 영어로 검색해 보강했다.

### 수집 — `collect/collect_news_global.py`

구글 뉴스 RSS 미국판(영어)으로 2023-10-19 ~ 2026-10-19 기간을 30일 구간으로 검색했다. 검색어는 `collect/config.py` 의 `GLOBAL_QUERIES` 에 있다.

| 키워드 | 세부 이슈 | 영어 검색어 |
|---|---|---|
| CDMO 지정학 | 생물보안법 | `CDMO BIOSECURE Act` |
| CDMO 지정학 | 의약품 관세 | `CDMO pharmaceutical tariffs` |
| CDMO 지정학 | 미국 현지 생산 | `CDMO US manufacturing` |
| CDMO 지정학 | 유럽 현지 생산 | `CDMO Europe manufacturing` |

- 원본: `data/raw/news_global/CDMO_지정학_en.jsonl` (1,004행, 기사 800건)
- 영어 원문 그대로 저장하고, **한국어 번역은 대시보드에 보여줄 때** 한다.

### 통합본 — `analysis/build_cdmo_news.py`

팀원이 만든 통합·재분류 단계에 해외 뉴스를 추가했다.

- 수집출처 `해외검색` (우선순위 맨 뒤), 새 열 `언어` (`ko` / `en`)
- 같은 6개 CDMO 키워드를 영어 표현으로 옮긴 규칙(`GATE_EN`, `RULES_EN`)으로 분류
- 세부 이슈는 `원수집키워드` 에 기록
- 통합본 8,419건 → **9,216건** (해외검색 797건 추가)

| 키워드 (복수 포함) | 해외검색 건수 |
|---|---|
| CDMO 지정학 | 388 |
| CDMO 생산능력 | 258 |
| CDMO 경쟁 구도 | 214 |
| CDMO 수주 | 161 |
| CDMO 모달리티 | 69 |
| CDMO 규제·정책 | 57 |

### DB — `db/schema.sql`, `db/build_db.py`

| 변경 | 내용 |
|---|---|
| `news.origin` | `google_global` 추가 |
| `news.lang` | 기사 언어 `ko` / `en` |
| `news.title_ko` | 한국어 번역 제목 캐시. 적재 시 NULL, 번역 단계에서 채움 |
| `news.search_terms` | 해외 기사는 세부 이슈(생물보안법 등) |
| `v_documents` | `lang`, `title_ko` 컬럼 추가 |
| 기업·CDMO 판정 | 영어 기사는 영어 패턴(`COMPANY_PATTERNS_EN`, `CDMO_PATTERN_EN`) 사용 |

영어 기사 기업 매핑: 삼성바이오로직스 31건, 에스티팜 4건, SK바이오사이언스 1건.

### 확인

- 변경 전 통합본 재생성 결과가 커밋된 파일과 같음을 먼저 확인했다(줄바꿈 외 차이 없음).
- 변경 후 한국어 출처 4종(제공·팀원수집·기업명검색·CDMO검색)의 건수·키워드 집계·근거 분포가 모두 이전과 같다.
- `python db/build_db.py` 재빌드 성공: 뉴스 9,216건(영어 797건).

---

## 남은 작업과 유의점

| 항목 | 내용 |
|---|---|
| 번역 | 영어 기사의 `title_ko` 를 채우고 대시보드에 한국어로 표시 |
| 영어 분류 검수 | 영어 규칙의 `Europe`·`deal` 등 넓은 표현으로 지정학·수주가 과다 분류될 수 있다. 표본 검수 필요 |
| 국내·해외 중복 | 언어가 달라 같은 사건이 국내·해외 기사로 각각 남는다 |
| 다른 이슈의 글로벌 범위 | 해외 보강은 지정학 이슈만 했다. 모달리티·수주 등은 여전히 국내 언론 중심 |
| `main` 반영 | 해외 뉴스 보강(#4)은 `develop` 에만 있다. 출시 시 `release/*` 브랜치로 `main` 에 반영 |
| 대시보드 | 미구현. `docs/대시보드_사용자_핵심질문.md` 의 기능 ①~⑥과 점검표를 기준으로 구현 |

## 재현 순서

README의 "실행 순서 — 통합 DB 구축"을 따른다. 해외 뉴스 관련 단계만 다시 실행하려면:

```bash
python collect/collect_news_global.py
```

```bash
python analysis/build_cdmo_news.py
```

```bash
python db/build_db.py
```
