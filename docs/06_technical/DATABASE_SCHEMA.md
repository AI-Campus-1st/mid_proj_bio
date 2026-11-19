# 데이터베이스 스키마

> **상태:** 작성 완료 — `docs/data_schema.md` 전체를 옮기고, DB 밖 산출물(LLM·매칭·금액·요약 CSV, RAG 색인)과의 연결·재빌드 시 보존 규칙을 더함 · **최종 갱신:** 2026-11-19
> **원본:** `docs/data_schema.md` (전체), `db/schema.sql`, `db/build_db.py`
> **관련 문서:** [masterplan](../masterplan.md) · [DATA_PIPELINE](../03_data/DATA_PIPELINE.md) · `SYSTEM_ARCHITECTURE.md` · [NEWS_DISCLOSURE_MATCHING](../04_ai/NEWS_DISCLOSURE_MATCHING.md) · [UI_SPECIFICATION](../05_design/UI_SPECIFICATION.md)

---

- **DB 파일:** `data/db/bio_cdmo.sqlite` (SQLite, `python db/build_db.py` 로 재생성. git 제외)
- **스키마 정의:** `db/schema.sql`
- **대상 기업:** 삼성바이오로직스, SK바이오사이언스, 프레스티지바이오로직스, 에스티팜, 바이넥스
- **기간:** 2023-10-19 ~ 2026-10-19 — 제공 뉴스(`02_BIO_news_3y`)의 수집 기간에 뉴스·공시를 모두 맞췄다.
- **날짜:** 모두 한국시간(KST) 기준 `YYYY-MM-DD` 문자열이다 (`db/schema.sql` 3행). 변환하지 않는다.

## 1. 데이터 구성 (가이드 2-1 대응)

뉴스는 원본 5종을 합쳐 CDMO 키워드로 재분류한 **통합본**(`03_CDMO_news_3y/*묶음*.csv`)을 거쳐 DB에 들어간다. 통합본을 만드는 과정은 `docs/news_sort.md` 에 있다.

| 구분 | 출처 | 원본 위치 | DB `origin` |
|---|---|---|---|
| 뉴스 (제공) | 네이버 뉴스, 바이오 키워드 5개 | `02_BIO_news_3y/` | `provided` |
| 뉴스 (팀원 수집) | CDMO 규제·투자유치 검색 | `data/raw/cdmo_*.csv` | `team` |
| 뉴스 (기업명 검색) | 구글 뉴스 RSS, 5개사 기업명 | `data/raw/news/company_*.jsonl` | `google_company` |
| 뉴스 (CDMO 검색) | 구글 뉴스 RSS, CDMO 검색어 25개 | `data/raw/news_cdmo/*.jsonl` | `google_cdmo` |
| 뉴스 (해외 검색) | 구글 뉴스 RSS 미국판, CDMO 지정학 영어 검색어 4개 | `data/raw/news_global/*_en.jsonl` | `google_global` (`lang='en'`) |
| 공시 목록 | DART `list.json` | `data/raw/dart/list_selected/` | – (`disclosures`) |
| 공시 원문 | DART `document.xml` | `data/raw/dart/document/{접수번호}.zip` | – (`disclosure_documents`) |

수집(collect) → 재분류(analysis) → 적재(db) 계층을 분리했다. `db/build_db.py` 는 API를 호출하지 않고 저장된 파일만 읽는다. 원본 파일은 모두 git에 있으므로 저장소만으로 DB를 다시 만들 수 있다 (흐름은 [DATA_PIPELINE](../03_data/DATA_PIPELINE.md)).

## 2. 테이블

```
                    ┌──< news_cdmo_keywords   (CDMO 키워드 6개)
companies ──< news_companies >── news ──── news_clean   (정제 텍스트, 1:1)
    │               └──< news_keywords        (원래 바이오 키워드, 제공 뉴스만)
    └──< disclosures ──< disclosure_documents
meta (빌드 정보)
```

### meta — 빌드 정보

| key | 값 (2026-11-17 빌드) |
|---|---|
| `period_start`, `period_end` | 2023-10-19, 2026-10-19 (`collect/config.py` 의 `DB_START`, `DB_END`) |
| `built_at` | 2026-11-17T11:23:42 (KST) |
| `dup_rule` | 정규화 제목 동일 & 7일 이내 |

