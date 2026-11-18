# 기술 스택

> **상태:** 작성 완료 — 영역별 도구와 실제 사용 여부, 선택 이유와 대안, LLM·임베딩 모델, Python 버전·설치 · **최종 갱신:** 2026-11-18
> **원본:** `README.md` 기술 스택·준비, `requirements.txt`, 각 스크립트의 import·설정 상수 (과제 가이드의 "핵심 기술" 원문은 저장소에 없어 확인하지 못함)
> **관련 문서:** [masterplan](../masterplan.md) · [SYSTEM_ARCHITECTURE](SYSTEM_ARCHITECTURE.md) · [API_SPECIFICATION](API_SPECIFICATION.md) · [DATA_PIPELINE](../03_data/DATA_PIPELINE.md) · [UI_SPECIFICATION](../05_design/UI_SPECIFICATION.md)

---

## 1. 실행 환경

| 항목 | 값 | 비고 |
|---|---|---|
| Python | **3.12** (`.venv` 실측 3.12.0) | `requirements.txt` 가 3.12 기준으로 버전을 고정. README는 "3.10 이상"으로 적었으나 3.10·3.11에서 설치·실행을 확인하지 않았다 (미확인) |
| 가상환경 | `python -m venv .venv` → `pip install -r requirements.txt` | README "준비" |
| 비밀 정보 | `.env` 의 `DART_OPEN_API`, `OPENAI_API_KEY` (`.env.example` 은 빈 값, `.env` 는 git 제외) | 코드는 키를 변수로만 읽고 출력하지 않는다 |
| 운영체제 | Windows 11에서 개발·확인. 경로는 `pathlib` 로 다뤄 OS에 묶이지 않게 했다 | macOS·Linux 실행은 미확인 |

## 2. 영역별 도구 — 실제로 쓰는 것

2026-11-18 기준, 코드(`collect/`, `analysis/`, `db/`, `rag/`, `dashboard/`, `tests/`)의 import로 확인했다.

| 영역 | 도구 (버전) | 쓰는 곳 | 선택 이유 |
|---|---|---|---|
| 수집 | Python 표준 라이브러리 (`urllib`, `xml.etree`, `json`, `zipfile`) | `collect/` | DART·구글 뉴스 RSS는 단순 GET이라 외부 패키지가 필요 없다. 응답 원본을 그대로 저장해 재현성을 확보 |
| 저장 | **SQLite** (표준 `sqlite3`) | `db/build_db.py`, 대시보드 | 파일 하나로 팀원이 같은 DB를 다시 만들 수 있고 서버가 필요 없다. 데이터 규모(뉴스 9,216 · 공시 867)에 충분 |
| 처리 | `pandas` 3.1.1, `numpy` 2.5.4 | `analysis/`, `dashboard/core/data.py` | 집계·조인·필터 |
| EDA 차트 | `matplotlib` 3.11.2 | `analysis/eda.py`, `issue_trend.py` | 리포트용 정적 그림 (`docs/figures/eda/`) |
| 대시보드 차트 | `plotly` 7.1.0 | `dashboard/views/` | 호버·점 선택(`on_select`)이 되는 상호작용 차트. Streamlit 테마와 연동 |
| 대시보드 | `streamlit` 1.67.0 | `dashboard/` | 과제 산출물 형식. `st.navigation` 멀티 페이지, 사이드바 필터, `AppTest` 로 자동 점검 |
| LLM | `openai` 3.51.0 — Chat Completions, 구조화 출력(`response_format` json_schema) | 감성·이슈·이슈 묶기·모달리티·번역, RAG 답변 | 5절 |
| 임베딩·벡터 DB | `openai` 임베딩 + `chromadb` 1.5.9 (로컬 `PersistentClient`, cosine) | `rag/build_index.py`, `rag/qa.py` | 서버 없이 폴더(`chroma_db/`) 하나로 동작. 공시 864건 규모에 충분 |
| RAG 체인 | `langchain-core` (`RunnableLambda`) | `rag/qa.py` | 과제 요구 "LangChain 기반 질의응답". 검색 → 생성 → 검증 단계를 체인으로 잇는 데만 쓴다 |
| 청킹 | `langchain-text-splitters` 1.1.3 (`RecursiveCharacterTextSplitter`) | `rag/build_index.py` | 문단·줄 경계를 우선해 글자 수 기준 분할(1,000자, 겹침 150자) |
| 테스트 | Streamlit `AppTest` (`streamlit.testing.v1`) | `tests/check_dashboard_filters.py` | 별도 테스트 패키지(pytest) 없이 화면을 실행해 점검 |

## 3. 설치돼 있지만 코드에서 쓰지 않는 것

`requirements.txt` 에 있으나 2026-11-18 기준 어떤 스크립트도 import하지 않는다. 초기 설계(README 기술 스택 표)에서 후보로 넣었다가 더 단순한 방법을 택한 것들이다.

