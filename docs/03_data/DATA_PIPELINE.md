# 데이터 파이프라인

> **상태:** 작성 완료 — 수집 → 통합·재분류 → 적재 → 분석·AI 사전 생성 → 대시보드 흐름, 단계별 입출력·비용·재실행, git 포함/제외, DB 재빌드 시 보존 · **최종 갱신:** 2026-11-18
> **원본:** `README.md` 실행 순서, `docs/data_schema.md` 1절, `docs/news_sort.md`, `.gitignore`, 각 스크립트 머리말
> **관련 문서:** [masterplan](../masterplan.md) · [DATABASE_SCHEMA](../06_technical/DATABASE_SCHEMA.md) · `NEWS_DATA_SPEC.md` · `DART_DATA_SPEC.md` · `../06_technical/SYSTEM_ARCHITECTURE.md` · [NEWS_DISCLOSURE_MATCHING](../04_ai/NEWS_DISCLOSURE_MATCHING.md) · [AI_CLASSIFICATION](../04_ai/AI_CLASSIFICATION.md)

---

## 1. 흐름

```
① 수집 (collect/)                    ② 통합·재분류 (analysis/)          ③ 적재 (db/)
DART list.json·document.xml  ─┐
구글 뉴스 RSS (기업명·CDMO·해외) ├─→ data/raw/ ──→ build_cdmo_news.py ──→ 03_CDMO_news_3y/ ─┐
제공 뉴스 02_BIO_news_3y/      ─┤                                                         ├─→ build_db.py ──→ data/db/bio_cdmo.sqlite
팀원 수집 data/raw/cdmo_*.csv  ─┘                    DART 공시 목록·원문 zip ──────────────┘        (뉴스·공시·정제 텍스트)
                                                                                                        │
④ 분석·AI 사전 생성 (analysis/, rag/) — DB를 읽어 결과를 파일로 저장 ◀────────────────────────────────┘
   eda.py ─────────────────→ data/processed/eda_*.csv            (규칙·통계, 무료)
   label_sentiment.py ─────→ sentiment_llm.csv                    (LLM, 유료)
   extract_issues.py ──────→ issues_llm.csv ─→ group_issues.py ─→ issue_groups.csv   (LLM, 유료)
   tag_modality.py ────────→ modality_llm.csv                     (LLM, 유료)
   translate_titles.py ────→ title_ko.csv (+ DB news.title_ko)   (LLM, 유료)
   match_news_disclosure.py → news_disclosure_links.csv          (규칙, 무료)
   extract_contract_amounts.py → contract_amounts.csv            (정규식, 무료)
   build_summary_cards.py ─→ summary_cards.json                  (④ 결과 + DB, 무료)
   rag/build_index.py ─────→ chroma_db/                          (임베딩, 유료)
                                                                                                        │
⑤ 대시보드 (dashboard/) — DB와 ④의 파일을 읽기만 한다. 공시 Q&A만 질문할 때 임베딩 1회 + 답변 1회 호출 ◀─┘
```

- **계층을 나눈 이유:** 수집은 외부 API(시간·호출 제한), 적재는 파일 → DB 변환, AI는 비용이 드는 단계라 서로 다시 돌리는 주기가 다르다. 적재(`db/build_db.py`)와 분석은 API를 부르지 않고 저장된 파일만 읽는다.
- **대시보드가 API를 직접 부르지 않는다(PRD N1·N2, 과제 제출 전 점검).** LLM 결과는 ④에서 미리 만들어 둔다. 예외는 공시 Q&A의 질문 시점 호출이다 (NEWS_DISCLOSURE_MATCHING D4).

## 2. 단계별 입력·출력