대시보드는 이 값을 "데이터 범위·한계"의 기준 줄과 기간 필터 범위로 쓴다.

### companies — 분석 대상 기업
| 컬럼 | 설명 |
|---|---|
| `corp_code` (PK) | DART 고유번호 |
| `corp_name` | DART 회사명 |
| `stock_code` | 종목코드 |
| `corp_cls` | Y 유가증권 / K 코스닥. 공시 목록(`list.json`)의 값으로 채운다 — 삼성바이오로직스·SK바이오사이언스 Y, 에스티팜·바이넥스·프레스티지바이오로직스 K |
| `sector` | CDMO |

### news — 뉴스 1건 = 1행
| 컬럼 | 설명 |
|---|---|
| `news_id` (PK) | 일련번호 (빌드할 때마다 다시 매긴다) |
| `origin` | `provided` / `team` (본문 있음), `google_company` / `google_cdmo` / `google_global` (제목만) |
| `title`, `body` | 제목, 본문 전문 (`google_*` 는 본문 NULL). `google_global` 은 영어 원문 |
| `url` | 원문 링크 (UNIQUE) — **DB 밖 산출물이 기사를 찾는 키** (5절) |
| `published_at`, `published_date` | 발행 일시·일자 (KST) |
| `press` | 매체명 |
| `body_len` | 본문 글자 수 |
| `cdmo_mention` | 제목·본문에 CDMO·CMO·위탁(개발)생산 표현이 있으면 1 |
| `title_norm` | 중복 판정용 정규화 제목 (한글·영문·숫자만 남김) |
| `dup_of` | 중복이면 대표 기사의 `news_id`, 대표 기사는 NULL |
| `search_terms` | 수집에 쓴 검색어·기업명. 제공 뉴스는 NULL (`news_keywords` 참고). 해외 검색은 세부 이슈(생물보안법 / 의약품 관세 / 미국 현지 생산 / 유럽 현지 생산) |
| `cdmo_rel_basis` | CDMO 관련 근거: `title` / `body` / `query` / `none` |
| `cdmo_kw_basis` | CDMO 키워드 근거: `title` / `body` / `query` / `none` |
| `lang` | 기사 언어 `ko` / `en`. `en` 은 대시보드에서 한국어로 번역해 보여준다 |
| `title_ko` | 한국어 번역 제목 (영어 기사 797건 모두). `analysis/translate_titles.py` 가 만들어 `data/processed/title_ko.csv` 에 저장하고, `db/build_db.py` 의 `load_title_ko()` 가 빌드 때 이 파일로 채운다 (6절) |

영어 기사의 `cdmo_mention` 과 기업 매핑(`news_companies`)은 영어 패턴(`collect/config.py` 의 `CDMO_PATTERN_EN`, `COMPANY_PATTERNS_EN`)으로 판정한다. 한국어 기사의 판정 규칙은 그대로이다.

### news_clean — 뉴스 정제 텍스트 (뉴스 1건 = 1행)
| 컬럼 | 설명 |
|---|---|
| `news_id` (PK) | `news.news_id` |
| `title_clean` | 정제한 제목 — 보이지 않는 문자·HTML 엔티티 제거, 따옴표 통일, 공백 정리 |
| `body_clean` | 정제한 본문 — 발신지·기자 서명, 저작권·제보·구독 문구, 이메일, URL, 사진 출처 제거. 본문이 없으면 NULL |
| `body_clean_len` | 정제 본문 글자 수 |

원문(`news.title`, `news.body`)은 바꾸지 않는다. LLM 입력·임베딩·화면 표시에는 이 테이블을 쓴다. 규칙은 `analysis/clean_text.py`, 결과와 한계는 `docs/eda_report.md` 2절에 있다. `db/build_db.py` 가 적재할 때 함께 채운다.

### news_cdmo_keywords — 뉴스 ↔ CDMO 키워드
| 컬럼 | 설명 |
|---|---|
| `news_id`, `keyword` (PK) | CDMO 규제·정책 / 지정학 / 모달리티 / 생산능력 / 수주 / 경쟁 구도. 한 기사에 여러 행 가능 |
| `category` | 규제 및 정책 / 기술 및 트렌드 / 시장 및 경쟁 |
| `is_primary` | 대표 키워드이면 1 (기사당 1개) |