| 패키지 | 처음 의도 | 실제로 한 방법 |
|---|---|---|
| `requests`, `feedparser`, `beautifulsoup4`, `lxml`, `OpenDartReader`, `python-dotenv` | 수집·파싱·키 읽기 | 표준 라이브러리(`urllib`, `xml.etree`, 정규식)와 `collect/config.py` 의 `.env` 읽기 함수 |
| `SQLAlchemy` | DB 접근 | 표준 `sqlite3` |
| `openpyxl` | 엑셀 입출력 | CSV(UTF-8 BOM)로 통일 |
| `seaborn` | EDA 차트 | `matplotlib` 만 사용 |
| `statsmodels`, `ruptures`, `scikit-learn` | 시계열·변화점 탐지 | 급증 판정은 직접 쓴 규칙(주별 z ≥ 3, 직전 26주 중앙값 기준 — `analysis/eda.py`) |
| `kiwipiepy` | 한국어 형태소 분석 | 급증 상위어는 제목에서 한글 2자 이상·영문 3자 이상 토큰을 정규식으로 뽑아 불용어를 빼고 센다 (`analysis/eda.py` `top_terms()`) |
| `anthropic`, `langchain-anthropic` | Claude API | OpenAI로 통일 (5절) |
| `langchain-chroma` | LangChain–Chroma 연동 | `chromadb` 를 직접 호출 |
| `jupyter`, `ipykernel` | 노트북 탐색 | 저장소에 노트북 없음 |

이 패키지들을 `requirements.txt` 에서 뺄지는 팀 결정이다. 빼면 설치가 빨라지고 의존성 충돌이 줄지만, 노트북 등 개인 작업에 쓰는 팀원이 있을 수 있다.

## 4. 외부 데이터 원천

| 원천 | 방식 | 인증 |
|---|---|---|
| DART OpenAPI | `corpCode.xml`, `list.json`, `document.xml`, `fnlttSinglAcnt.json` | `DART_OPEN_API` 키 |
| 구글 뉴스 RSS | 검색 RSS (한국판·미국판) | 없음 |
| 제공 뉴스 | `02_BIO_news_3y/` CSV (과제 제공) | — |

호출 방식과 제한은 [API_SPECIFICATION](API_SPECIFICATION.md) 1절.

## 5. LLM·임베딩 모델

| 용도 | 모델 | 설정 | 비용 (가격표 기준, 콘솔 미확인) |
|---|---|---|---|
| 감성 분류 (`sentiment-v3`) | `gpt-6-luna` | effort low, 동시 8, 기사 1건 1회 | 입력 $0.10 · 출력 $0.50 / 100만 토큰 (코드의 `PRICE` 표) |
| 이슈 추출 (`issue-v1`) | `gpt-6-luna` | effort low, 동시 8 | 같음 |
| 이슈 이름 묶기 (`issue-group-v1`) | `gpt-6-luna` | effort **medium**, 이름 120개씩 차례로 | 같음 |
| 모달리티 태깅 (`modality-v2`) | `gpt-6-luna` | effort low, 동시 8 | 같음 |
| 영어 제목 번역 (`translate-v3`) | `gpt-6-luna` | effort low, 동시 8 | 전체 약 $0.18 (dry-run 추정) |
| RAG 답변 | `gpt-6-luna` | effort low, 최대 4,096 토큰, 구조화 출력 | 질문 1회 1센트 미만 |
| RAG 임베딩 | `text-embedding-3-small` | 1,000자 청크 64개씩 | $0.02 / 100만 토큰, 전체 색인 약 $0.58 |

**선택 이유와 대안**
- **한 모델로 통일:** 모든 LLM 단계가 같은 모델을 써서 비용 추정·키 관리·결과 비교가 단순하다. 분류·번역은 짧은 입력이라 작은 모델로 충분했고(감성 표본 정확도 85.0%), 부족하면 effort를 올리는 방식으로 조정한다.
- **Claude(Anthropic) 대신 OpenAI:** 팀 키 발급 상황에 따라 OpenAI로 정했다(README "LLM 키" 변경 이력). `anthropic` 패키지는 남아 있지만 쓰지 않는다.
- **임베딩 `small` vs `large`:** `large`($0.13)는 비용이 6.5배다. 공시 표·숫자 검색에서 `small` 로 검색 정확도 12/14를 얻어 바꾸지 않았다 ([AI_EVALUATION](../04_ai/AI_EVALUATION.md) 6절).
- **벡터 DB `chromadb` vs FAISS·pgvector:** 메타데이터(기업·접수일·분류) 필터 검색이 필요하고 서버를 띄우지 않으려고 `chromadb` 로컬 모드를 택했다.

## 6. 버전과 호환성 메모

- **Streamlit 1.67.0** 의 기능을 전제로 화면을 만들었다: `st.navigation`, `st.Page`(함수 페이지, `url_path`), `st.segmented_control`, `st.container(horizontal=True)`, `width="stretch"`, `st.metric(border=True)`, 마크다운 배지(`:blue-badge[…]`), `st.plotly_chart(on_select=…)`, `st.dataframe(on_select=…)`, 라이트·다크 테마 설정(`[theme.light]`·`[theme.dark]`). 낮은 버전에서는 화면이 열리지 않을 수 있다 ([UI_SPECIFICATION](../05_design/UI_SPECIFICATION.md) 2-6절).
- **pandas 3.x** 문자열 열은 Arrow 문자열 형식이다. 빈 결과에서 `map` 결과가 object 형이 되어 불리언 거르기가 열 선택으로 읽힌 버그가 있었다 (`filter_links`, [TEST_PLAN](../07_project-management/TEST_PLAN.md) 2절에서 고침).
- **chromadb** 는 한 번에 많은 ID를 조회하면 "too many SQL variables" 오류가 난다. 색인 전체를 확인할 때는 나눠 읽는다.