| 단계 | 스크립트 | 입력 | 출력 | API·비용 |
|---|---|---|---|---|
| ① 기업 코드·후보 14개사 공시 목록 | `collect/collect_dart_list.py` | DART `corpCode.xml`, `list.json` | `data/raw/dart/companies.json`, `list/` | DART (무료, 호출 제한) |
| ① 5개사 기업명 뉴스 | `collect/collect_news.py company`, `collect/collect_news_selected.py` | 구글 뉴스 RSS | `data/raw/news/company_*.jsonl` | 무료 |
| ① 5개사 공시 목록·원문 | `collect/collect_dart_selected.py` | DART `list.json`, `document.xml` | `data/raw/dart/list_selected/`, `document/{접수번호}.zip`, `_missing.json` | DART |
| ① CDMO 키워드 뉴스 | `collect/collect_news_cdmo.py` | 구글 뉴스 RSS (검색어 25개) | `data/raw/news_cdmo/*.jsonl` | 무료 (20~30분) |
| ① 해외(영어) 뉴스 | `collect/collect_news_global.py` | 구글 뉴스 RSS 미국판 (지정학 검색어 4개) | `data/raw/news_global/*_en.jsonl` | 무료 |
| ① (기업 선정용) 재무 | `collect/collect_dart_fin.py` | DART `fnlttSinglAcnt.json` | `data/raw/dart/fin/` | DART |
| ② 뉴스 통합·CDMO 재분류 | `analysis/build_cdmo_news.py` | 제공 뉴스, 팀원 수집 CSV, ①의 jsonl | `03_CDMO_news_3y/*묶음*.csv` | 없음 |
| ③ 통합 DB | `db/build_db.py` (+ `analysis/clean_text.py` 규칙) | 통합본, 공시 목록·원문 zip | `data/db/bio_cdmo.sqlite` | 없음 |
| ④ EDA·급증 시점 | `analysis/eda.py` | DB | `data/processed/eda_*.csv`, `docs/figures/eda/` | 없음 |
| ④ 감성(기회/위험/중립) | `analysis/label_sentiment.py` | DB (대표 CDMO 키워드 있는 중복 제외 기사 4,727건) | `sentiment_llm.csv` | OpenAI `gpt-6-luna` |
| ④ 이슈 추출 | `analysis/extract_issues.py` | 같은 4,727건 | `issues_llm.csv` | OpenAI |
| ④ 이슈 이름 묶기 | `analysis/group_issues.py` | `issues_llm.csv` (이슈 이름 목록만) | `issue_groups.csv` | OpenAI |
| ④ 모달리티 태깅 | `analysis/tag_modality.py` | 같은 4,727건 | `modality_llm.csv` | OpenAI |
| ④ 영어 제목 번역 | `analysis/translate_titles.py` | DB 영어 기사 797건 (제목만) | `title_ko.csv` (+ DB `news.title_ko`) | OpenAI (전체 약 $0.18) |
| ④ 뉴스-공시 매칭 | `analysis/match_news_disclosure.py` | DB | `news_disclosure_links.csv` | 없음 (규칙) |
| ④ 수주 계약 금액 | `analysis/extract_contract_amounts.py` | DB (수주 공시 원문) | `contract_amounts.csv` | 없음 (정규식) |
| ④ 요약 결론·카드 | `analysis/build_summary_cards.py` | DB, 감성·이슈 CSV | `summary_cards.json` | 없음 |
| ④ 공시 RAG 색인 | `rag/build_index.py` | DB 공시 원문 | `chroma_db/` (청크 36,548) | OpenAI 임베딩 (전체 약 $0.58) |
| ④ 평가·검수 표본 | `analysis/sample_sentiment.py`·`sample_match.py`·`sample_modality.py`, `rag/eval_rag.py` | DB, ④ 결과 | `data/eval/*` | `eval_rag.py` 만 OpenAI |
| ⑤ 대시보드 | `dashboard/app.py` | DB, `data/processed/*`, `chroma_db/` | 화면 | 공시 Q&A 질문 때만 OpenAI (1센트 미만/질문) |

LLM 단계의 처리 범위·프롬프트·검수는 [AI_CLASSIFICATION](../04_ai/AI_CLASSIFICATION.md)과 [AI_EVALUATION](../04_ai/AI_EVALUATION.md), 매칭 규칙은 [NEWS_DISCLOSURE_MATCHING](../04_ai/NEWS_DISCLOSURE_MATCHING.md) 3절에 있다.

## 3. 실행 순서

①~③과 공시 RAG, 대시보드 실행 명령은 [README](../../README.md) "실행 순서 — 통합 DB 구축"·"실행 순서 — 공시 RAG"·"실행 — 대시보드"에 있다. README에 따로 적지 않은 ④ 분석 단계의 순서는 다음과 같다. **LLM 단계(★)는 비용이 들므로 먼저 `--dry-run` 으로 건수와 예상 비용을 확인하고 승인받은 뒤 실행한다.**

```
python analysis/eda.py
python analysis/label_sentiment.py --dry-run      ★ 확인 후 --dry-run 없이
python analysis/extract_issues.py --dry-run       ★
python analysis/group_issues.py --dry-run        ★ (extract_issues 다음)
python analysis/tag_modality.py --dry-run         ★
python analysis/translate_titles.py --all --dry-run ★ 영어 제목 번역
python analysis/match_news_disclosure.py
python analysis/extract_contract_amounts.py
python analysis/build_summary_cards.py            (감성·이슈 결과 다음)
python rag/build_index.py --dry-run               ★ 임베딩
```

`analysis/build_summary_cards.py` 는 감성·이슈 결과를 쓰므로 그 뒤에, `group_issues.py` 는 `extract_issues.py` 뒤에 돌린다. 나머지 ④ 단계는 DB만 있으면 서로 독립이다.

## 4. 재실행·이어받기

| 단계 | 끊겼을 때 | 근거 |
|---|---|---|
| ① DART 수집 | 같은 명령을 다시 실행하면 이미 받은 파일을 건너뛴다. 원문이 없는 공시(014)는 `_missing.json` 에 적어 다시 요청하지 않는다 | `collect_dart_list.py`, `collect_dart_selected.py` |
| ① 구글 뉴스 수집 | 끝난 검색 구간을 `_done.txt` 에 적고 다시 실행하면 이어서 받는다 | `collect/collect_news.py` |
| ③ DB 적재 | 임시 파일에 끝까지 쓴 뒤에만 기존 DB를 바꾼다. 실패하면 기존 DB가 남는다 | `db/build_db.py` |
| ④ LLM 단계 | 같은 모델·프롬프트 버전으로 이미 성공한 기사는 건너뛰고, 일정 건수마다 중간 저장한다. 다시 실행하면 남은 기사·실패한 기사만 처리한다 | 각 스크립트 머리말 |
| ④ RAG 색인 | 이미 색인한 청크 ID는 건너뛴다. 청크 설정이 색인과 다르면 멈춘다(`--reset` 으로 새로 만듦) | `rag/build_index.py` |

