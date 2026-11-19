# 마일스톤

> **상태:** 작성 완료 — Day 1~7 완료 조건과 실제 완료일(2026-11-19 기준 Day 6까지), 제출물 상태, `main` 반영 기록 · **최종 갱신:** 2026-11-19
> **원본:** 과제 가이드(`docs/중간프로젝트_가이드_뉴스공시_산업이슈_대시보드.md`) 3·4·7절, [PRODUCT_ROADMAP](../02_product-requirements/PRODUCT_ROADMAP.md) 1절, 팀원 기록 파일, git 기록
> **관련 문서:** [masterplan](../masterplan.md) · [PRODUCT_ROADMAP](../02_product-requirements/PRODUCT_ROADMAP.md) · [TASKS](TASKS.md) · [DECISIONS](DECISIONS.md) · [TEST_PLAN](TEST_PLAN.md)

---

- 과제 기간은 7일이다(가이드 머리말). 팀은 2026-11-13(금)에 시작했고, 기록은 11-13(금)·11-16(월)·11-17(화)·11-18(수) 네 작업일에 있다. **Day 번호별 계획 날짜는 따로 정하지 않았다** — 아래 "완료일"은 종료 조건을 처음 충족한 날이다.
- 단계별 상세 현황은 [PRODUCT_ROADMAP](../02_product-requirements/PRODUCT_ROADMAP.md) 1절, 작업 단위는 [TASKS](TASKS.md).

## 1. 단계별 완료 조건과 실제 완료

| 단계 | 완료 조건 (가이드 4절) | 완료일 | 상태 | 근거 |
|---|---|---|---|---|
| **Day 1** 기획 및 환경 구축 | 스키마와 역할 분담이 확정되어 있다 | 11-13 | ✅ (역할 분담은 문서화하지 않음 — [TASKS](TASKS.md) 2절에 실제 분담을 정리) | 산업·5개사 선정, 페르소나·핵심 질문, `db/schema.sql`, 저장소·`CLAUDE.md` 규칙 |
| **Day 2** 공시 수집 및 데이터 적재 | 뉴스와 공시가 DB에 적재되어 있다 | 11-13 | ✅ | DART 공시 867건·원문 864건, 뉴스 9,216건 적재 ([DATABASE_SCHEMA](../06_technical/DATABASE_SCHEMA.md) 4절) |
| **Day 3** 전처리 및 EDA | 이슈 급증 시점을 근거와 함께 제시할 수 있다 | 11-16 | ✅ | 정규표현식 정제(`news_clean`), 중복 표시, 급증 시점 67건과 대표 기사·공시 (`docs/eda_report.md`) |
| **Day 4** AI 기반 이슈 추출 | 분류 결과와 검수 결과가 존재한다 | 11-17 | ✅ | 감성 4,727건 + 표본 180건 검수(정확도 85.0%). 이슈 추출 4,727건과 이슈 추출 표본 30건 검수(층 가중 이름 98.7%·유형 97.4%·묶기 98.7%, 2026-11-18), 모달리티 태깅(11-18, 표본 80건 검수), 영어 번역(11-18, 품질 검수 전) |
| **Day 5** RAG 공시 Q&A 구축 | 근거 공시와 함께 답변한다 | 11-17 | ✅ | 청크 36,548개 색인, `rag/qa.py`, 평가 20문항(검색 12/14, 거절 6/6). 뉴스-공시 매칭 7,135쌍과 표본 50쌍 검수(11-18) |
| **Day 6** 대시보드 구현 | 필터가 모든 차트에 반영된다 | 11-18 | ✅ | S0~S6 7개 화면, 7화면 × 필터 17조합 자동 점검 오류 0 ([TEST_PLAN](TEST_PLAN.md) 2절) |
| **Day 7** 고도화 및 발표 | 처음 보는 사람이 결론을 이해할 수 있다 | — | 🔶 진행 중 | S0 결론 문장·카드(11-18), 결론 문구 실무 표현으로 정리(11-19 "지금 CDMO 시장 현황은 우호적"), LLM 한계 회고 초안, 리포트 초안(11-19 `docs/REPORT.md`·PDF). 스토리텔링 구성·발표는 남음 |

가이드 4절대로 Day 4와 Day 5를 나눠 병행했다 (11-17에 감성·이슈 추출과 RAG 색인·질의응답이 같은 날 진행).

## 2. 기본 목표 (가이드 3-1절)

