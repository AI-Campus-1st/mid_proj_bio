# Masterplan — 바이오 CDMO 산업 이슈 대시보드

> **최종 갱신:** 2026-11-13
> 이 문서는 프로젝트 문서 전체의 지도이다. 무엇을 만들고, 어디까지 왔고, 어떤 문서가 어디에 있는지 여기서 시작한다.

---

## 1. 프로젝트 한눈에 보기

| 항목 | 내용 |
|---|---|
| 제품 | 뉴스·DART 공시 기반 바이오 CDMO 산업 이슈 대시보드 (Streamlit) |
| 사용자 | 바이오 CDMO 기업의 사업전략·기획 담당자 |
| Core Question | 글로벌 바이오 CDMO 산업에서 지금 어떤 변화가 발생하고 있으며, 이러한 변화가 우리 기업의 사업 기회와 경쟁력에 어떤 영향을 미치는가? |
| 대상 기업 | 삼성바이오로직스, SK바이오사이언스, 프레스티지바이오로직스, 에스티팜, 바이넥스 |
| 데이터 | 2023-10-19 ~ 2026-10-19 · 뉴스 9,216건 · 공시 867건 |
| 최종 산출물 | Streamlit 대시보드(이슈 분석 + 공시 Q&A), PDF 리포트, PPT 발표 |
| 과제 원문 | `중간프로젝트_가이드_뉴스공시_산업이슈_대시보드.md` (저장소 루트) |

자세한 내용은 [PRODUCT_BRIEF](01_product-strategy/PRODUCT_BRIEF.md).

## 2. 진행 현황

| 단계 | 상태 | 근거 문서 |
|---|---|---|
| Day 1 기획·환경 | 완료 | 01·02 섹션 |
| Day 2 공시 수집·적재 | 완료 | `docs/data_schema.md` |
| Day 3 전처리·EDA | 진행 중 (중복 처리·재분류 완료, EDA 미착수) | `docs/news_sort.md` |
| Day 4 AI 이슈 추출 | 미착수 | 04_ai |
| Day 5 RAG 공시 Q&A | 미착수 | 04_ai |
| Day 6 대시보드 | 미착수 | 05_design, 06_technical |
| Day 7 고도화·발표 | 미착수 | 07_project-management |

상세 일정과 우선순위는 [PRODUCT_ROADMAP](02_product-requirements/PRODUCT_ROADMAP.md).

---

## 3. 문서 구조

### 3-1. 폴더 구성 원칙

문서는 **제품을 만드는 순서**대로 7개 섹션으로 나눈다. 앞 섹션이 "왜·무엇"을, 뒤 섹션이 "어떻게·언제"를 다룬다. 뒤 섹션 문서는 앞 섹션 문서를 근거로 쓰고, 앞 섹션이 바뀌면 뒤 섹션을 함께 갱신한다.

```
docs/
├── masterplan.md                 ← 이 문서. 전체 지도
├── 01_product-strategy/          왜 만드는가 — 문제, 사용자, 비전
├── 02_product-requirements/      무엇을 만드는가 — 기능, 스토리, 검수 기준, 일정
├── 03_data/                      어떤 데이터로 — 수집, 분류, 파이프라인
├── 04_ai/                        AI가 맡는 일 — 분류, 매칭·RAG, 평가
├── 05_design/                    어떻게 보여주는가 — 화면 구조, 흐름, 배치
├── 06_technical/                 어떻게 구현하는가 — 구조, 인터페이스, DB, 기술
└── 07_project-management/        어떻게 진행하는가 — 일정, 작업, 결정, 테스트
```

### 3-2. 문서 목록과 상태

상태: ✅ 작성 완료 · 📝 작성 전(작성 가이드 주석 있음)