키워드가 붙지 않은 기사(`해당 없음`)는 이 테이블에 행이 없다.

### news_keywords — 뉴스 ↔ 원래 수집 키워드 (제공 뉴스만)
| 컬럼 | 설명 |
|---|---|
| `news_id`, `keyword` (PK) | 바이오 규제 / 특허 / R&D / M&A / 투자 유치 (가이드 2-3) |
| `category` | 규제 및 정책 / 기술 및 트렌드 / 시장 및 경쟁 |

### news_companies — 뉴스 ↔ 기업
| 컬럼 | 설명 |
|---|---|
| `news_id`, `corp_code` (PK) | 한 기사가 여러 기업을 언급하면 여러 행 |
| `match_field` | `title` 제목에 기업명 / `body` 본문에만 / `query` 기업명 검색 결과이지만 제목에는 없음 |

### disclosures — 공시 1건 = 1행
| 컬럼 | 설명 |
|---|---|
| `rcept_no` (PK) | 접수번호 (14자리) — **DB 밖 산출물과 RAG 색인이 공시를 찾는 키** (5절) |
| `corp_code` | 기업 |
| `rcept_date` | 접수일 |
| `report_nm` | 보고서명 |
| `pblntf_ty`, `pblntf_ty_nm` | 공시 유형 (A 정기공시, B 주요사항보고, I 거래소공시 등) |
| `flr_nm`, `rm` | 제출인, 비고 |
| `is_amended` | 정정 공시이면 1 |
| `event_class`, `event_weight` | 수주·증설·M&A·실적 등 분류와 가중치 (`docs/company_selection.md` 3절 규칙과 동일, `analysis/disclosure_weights.py`). 정정 공시의 가중치는 0 |
| `url` | DART 뷰어 링크 (RAG 답변의 근거 링크로 사용) |
| `has_document`, `doc_chars` | 원문 확보 여부, 원문 글자 수 |

### disclosure_documents — 공시 원문 텍스트
| 컬럼 | 설명 |
|---|---|
| `rcept_no`, `seq` (PK) | `seq`=1 본문, 2 이상은 첨부(감사보고서 등) |
| `file_name` | zip 안의 파일명 |
| `text` | 태그를 제거한 텍스트. 표는 행마다 줄바꿈, 칸은 ` | ` 로 구분 |
| `n_chars` | 글자 수 |

### 뷰
| 뷰 | 용도 |
|---|---|
| `v_documents` | 뉴스와 공시를 같은 컬럼(`doc_type, doc_id, corp_code, doc_date, title, body, source, url, category, keyword, subtype, is_duplicate, lang, title_ko`)으로 조회. 공시는 `lang='ko'`. 뉴스의 `category`·`keyword` 는 대표 CDMO 키워드 기준, 공시의 `category` 는 `event_class` 이고 `keyword` 는 NULL. 기업이 매핑되지 않은 뉴스는 `corp_code` 가 NULL 인 1행 |
| `v_company_daily` | 기업 × 일자별 뉴스 건수(중복 제거)·공시 건수. 기사량·공시 추이와 시점 비교에 사용. **주의:** `match_field` 를 거르지 않아 `query` 기사도 센다 — 대시보드 S5는 PRD 4절 R2(`title`·`body` 만)를 지키려고 이 뷰 대신 기본 테이블로 집계한다 (UI_SPECIFICATION 미결 Q2) |

## 3. 적재 규칙과 판단 근거

