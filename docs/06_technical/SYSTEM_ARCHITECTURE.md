# 시스템 구조

> **상태:** 작성 완료 — 계층과 구성 요소별 책임·디렉터리, 저장소, 대시보드 내부 구조, 실시간 호출을 하지 않는 구조, 실행 환경·비밀 정보 · **최종 갱신:** 2026-11-18
> **원본:** `README.md` 디렉터리·실행 순서, `docs/data_schema.md` 1절, 코드 (`collect/`, `analysis/`, `db/`, `rag/`, `dashboard/`). 과제 가이드 5·6절 원문은 저장소에 없어 확인하지 못함 — 이 문서의 "과제 요구"는 PRD N1·N2와 제출 전 점검표 기준
> **관련 문서:** [masterplan](../masterplan.md) · [DATA_PIPELINE](../03_data/DATA_PIPELINE.md) (단계별 입출력·실행 순서) · [DATABASE_SCHEMA](DATABASE_SCHEMA.md) · [API_SPECIFICATION](API_SPECIFICATION.md) · [TECH_STACK](TECH_STACK.md)

---

## 1. 계층

```
┌──────────────┐   ┌────────────────┐   ┌──────────┐   ┌──────────────────────┐   ┌──────────────┐
│ ① 수집        │ → │ ② 통합·재분류    │ → │ ③ 적재    │ → │ ④ 분석·AI 사전 생성    │ → │ ⑤ 대시보드     │
│ collect/     │   │ analysis/       │   │ db/      │   │ analysis/, rag/       │   │ dashboard/   │
│ 외부 API 호출  │   │ build_cdmo_news │   │ build_db │   │ LLM·임베딩 호출(유료)   │   │ 조회만        │
└──────┬───────┘   └───────┬────────┘   └────┬─────┘   └──────────┬───────────┘   └──────┬───────┘
       ▼                   ▼                 ▼                    ▼                      ▲
  data/raw/          03_CDMO_news_3y/   data/db/*.sqlite   data/processed/*,          DB + 파일 읽기
  (git)              (git)              (git 제외)          chroma_db/ (git 제외)      + Q&A만 질의 시 호출
```

- **한 방향 흐름:** 각 계층은 앞 계층이 저장한 **파일만** 읽는다. 뒤 계층이 앞 계층의 API를 부르지 않으므로, 수집을 다시 하지 않고도 ②부터 다시 돌릴 수 있다.
- **비용이 드는 곳은 ①(호출 제한)과 ④(LLM·임베딩)뿐**이다. 둘 다 결과를 파일로 남기고, 이미 처리한 것은 건너뛰는 이어받기 방식이다.
- 단계별 스크립트·입출력·실행 순서는 [DATA_PIPELINE](../03_data/DATA_PIPELINE.md)에 있다. 이 문서는 구성 요소의 책임과 경계를 다룬다.

## 2. 구성 요소와 책임

| 구성 요소 | 디렉터리 | 책임 | 하지 않는 것 |
|---|---|---|---|
| 수집 | `collect/` (`config.py` 공통 설정) | DART OpenAPI·구글 뉴스 RSS 호출, **응답 원본 그대로 저장**, 이어받기 | 가공·분류 (원본만 남긴다) |
| 통합·재분류 | `analysis/build_cdmo_news.py` | 뉴스 5종 통합, 출처 간 겹침 제거, CDMO 키워드 규칙 분류 | API 호출 |
| 적재 | `db/` (`schema.sql`, `build_db.py`) | 통합본·공시 목록·원문 zip → SQLite, 텍스트 정제, 공시 분류, 중복 표시, 번역 파일 재적재 | API 호출, LLM |
| 분석 (규칙) | `analysis/` (`eda.py`, `match_news_disclosure.py`, `extract_contract_amounts.py`, `build_summary_cards.py`, `disclosure_weights.py`) | 기사량·급증, 뉴스-공시 매칭, 계약 금액, 요약 카드, 기업 선정 점수 | API 호출 |
| AI 사전 생성 | `analysis/*_prompt.py` + `label_sentiment.py`, `extract_issues.py`, `group_issues.py`, `tag_modality.py`, `translate_titles.py` | 감성·이슈·이슈 묶기·모달리티·번역을 미리 만들어 CSV로 저장 | 화면 표시 |
| 공시 RAG | `rag/` (`build_index.py`, `qa.py`, `eval_rag.py`) | 공시 원문 청킹·임베딩·색인, 질의응답(검색 → 답변 → 인용 검증), 평가 | 색인 밖 문서 답변 (근거 없으면 거절) |
| 검수·평가 | `analysis/sample_*.py`, `eval_*.py`, `data/eval/` | 표본 추출, 사람·Claude 판정 기록, 정확도 집계 | — |
| 대시보드 | `dashboard/` (3절) | DB와 파일 조회, 필터·차트·목록, 공시 Q&A 화면 | LLM 분류·번역 실행 |
| 점검 | `tests/check_dashboard_filters.py` | 7개 화면 × 필터 조합 자동 실행 | API 호출 |