| 섹션 | 문서 | 내용 | 상태 |
|---|---|---|---|
| **01 product-strategy** | [PRODUCT_BRIEF](01_product-strategy/PRODUCT_BRIEF.md) | 제품 기획서 — 배경, 산업·기업·데이터 범위, 문제, 제품 구성 | ✅ |
| | [PRODUCT_VISION](01_product-strategy/PRODUCT_VISION.md) | 비전, Core Question, 핵심 질문, 원칙, 목표, 범위 밖 | ✅ |
| | [PERSONA](01_product-strategy/PERSONA.md) | 사용자 정의, 페르소나, Pain Point, 대표 시나리오 | ✅ |
| | [USER_RESEARCH](01_product-strategy/USER_RESEARCH.md) | 니즈 가설, 데이터로 확인한 사실, 검증 계획 (인터뷰 미실시) | ✅ |
| **02 product-requirements** | [PRD](02_product-requirements/PRD.md) | 기능 F1~F8, 비기능 N1~N7, 데이터 해석 규칙, 한계, 의존 관계 | ✅ |
| | [USER_STORIES](02_product-requirements/USER_STORIES.md) | 에픽 E1~E7, 스토리 US-01~18, 시나리오 연결 | ✅ |
| | [ACCEPTANCE_CRITERIA](02_product-requirements/ACCEPTANCE_CRITERIA.md) | 검수 기준 AC-01~18, 반영·근거·데이터 점검, 제출 전 점검 | ✅ |
| | [PRODUCT_ROADMAP](02_product-requirements/PRODUCT_ROADMAP.md) | Day 1~7 단계와 현황, 완료 작업, 다음 우선순위, 확장 | ✅ |
| **03 data** | [NEWS_DATA_SPEC](03_data/NEWS_DATA_SPEC.md) | 뉴스 출처 5종, 원본·통합본 형식, 품질 | 📝 |
| | [DART_DATA_SPEC](03_data/DART_DATA_SPEC.md) | 기업 선정 근거, DART API, 공시 분류·가중치 | 📝 |
| | [NEWS_CLASSIFICATION](03_data/NEWS_CLASSIFICATION.md) | 카테고리·CDMO 키워드 6개, 규칙 기반 분류, 중복 판정 | 📝 |
| | [DATA_PIPELINE](03_data/DATA_PIPELINE.md) | 수집 → 재분류 → 적재 → AI → 대시보드 흐름, 재실행 | 📝 |
| **04 ai** | [AI_REQUIREMENTS](04_ai/AI_REQUIREMENTS.md) | AI 기능 목록, 처리 범위, 사전 생성·근거 조건 | 📝 |
| | [AI_CLASSIFICATION](04_ai/AI_CLASSIFICATION.md) | 감성·이슈·모달리티·번역 프롬프트와 출력 형식 | 📝 |
| | [NEWS_DISCLOSURE_MATCHING](04_ai/NEWS_DISCLOSURE_MATCHING.md) | 뉴스-공시 매칭 규칙, 공시 RAG 구성 | 📝 |
| | [AI_EVALUATION](04_ai/AI_EVALUATION.md) | 표본 검수 방법과 정확도 기록 (과제 필수) | 📝 |
| **05 design** | [INFORMATION_ARCHITECTURE](05_design/INFORMATION_ARCHITECTURE.md) | 화면 목록·계층·필터 위치 | 📝 |
| | [USER_FLOW](05_design/USER_FLOW.md) | 시나리오별 화면 이동 흐름 | 📝 |
| | [WIREFRAME](05_design/WIREFRAME.md) | 화면별 배치 | 📝 |
| | [UI_SPECIFICATION](05_design/UI_SPECIFICATION.md) | 컴포넌트 동작·표시 규칙 | 📝 |
| **06 technical** | [SYSTEM_ARCHITECTURE](06_technical/SYSTEM_ARCHITECTURE.md) | 계층 구조, 구성 요소, 실행 환경 | 📝 |
| | [API_SPECIFICATION](06_technical/API_SPECIFICATION.md) | 외부 API, 내부 조회 인터페이스, RAG 입출력 | 📝 |
| | [DATABASE_SCHEMA](06_technical/DATABASE_SCHEMA.md) | 통합 DB 스키마 공식 문서 | 📝 |
| | [TECH_STACK](06_technical/TECH_STACK.md) | 도구·버전·선택 이유 | 📝 |
| **07 project-management** | [MILESTONES](07_project-management/MILESTONES.md) | 단계별 완료 조건과 실제 완료일, 릴리스 기록 | 📝 |
| | [TASKS](07_project-management/TASKS.md) | 작업·담당자·상태 | 📝 |
| | [DECISIONS](07_project-management/DECISIONS.md) | 주요 결정과 이유 (ADR) | 📝 |
| | [TEST_PLAN](07_project-management/TEST_PLAN.md) | 검수 방법과 결과 기록 | 📝 |

### 3-3. 문서 간 연결

```
PRODUCT_BRIEF ─┬─ PRODUCT_VISION ── (Core Question, 핵심 질문)
               └─ PERSONA ── USER_RESEARCH
                     │
                     ▼
                    PRD (F1~F8, N1~N7) ──┬── USER_STORIES (US) ── ACCEPTANCE_CRITERIA (AC) ── TEST_PLAN
                     │                   └── PRODUCT_ROADMAP ── MILESTONES ── TASKS
                     ▼
   03_data ──► 04_ai ──► 05_design ──► 06_technical          DECISIONS (모든 섹션의 결정 기록)
```