| 목표 | 상태 | 근거 |
|---|---|---|
| 대상 산업과 분석 대상 기업을 선정하고, 대시보드의 사용자와 핵심 질문을 정의하였다 | ✅ | [DART_DATA_SPEC](../03_data/DART_DATA_SPEC.md) 1절, [PERSONA](../01_product-strategy/PERSONA.md), [PRODUCT_VISION](../01_product-strategy/PRODUCT_VISION.md) |
| DART 공시를 API로 수집하고 뉴스와 함께 DB에 저장하였다 | ✅ | [DATA_PIPELINE](../03_data/DATA_PIPELINE.md), [DATABASE_SCHEMA](../06_technical/DATABASE_SCHEMA.md) |
| 뉴스·공시 EDA를 수행하였다 (기사량·공시 건수 추이, 이슈 급증 시점) | ✅ | `docs/eda_report.md`, 대시보드 S1 |
| LLM으로 감성 분류 및 핵심 이슈 추출을 수행하고, 결과의 정확도를 표본 검수로 확인하였다 | ✅ | 감성 분류 표본 180건 85.0%, 이슈 추출 표본 30건(층 가중 이름 98.7%·유형 97.4%·묶기 98.7%, 판정 `dtt-dtdt`) ([AI_EVALUATION](../04_ai/AI_EVALUATION.md) 4·9절) |
| 공시 문서 기반 RAG 질의응답 기능을 구현하고, 답변에 근거 공시를 표시하였다 | ✅ | [AI_EVALUATION](../04_ai/AI_EVALUATION.md) 6절, 대시보드 S6 |
| Streamlit 대시보드에 이슈 분석 화면과 공시 Q&A를 통합하였다 | ✅ | S0~S6 |
| 대시보드 상단에 의사결정 관점의 결론이 제시되어 있다 | ✅ | S0 결론 문장 (AC-01, 1366×768에서 스크롤 없이 보임) |

심화 확장(가이드 3-2절: 주가 연계, 본문 보강, 자동 요약, 검색 고도화)은 하지 않았다. 뉴스 본문 보강은 시도했다가 되돌렸다 ([DECISIONS](DECISIONS.md) D-09).

## 3. 제출물 (가이드 7절)

| 제출물 | 상태 | 비고 |
|---|---|---|
| 1. 코드 저장소 — 계층별 디렉터리, README에 실행 순서 | ✅ | `collect/` → `analysis/` → `db/` → `rag/` → `dashboard/`. README 실행 순서는 DB 구축·RAG·대시보드까지. LLM 분석 단계 순서는 [DATA_PIPELINE](../03_data/DATA_PIPELINE.md) 3절에만 있음 |
| 2. 동작하는 Streamlit 대시보드 — 로컬 실행 또는 배포 URL | ✅ 로컬 | 배포는 하지 않음. 실행 PC에 DB와 `chroma_db/` 가 필요 ([SYSTEM_ARCHITECTURE](../06_technical/SYSTEM_ARCHITECTURE.md) 6절) |
| 3. 리포트 (PDF) | 🔶 초안 — [REPORT.md](../REPORT.md), `docs/REPORT.pdf` (A4 13쪽, 11-19), 팀 검토 전 | 구성(가이드 7절): 분석 목적 · 데이터 · EDA · AI 이슈 분석 · 공시 Q&A · 대시보드 · 회고 |
| 4. 발표 (PPT) | ⬜ | 발표자료에 키가 없는지 만든 뒤 확인 ([TEST_PLAN](TEST_PLAN.md) 4절) |

리포트 각 장의 재료가 있는 문서: 분석 목적 — 01 섹션 / 데이터 — 03 섹션, DATABASE_SCHEMA / EDA — `eda_report.md` / AI 이슈 분석 — AI_CLASSIFICATION, AI_EVALUATION / 공시 Q&A — NEWS_DISCLOSURE_MATCHING 4절, AI_EVALUATION 6절 / 대시보드 — 05 섹션, S0 결론 / 회고 — DECISIONS, 팀원 기록 파일.

## 4. 제출 전 점검 (가이드 8절)

8개 항목 중 6개 통과, 2개 남음(발표자료 키 확인, 두 사람 모두 설계 판단 설명). 항목별 근거는 [TEST_PLAN](TEST_PLAN.md) 4절.

## 5. `main` 반영 기록

| 기간 | 방식 | 주요 반영 |
|---|---|---|
| 11-13 | Gitflow (작업 브랜치 → `develop` → `release/0.1.0` → `main`, PR #1~#8) | 프로젝트 설정·README(PR #1), 페르소나·핵심 질문(PR #2), `develop` 반영(PR #3), 해외 뉴스 보강(PR #4), `release/0.1.0`(PR #6), 문서 01~07 재편(PR #8). 이후 `main` 단일 브랜치로 전환 |
| 11-16 ~ 11-17 | `main` + 작업 브랜치 PR (#9~#19) | 감성 분류 라벨링·검수(#9~#14), README OpenAI 키(#15), 공시 RAG(#16), 문서 상태(#17), 이슈 추출 설계(#18), 이슈 키워드 길이 수정·매칭 표본(#19) |
| 11-17 오후 ~ | 작업 브랜치 → `main` 직접 병합 (PR 없음, [DECISIONS](DECISIONS.md) D-35) | 매칭 판정, RAG 반환값, 대시보드 S0~S6, 통합 점검, 모달리티·번역·계약 금액, 03·06 문서 |

브랜치 이름과 커밋은 git 기록(`git log --oneline main`)이 원본이다. `release` 브랜치와 태그는 쓰지 않는다.