## 3. 대시보드 내부 구조

```
dashboard/app.py                 페이지 설정 → 사이드바(필터) → st.navigation(7개 화면) → 실행
├── core/
│   ├── filters.py               기간·기업·카테고리 위젯, st.session_state["filters"], 필터 상태 줄
│   ├── data.py                  DB(읽기 전용)·CSV 읽기(st.cache_data), 필터 규칙(filter_news, filter_links …)
│   ├── ui.py                    공통 부품(header, kpis, pending, empty, limits, news_line …)
│   └── theme.py                 색 토큰, Plotly 스타일, 모든 차트를 그리는 show()
└── views/                       화면 7개 — 각자 render() 하나
    s0_summary  s1_trend  s2_policy  s3_tech  s4_compare  s5_linkage  s6_qa
```

| 원칙 | 구현 |
|---|---|
| 화면은 필터만 읽는다 | 위젯 값은 콜백에서 `filters` 로 옮기고, 화면 코드는 `st.session_state["filters"]` 만 읽는다. 화면을 옮겨도 필터가 유지된다 |
| 데이터 읽기는 한 곳 | `core/data.py` 가 DB·CSV를 읽고 캐시한다. 필터 규칙(UI_SPECIFICATION 4-2절)도 여기 있어 화면마다 같은 규칙을 쓴다 |
| 시각 값은 두 곳 | `.streamlit/config.toml`(테마)과 `core/theme.py`(차트 색·스타일)에만 둔다. 화면 코드는 색을 직접 쓰지 않는다 |
| 화면 간 이동 | `st.switch_page` + 세션 상태 (카드 → 상세 화면 L1, 공시 → Q&A L8, 요약 검색창 → Q&A) |
| 실패를 화면 안에 가둔다 | 파일·DB가 없으면 그 화면만 "데이터 오류" 안내, Q&A 설정 문제는 S6만 "설정 확인" 안내. 다른 화면은 계속 동작 |

DB는 `file:...?mode=ro` 로 **읽기 전용** 연결한다. 대시보드가 DB를 바꾸는 일은 없다.

## 4. 저장소

| 저장소 | 위치 | 내용 | git | 다시 만드는 법 |
|---|---|---|---|---|
| 원본 파일 | `data/raw/`, `02_BIO_news_3y/` | API 응답 원본, 제공·팀원 뉴스 | 올림 | (재수집은 결과가 달라질 수 있어 하지 않음) |
| 통합본 | `03_CDMO_news_3y/` | CDMO 재분류 뉴스 CSV | 올림 | `build_cdmo_news.py` |
| 관계형 DB | `data/db/bio_cdmo.sqlite` (SQLite) | 뉴스·공시·원문·정제 텍스트·키워드·기업 매핑 | **제외** (약 107MB) | `python db/build_db.py` (API 호출 없음) |
| 분석·AI 결과 | `data/processed/` | LLM 결과·매칭·금액·EDA·요약 카드 (CSV·JSON, URL·접수번호 키) | 올림 | 해당 스크립트 (LLM 단계는 유료) |
| 벡터 DB | `chroma_db/` (Chroma, 약 692MB) | 공시 원문 청크 36,548개 임베딩 | **제외** | `python rag/build_index.py` (약 $0.58) 또는 팀원에게 폴더를 받음 |
| 검수·평가 | `data/eval/` | 표본, 판정, 평가 결과 | 올림 | — |