- **기간 정렬** — 제공 뉴스가 2023-10-19 ~ 2026-10-19 이므로 이 기간을 기준으로 삼았다. 공시 목록은 이 기간으로 받았고, 뉴스는 통합본을 만들 때 기간 밖 기사를 제외했다.
- **뉴스는 통합본 그대로** — 출처 간 겹침은 통합본 단계에서 이미 정리되어 있다 (제공 > 팀원 수집 > 기업명 검색 > CDMO 검색 순으로 한 건만 남김). DB는 통합본의 행을 그대로 싣고 CDMO 키워드를 `news_cdmo_keywords` 로 펼친다.
- **중복 표시** — 삭제하지 않고 `dup_of` 로 표시만 한다. 기준은 "정규화 제목이 같고 발행일이 7일 이내"이다. 통합본은 제공 뉴스끼리의 겹침을 지우지 않으므로, 남아 있는 74건은 모두 제공 뉴스이다.
- **기업 매핑** — 정규식(`collect/config.py` 의 `COMPANY_PATTERNS`)으로 제목·본문을 검색한다. `삼성바이오`·`삼바`는 삼성바이오로직스로 보되 `삼성바이오에피스`는 제외하고, `프레스티지바이오파마`(모회사)는 프레스티지바이오로직스로 보지 않는다.
- **공시 원문** — DART가 주는 zip을 그대로 보관하고, 적재할 때 텍스트만 추출한다. 지분공시 등 유형을 가리지 않고 5개사의 모든 공시를 대상으로 했다.
- **원자적 교체** — 임시 파일(`bio_cdmo.tmp`)에 끝까지 적재한 뒤에만 기존 DB를 바꾼다. 중간에 실패하면 기존 DB가 그대로 남는다 (`db/build_db.py` `main()`).

## 4. 적재 결과 (2026-11-17 빌드)

2026-11-18에 현재 DB로 다시 셌다. 2026-11-16 빌드(`docs/data_schema.md` 4절)와 모든 수치가 같다.

| 항목 | 건수 |
|---|---|
| 뉴스 전체 | 9,216 (제공 2,792 / 팀원 수집 1,306 / 기업명 검색 2,202 / CDMO 검색 2,119 / 해외 검색 797) |
| 중복 제외 뉴스 | 9,142 |
| 본문이 있는 뉴스 | 4,059 (제공 2,790 / 팀원 수집 1,269) |
| 정제 텍스트(`news_clean`) | 9,216 (본문 4,059, 정제 후 글자 수 780만 → 원문 대비 0.9% 감소) |
| CDMO 키워드가 붙은 뉴스 | 4,729 (키워드 매핑 7,343행) |
| 중복 표시(`dup_of`) | 74 |
| 원래 키워드 매핑(`news_keywords`) | 2,851 |
| 뉴스–기업 매핑 | 3,606 |
| 공시 | 867 |
| 공시 원문 확보 | 864 (파일 891개, 약 3,189만 자) |
| 뷰 행 수 | `v_documents` 10,259 · `v_company_daily` 1,916 |

| CDMO 키워드 | 기사 수 | 대표 키워드인 기사 |
|---|---|---|
| CDMO 규제·정책 | 897 | 718 |
| CDMO 지정학 | 831 | 602 |
| CDMO 모달리티 | 1,387 | 996 |
| CDMO 생산능력 | 1,126 | 644 |
| CDMO 수주 | 1,507 | 893 |
| CDMO 경쟁 구도 | 1,595 | 876 |

| 기업 | 뉴스(제목) | 뉴스(본문만) | 뉴스(검색만) | 공시 | 원문 |
|---|---|---|---|---|---|
| 삼성바이오로직스 | 1,369 | 403 | 104 | 332 | 330 |
| SK바이오사이언스 | 419 | 91 | 143 | 167 | 167 |
| 에스티팜 | 329 | 87 | 160 | 189 | 188 |
| 프레스티지바이오로직스 | 53 | 16 | 282 | 95 | 95 |
| 바이넥스 | 74 | 17 | 59 | 84 | 84 |

원문이 없는 3건은 모두 첨부정정 공시로, DART가 "파일이 존재하지 않습니다"(014)를 반환했다. 사유는 `data/raw/dart/document/_missing.json` 에 남아 있다.

## 5. DB 밖 산출물과 연결

LLM 결과·매칭·금액·요약은 **DB 테이블이 아니라 `data/processed/` 의 CSV·JSON**에 둔다. DB는 git에 올리지 않고 각자 다시 빌드하는데, 다시 빌드하면 `news_id` 가 바뀔 수 있고 LLM 결과는 다시 만들면 비용이 들기 때문이다. 산출물은 git에 올리고, 바뀌지 않는 키(기사 `url`, 공시 `rcept_no`)로 DB와 잇는다. 대시보드는 DB와 이 파일들을 읽기만 한다(PRD N1·N2).