식별자는 문서 사이에서 그대로 쓴다: 기능 **F1~F8**, 비기능 **N1~N7**, Pain Point **P1~P4**, Supporting Question **SQ1~SQ5**, 스토리 **US-01~18**, 검수 기준 **AC-01~18**.

---

## 4. 문서 작성 규칙

1. **머리말:** 모든 문서 맨 위에 `상태`, `최종 갱신`, `원본`(옮겨 온 기존 자료), `관련 문서` 를 둔다.
2. **작성 전 문서:** `<!-- [작성 가이드] -->` 주석에 목적·넣을 내용·참고 자료·연결 문서가 있다. 작성할 때 이 주석을 따르고, 다 쓰면 주석을 지우고 상태를 바꾼 뒤 3-2 표를 갱신한다.
3. **유실 금지:** 기존 문서에서 내용을 옮길 때는 표·수치·한계·근거를 빠짐없이 옮긴다. 옮긴 뒤 5절 이전 현황을 갱신한다. 원본 파일은 이전이 끝나고 링크를 모두 바꾼 뒤에만 지운다.
4. **사실과 가설 구분:** 확인하지 않은 내용(예: 사용자 인터뷰, 정확도)은 "가설", "미확인", "미검수"로 표시한다.
5. **수치는 출처와 함께:** 건수·비율에는 산출 기준(스크립트, 빌드 일자)을 적는다. 데이터가 바뀌면 수치를 갱신한다.
6. **식별자 유지:** F·US·AC 등 번호는 바꾸지 않는다. 삭제하면 "폐기"로 남기고 새 번호를 붙인다.
7. **작업 기록:** 문서를 바꾼 Claude Code 세션은 `CLAUDE.md` 규칙에 따라 루트의 `<GitHub 닉네임>.md` 에 기록한다.

---

## 5. 기존 문서 이전 현황

기존 문서는 **지우지 않고 그대로 둔다.** 내용은 새 구조로 옮기는 중이며, 옮긴 위치는 아래와 같다.

| 기존 문서 | 옮긴 곳 | 상태 |
|---|---|---|
| `docs/dashboard_questions.md` | 1절 목적·Core Question → PRODUCT_VISION / 2절 사용자·Pain Point → PERSONA / 3절 핵심 질문 → PRODUCT_VISION, PRD / 4절 기능 ①~⑥ → PRD F1~F6 / 5절 시나리오 → PERSONA, USER_STORIES / 6절 점검표 → ACCEPTANCE_CRITERIA / 7절 한계 → PRD 5절, USER_RESEARCH | **이전 완료** — 모든 절이 01·02에 있음. 원본 삭제 여부는 팀 결정 |
| `docs/company_selection.md` | 요약 → PRODUCT_BRIEF 3-2절 / 전체 → 03_data/DART_DATA_SPEC (작성 예정) | 일부 이전 |
| `docs/data_schema.md` | 06_technical/DATABASE_SCHEMA, 03_data/DATA_PIPELINE (작성 예정) | 미이전 |
| `docs/news_sort.md` | 03_data/NEWS_DATA_SPEC, 03_data/NEWS_CLASSIFICATION (작성 예정) | 미이전 |
| `중간프로젝트_가이드_뉴스공시_산업이슈_대시보드.md` (루트) | 과제 요구사항 → PRODUCT_BRIEF, PRODUCT_VISION, PRD, ACCEPTANCE_CRITERIA, PRODUCT_ROADMAP | 과제 원문이므로 루트에 그대로 둔다 |
| `README.md` (루트) | 실행 방법은 README에 유지. 문서 안내는 이 masterplan으로 연결 | 유지 |

---

## 6. 다음 문서 작업 순서

구현 순서와 맞춘다. 앞 문서가 뒤 문서의 근거가 된다.

| 순서 | 문서 | 이유 |
|---|---|---|
| 1 | 03_data 4개 | 기존 `data_schema.md`·`news_sort.md`·`company_selection.md` 를 옮기면 바로 채워진다 |
| 2 | 06_technical/DATABASE_SCHEMA, TECH_STACK | 기존 자료로 채울 수 있고, AI 결과 테이블 설계의 기준이 된다 |
| 3 | 04_ai/AI_REQUIREMENTS → AI_CLASSIFICATION → AI_EVALUATION | Day 4 작업 전에 처리 범위와 검수 방법을 정한다 |
| 4 | 04_ai/NEWS_DISCLOSURE_MATCHING | Day 5 RAG 작업 전 |
| 5 | 05_design 4개 | Day 6 대시보드 구현 전 |
| 6 | 07_project-management 4개 | DECISIONS·TASKS는 지금부터 계속 갱신, TEST_PLAN은 구현 후 |