**무엇이 바뀌면 어디부터 다시 돌리나**

| 바뀐 것 | 다시 실행할 단계 |
|---|---|
| 기간(`collect/config.py` 의 `DB_START`, `DB_END`) | `data/raw/dart/list_selected/` 를 비우고 ① 5개사 공시부터 ②·③·④ 전부 (README) |
| 뉴스 원본·재분류 규칙 | ② → ③ → ④ (기사 집합이 바뀌면 LLM 단계는 새 기사만 처리됨) |
| 공시 원문 | ③ → ④ 매칭·금액·RAG 색인 |
| DB만 다시 빌드 (원본 그대로) | 할 일 없음 — ④ 결과는 `url`·`rcept_no` 키라 그대로 맞는다 (2026-11-18 확인, [DATABASE_SCHEMA](../06_technical/DATABASE_SCHEMA.md) 5절) |
| 감성·이슈 결과 | `build_summary_cards.py` (요약 카드의 건수·근거 기사) |
| 영어 기사 집합 | `translate_titles.py --all` (새 기사만 번역). DB만 다시 빌드하면 `build_db.py` 가 `title_ko.csv` 로 번역을 다시 채운다 |
| 프롬프트·모델 | 해당 LLM 단계 (버전이 다르면 전체를 다시 처리 — 비용 추정 먼저) |

## 5. Git에 올리는 것과 빼는 것

| 구분 | 경로 | 이유 |
|---|---|---|
| **올림** | `02_BIO_news_3y/`, `03_CDMO_news_3y/`, `data/raw/` (DART 목록·원문 zip, 뉴스 jsonl, 팀원 CSV, 수집 로그) | 저장소만으로 API 없이 DB를 다시 만들 수 있게 |
| **올림** | `data/processed/` (EDA·LLM·매칭·금액·요약 결과), `data/eval/` (검수 표본·평가 결과) | LLM 결과는 다시 만들면 비용이 들고, 화면이 바로 읽는다 |
| **뺌** | `data/db/` (통합 DB) | 원본에서 `python db/build_db.py` 로 다시 만든다 |
| **뺌** | `chroma_db/` (RAG 색인, 약 692MB) | 용량. `python rag/build_index.py` 로 다시 만들거나 팀원에게 폴더를 받는다 |
| **뺌** | `.env`, `.streamlit/secrets.toml` | API 키 (`.env.example` 만 빈 값으로 올림) |

## 6. 결과 저장 위치와 DB 재빌드 시 보존

- **LLM 결과·매칭·금액·요약**은 DB 테이블이 아니라 `data/processed/` 파일에 기사 `url` 또는 공시 `rcept_no` 키로 저장한다. DB를 다시 빌드하면 `news_id` 가 바뀔 수 있기 때문이다. 대시보드가 화면에서 붙인다 (`dashboard/core/data.py`).
- **영어 제목 번역(`title_ko`)** 은 `data/processed/title_ko.csv` (URL 키, 797건)에 저장한다. DB 칸은 적재할 때 비지만 `db/build_db.py` 의 `load_title_ko()` 가 이 파일로 다시 채운다. 번역만 DB에 다시 넣으려면 `python analysis/translate_titles.py --apply` (API 호출 없음). 2026-11-18 전체 번역 완료 (`translate-v3`, 품질 표본 검수 전 — [AI_CLASSIFICATION](../04_ai/AI_CLASSIFICATION.md) 5절).
- **임베딩**은 `chroma_db/` 에 있고 청크마다 `rcept_no` 를 메타데이터로 가진다. DB 재빌드와 무관하다.

## 7. 한계와 유의점

- **DB 재빌드를 실제로 다시 해서 결과가 같은지는 이 문서를 쓰며 확인하지 않았다.** 2026-11-16 빌드와 2026-11-17 빌드의 적재 건수가 같은 것은 확인했다 ([DATABASE_SCHEMA](../06_technical/DATABASE_SCHEMA.md) 4절).
- **구글 뉴스 RSS는 같은 검색을 다시 해도 같은 결과를 보장하지 않는다.** ① 뉴스 수집을 처음부터 다시 하면 기사 집합이 달라질 수 있다. 그래서 받은 원본(`data/raw/`)을 git에 보관하고 ②부터 다시 돌리는 것을 기본으로 한다.
- **LLM 결과는 다시 돌리면 조금씩 달라질 수 있다.** 같은 버전으로 성공한 기사를 건너뛰는 이유이기도 하다.
- **④ 분석 단계의 실행 순서는 README에 아직 없다** (공시 RAG·요약 카드만 있음). README를 고칠 때 3절을 옮긴다.