| 산출물 | 만드는 스크립트 | 키 → DB | 행 | 연결 확인 (2026-11-18) |
|---|---|---|---|---|
| `sentiment_llm.csv` 감성(기회/위험/중립) | `analysis/label_sentiment.py` (LLM) | `url` → `news` | 4,727 | 전부 중복 제외 뉴스에 있음 |
| `issues_llm.csv` 이슈 이름·유형·키워드 | `analysis/extract_issues.py` (LLM) | `url` → `news` | 4,727 | 전부 있음 |
| `issue_groups.csv` 이슈 이름 묶음 | `analysis/group_issues.py` (LLM) | `issue_norm` → `issues_llm.csv` | 3,581 | — |
| `title_ko.csv` 영어 제목 번역 | `analysis/translate_titles.py` (LLM) | `url` → `news` (빌드 때 `news.title_ko` 로 적재) | 797 | 전부 영어 기사에 있음 (2026-11-18 확인) |
| `modality_llm.csv` 모달리티 태그 | `analysis/tag_modality.py` (LLM) | `url` → `news` | 4,727 | 전부 있음 |
| `news_disclosure_links.csv` 뉴스-공시 연결 | `analysis/match_news_disclosure.py` (규칙) | `url` → `news`, `rcept_no` → `disclosures` | 7,135 (기사 1,441 · 공시 211) | 전부 있음 |
| `contract_amounts.csv` 수주 계약 금액 | `analysis/extract_contract_amounts.py` (정규식) | `rcept_no` → `disclosures` | 98 | 전부 있음 |
| `eda_*.csv` 기사량·급증 집계 | `analysis/eda.py` | 급증 대표 기사 `url` → `news` | `eda_spikes` 67 | 대표 기사 175건 전부 있음 |
| `summary_cards.json` 요약 결론·카드 | `analysis/build_summary_cards.py` | 근거 기사 `url`, 공시 `rcept_no` | 카드 8 | 근거 기사 24건 전부 있음 |
| `chroma_db/` 공시 RAG 색인 (git 제외) | `rag/build_index.py` (임베딩) | 청크 메타데이터 `rcept_no` → `disclosures` | 청크 36,548 · 공시 864 | 원문 있는 공시 864건 전부 색인, DB에 없는 공시 0 |

확인 방법: 각 산출물의 키를 DB(2026-11-17 빌드)에 대어 DB에 없는 키를 셌다. 연결 키도 확인했다 — `news.url` 은 9,216건 모두 값이 있고 중복이 없다(UNIQUE 제약).

**DB 테이블로 옮기지 않은 이유 (설계 판단):** 가이드의 "추가 예정 테이블(LLM 분류 결과, 모달리티 태그, 매칭 결과, 번역)"은 CSV로 대신했다. DB를 다시 빌드할 때 LLM 결과를 다시 적재하는 단계가 따로 필요 없고, git에서 결과 변경을 그대로 볼 수 있으며, 팀원이 DB 없이도 결과를 검토할 수 있다. 대신 화면에서 CSV와 DB를 `url`·`rcept_no` 로 붙이는 비용이 있고(대시보드 `core/data.py`), 키가 맞는지는 위 표처럼 따로 확인해야 한다.

## 6. DB 재빌드 시 보존할 것

| 데이터 | 재빌드하면 | 처리 |
|---|---|---|
| `news.news_id` | 다시 매겨져 바뀔 수 있다 | 분석 결과는 `url` 을 키로 저장한다 (5절의 산출물 모두 그렇게 되어 있음) |
| `news.title_ko` (영어 제목 번역) | 적재 직후 비지만 `load_title_ko()` 가 `data/processed/title_ko.csv` 로 다시 채운다 (2026-11-18 `build_db.py` 수정) | 할 일 없음. 번역만 다시 넣을 때는 `python analysis/translate_titles.py --apply` (API 호출 없음) |
| `news_clean` | 같은 규칙으로 다시 만들어진다 | 할 일 없음 (`analysis/clean_text.py` 규칙이 같으면 결과도 같다) |
| `chroma_db/` (RAG 색인) | DB 재빌드와 무관 (별도 폴더) | 공시 원문이 바뀌면 `python rag/build_index.py` 로 다시 만든다 (임베딩 비용, 약 $0.58) |
| `data/processed/` 산출물 | DB 재빌드와 무관 | 기사·공시 집합이 바뀌면 해당 스크립트를 다시 실행 ([DATA_PIPELINE](../03_data/DATA_PIPELINE.md) 4절) |

## 7. 한계와 유의점