LLM 결과를 DB 테이블이 아니라 파일에 두는 이유와 키 연결은 [DATABASE_SCHEMA](DATABASE_SCHEMA.md) 5·6절.

## 5. 대시보드가 실시간으로 API·LLM을 부르지 않는 구조

과제 제출 전 점검 "대시보드가 API를 직접 호출하지 않고 저장된 결과를 조회한다"와 PRD N1·N2를 지키는 방법이다.

| 화면 결과 | 만드는 곳 (미리) | 대시보드가 하는 일 |
|---|---|---|
| 기사량·급증·대표 기사 | `eda.py` → `eda_spikes.csv`, DB 집계 | 읽고 거르기 |
| 감성·판단 이유·이슈 이름·모달리티 | LLM 단계 → CSV | URL로 붙이기 |
| 영어 제목 번역 | `translate_titles.py` → `title_ko.csv` → DB `news.title_ko` | 읽기 (번역 호출 없음) |
| 뉴스-공시 연결, 계약 금액 | 규칙·정규식 → CSV | 읽기 |
| 요약 결론·카드 | `build_summary_cards.py` → JSON | 읽고 필터로 거르기 |
| **공시 Q&A 답변** | (미리 만들 수 없음 — 사용자 질문) | **질문할 때만 임베딩 1회 + 답변 1회 호출** (예외, NEWS_DISCLOSURE_MATCHING D4) |

Q&A 예외의 안전장치: 답변은 검색된 공시 발췌로만 만들고, 인용한 접수번호와 구절이 실제 발췌에 있는지 검증해 없으면 거절한다(`rag/qa.py` `verify`). 결과를 캐시하지 않고, 이전 질문을 다시 볼 때는 재호출하지 않는다.

## 6. 실행 환경

| 항목 | 현재 | 비고 |
|---|---|---|
| 실행 위치 | **로컬** (`streamlit run dashboard/app.py`, 저장소 루트에서) | 배포하지 않았다 |
| 필요한 것 | Python 3.12 가상환경, `data/db/bio_cdmo.sqlite`, (Q&A) `chroma_db/`·`OPENAI_API_KEY` | DB·색인은 git에 없어 각자 만들거나 받는다 |
| 배포 시 고려 | DB(약 107MB)와 `chroma_db/`(약 692MB)를 배포 환경에 올리거나 시작할 때 만들어야 한다. 키는 Streamlit `secrets.toml`(git 제외 등록됨)로 넣는다 | 미검토 — 발표는 로컬 실행 전제 |
| 성능 | 화면마다 첫 로딩 약 0.5~1초 (2026-11-18 측정, 캐시 전) | [TEST_PLAN](../07_project-management/TEST_PLAN.md) |

## 7. 비밀 정보

| 키 | 쓰는 곳 | 보관 |
|---|---|---|
| `DART_OPEN_API` | `collect/` DART 호출 | `.env` (git 제외). `collect/config.py` 가 읽고 출력하지 않는다 |
| `OPENAI_API_KEY` | `analysis/` LLM 단계, `rag/`, 대시보드 S6 | 환경변수 또는 `.env`. 없으면 S6만 "설정 확인" 안내 |

- `.env.example` 은 키 이름만 있고 값은 비어 있다. 저장소 전체와 커밋 기록에 키 패턴이 없음을 확인했다 (2026-11-18, [TEST_PLAN](../07_project-management/TEST_PLAN.md) 4절).
- 발표자료에 키가 없는지는 자료를 만든 뒤 다시 확인한다.