- **구글 뉴스 수집분에는 본문이 없다.** 제목·매체·일자·링크만 있다. 본문 기반 분석(감성 분류 등)은 `provided`·`team` 또는 제목 기준으로 범위를 정해야 한다.
- **해외 뉴스는 영어 원문이다.** 화면에는 번역 제목(`title_ko`)과 원제목을 함께 보여준다(번역은 미리 만든 것이고 화면에서 호출하지 않는다, PRD N2). 번역 품질은 표본 30건 검수에서 의미·숫자·이름이 모두 맞았다(30/30, AI_EVALUATION 10절). 국내 기사와 언어가 달라 같은 사건이 국내·해외 기사로 각각 남는다.
- **CDMO 키워드는 규칙 기반 분류이고 정확도를 검수하지 않았다.** `cdmo_kw_basis='query'` (1,045건, 해외 검색 159건 포함)는 제목에 단서가 없어 검색어를 따른 것으로 신뢰도가 낮다. 자세한 한계는 `docs/news_sort.md` 5절에 있다.
- **`match_field='query'` 는 관련도가 낮다.** 기업명 검색에 걸렸으나 제목에는 기업명이 없는 기사로, 무관한 기사가 섞여 있다. 기업 단위 분석은 `title`·`body` 만 쓰는 것을 권장한다.
- **출처마다 시기 분포가 다르다.** 팀원 수집과 CDMO 검색은 2026년에 몰려 있다. 기사량 추이는 `origin` 별로 나눠 해석한다.
- **구글 뉴스 검색은 한 번에 최대 100건**이다. 삼성바이오로직스는 하루 100건에 닿은 날이 있어 일부 누락이 있을 수 있다.
- **중복 판정은 제목 기준**이라, 제목을 바꿔 실은 통신사 전재 기사는 잡지 못한다.
- **`news_id` 는 빌드할 때마다 바뀔 수 있다.** 분석 결과를 따로 저장할 때는 `url` 을 키로 쓴다.
- **기업 선정 점수도 같은 기간(2023-10-19 ~ 2026-10-19)의 공시로 산출**했다. 다만 구글 뉴스 기업명 검색 구간은 2023-11-13부터 나눠져 있어(`config.py` 의 `START`), 앞쪽 25일은 5개사만 보충 수집했다.

## 8. 조회 예시

```sql
-- 기업별 월간 뉴스·공시 건수
SELECT corp_name, substr(doc_date, 1, 7) AS ym,
       SUM(news_cnt) AS news, SUM(disclosure_cnt) AS disclosures
FROM v_company_daily GROUP BY corp_name, ym;

-- CDMO 키워드별 월간 기사 수 (대표 키워드 기준, 검색어만으로 분류한 기사 제외)
SELECT k.keyword, substr(n.published_date, 1, 7) AS ym, COUNT(*) AS news
FROM news n JOIN news_cdmo_keywords k USING (news_id)
WHERE k.is_primary = 1 AND n.cdmo_kw_basis <> 'query' AND n.dup_of IS NULL
GROUP BY k.keyword, ym;

-- 수주 공시와 계약 내용
SELECT c.corp_name, d.rcept_date, d.report_nm, d.url, x.text
FROM disclosures d
JOIN companies c USING (corp_code)
JOIN disclosure_documents x ON x.rcept_no = d.rcept_no AND x.seq = 1
WHERE d.event_class = '수주' AND d.is_amended = 0;

-- 제목이나 본문에 기업이 나오는 기사 (중복 제외)
SELECT c.corp_name, n.published_date, n.title, n.press, n.url
FROM news n
JOIN news_companies nc USING (news_id)
JOIN companies c USING (corp_code)
WHERE nc.match_field IN ('title', 'body') AND n.dup_of IS NULL;
```

```python
# DB 밖 산출물 붙이기 — 감성 라벨을 중복 제외 기사에 url 로 잇는다 (대시보드 core/data.py 와 같은 방식)
import sqlite3, pandas as pd
con = sqlite3.connect("data/db/bio_cdmo.sqlite")
news = pd.read_sql("SELECT news_id, url, published_date, title FROM news WHERE dup_of IS NULL", con)
labeled = news.merge(pd.read_csv("data/processed/sentiment_llm.csv"), on="url")   # 4,727행
```
