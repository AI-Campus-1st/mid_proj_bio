# API 명세

> **상태:** 작성 완료 — 외부 API(DART, 구글 뉴스 RSS, OpenAI), 단계 사이의 파일 인터페이스, 대시보드 조회 함수·DB 뷰, RAG 입출력 · **최종 갱신:** 2026-11-18
> **원본:** `collect/*.py`, `db/schema.sql`, `docs/data_schema.md` 6절(조회 예시), `analysis/*.py`, `rag/qa.py`, `dashboard/core/data.py`
> **관련 문서:** [masterplan](../masterplan.md) · [SYSTEM_ARCHITECTURE](SYSTEM_ARCHITECTURE.md) · [DATABASE_SCHEMA](DATABASE_SCHEMA.md) (테이블·조회 예시) · [TECH_STACK](TECH_STACK.md) · [NEWS_DISCLOSURE_MATCHING](../04_ai/NEWS_DISCLOSURE_MATCHING.md) 4-8절 (Q&A 화면용 반환값) · [AI_CLASSIFICATION](../04_ai/AI_CLASSIFICATION.md) (프롬프트·출력 규칙)

---

## 1. 외부 API

### 1-1. DART OpenAPI (`https://opendart.fss.or.kr/api`)

| 엔드포인트 | 파라미터 | 응답 | 쓰는 곳 |
|---|---|---|---|
| `corpCode.xml` | `crtfc_key` | zip 안 XML (전체 기업 고유번호) | `collect_dart_list.py` — 기업명 → `corp_code` |
| `list.json` | `crtfc_key`, `corp_code`, `bgn_de`, `end_de` (`YYYYMMDD`), `pblntf_ty` (A~J), `page_no`, `page_count=100` | JSON `status`, `message`, `list[]`(`rcept_no`, `rcept_dt`, `report_nm`, `corp_code`, `corp_cls`, `flr_nm`, `rm`), `total_page` | `collect_dart_list.py`, `collect_dart_selected.py` |
| `document.xml` | `crtfc_key`, `rcept_no` | zip (본문·첨부 XML/HTML). 실패 시 XML `<status>` | `collect_dart_selected.py doc` |
| `fnlttSinglAcnt.json` | `crtfc_key`, `corp_code`, `bsns_year=2025`, `reprt_code=11011` | JSON `list[]`(`account_nm`, `fs_div` CFS/OFS, `thstrm_amount`) | `collect_dart_fin.py` (매출액) |

| 상태 코드 | 뜻 | 처리 |
|---|---|---|
| `000` | 정상 | 저장 |
| `013` | 조회 결과 없음 | 저장 (빈 목록) |
| `014` | 파일 없음 (원문) | `document/_missing.json` 에 기록, 다시 요청하지 않음 (3건, 모두 첨부정정) |
| `020` | 요청 제한 초과 | 기록하지 않고 멈춤 → 나중에 다시 실행하면 이어서 받음 |
| 그 밖 | 오류 | 저장하지 않고 멈춤 |

호출 간격 0.3초, 네트워크 오류는 최대 3번 재시도(3초 × 시도 횟수 대기). 키는 `.env` 의 `DART_OPEN_API`. 자세한 수집 범위는 [DART_DATA_SPEC](../03_data/DART_DATA_SPEC.md) 2절.

### 1-2. 구글 뉴스 RSS (`https://news.google.com/rss/search`)

| 항목 | 값 |
|---|---|
| 검색 | `q={검색어} after:{시작일−1} before:{끝일+1}` (양 끝 포함) |
| 지역·언어 | 국내 `hl=ko&gl=KR&ceid=KR:ko`, 해외 `hl=en-US&gl=US&ceid=US:en` |
| 응답 | RSS XML `item` (`title`, `link`, `guid`, `pubDate`, `source`) |
| 제한 | 한 번에 최대 100건 → 100건에 닿으면 구간을 반으로 나눠 다시 검색 |
| 인증 | 없음. 호출 간격 1초 |

`link` 는 원문 주소가 아니라 구글 뉴스 중계 주소다 (원문 주소는 풀지 않았다). 자세한 수집 방식은 [NEWS_DATA_SPEC](../03_data/NEWS_DATA_SPEC.md) 1절.

### 1-3. OpenAI

| 기능 | API | 모델 | 요청 | 응답 처리 | 쓰는 곳 |
|---|---|---|---|---|---|
| 분류·추출·번역 | Chat Completions | `gpt-6-luna` (`reasoning_effort` low, 이슈 묶기만 medium) | system 프롬프트 + 기사(제목·본문 일부) 1건, `response_format` = json_schema(strict) | `*_prompt.py` 의 `parse_response()` 로 한 번 더 검증, 실패는 `error` 칸에 기록 | `label_sentiment.py`, `extract_issues.py`, `group_issues.py`, `tag_modality.py`, `translate_titles.py` |
| 공시 Q&A 답변 | Chat Completions | `gpt-6-luna` (low, 최대 4,096 토큰) | 질문 + 검색된 공시 발췌 최대 7개, json_schema(strict) — 4절 | 인용 검증 (4절) | `rag/qa.py` |
| 임베딩 | Embeddings | `text-embedding-3-small` | 청크 64개씩 (색인), 질문 1개 (질의) | Chroma에 저장 / 유사도 검색 | `rag/build_index.py`, `rag/qa.py` |

- 키: 환경변수 `OPENAI_API_KEY`, 없으면 `.env`.
- 동시 호출: 분류·번역 8개(`WORKERS`), 이슈 묶기는 앞 결과를 이어 쓰므로 차례로.
- 비용·모델 선택 이유는 [TECH_STACK](TECH_STACK.md) 5절. 대시보드는 Q&A 질문 때만 호출한다 ([SYSTEM_ARCHITECTURE](SYSTEM_ARCHITECTURE.md) 5절).

## 2. 단계 사이의 파일 인터페이스

다음 단계와 대시보드가 읽는 파일의 형식이다. 모두 `data/processed/`, UTF-8(BOM) CSV 또는 JSON. 키는 기사 `url` 또는 공시 `rcept_no` 이고 DB와의 연결은 [DATABASE_SCHEMA](DATABASE_SCHEMA.md) 5절.

| 파일 | 키 | 열 | 만드는 곳 |
|---|---|---|---|
| `sentiment_llm.csv` | `url` | `label` (기회/위험/중립), `reason`, `confidence` (high/medium/low), `input_basis` (title / title+body), `model`, `prompt_version`, `labeled_at`, `error` | `label_sentiment.py` |
| `issues_llm.csv` | `url` | `issue`, `issue_norm` (묶음 키), `issue_type`, `keywords` (`; ` 구분), `confidence`, `input_basis`, `model`, `prompt_version`, `extracted_at`, `error` | `extract_issues.py` |
| `issue_groups.csv` | `issue_norm` | `issue`, `issue_group` (대표 이름), `n_articles`, `model`, `prompt_version`, `grouped_at` | `group_issues.py` |
| `modality_llm.csv` | `url` | `modalities` (`; ` 구분, 빈 값이면 해당 없음), `evidence`, `confidence`, `input_basis`, `model`, `prompt_version`, `tagged_at`, `error` | `tag_modality.py` |
| `title_ko.csv` | `url` | `title` (원제목), `title_ko`, `model`, `prompt_version`, `translated_at`, `error` | `translate_titles.py` (DB `news.title_ko` 로도 적재) |
| `news_disclosure_links.csv` | `url` × `rcept_no` | `published_date`, `corp_code`, `corp_name`, `rcept_date`, `report_nm`, `window` (direct/follow), `day_gap` (공시일 − 기사일), `news_keyword` (`; ` 구분), `event_class`, `class_weight`, `is_amended`, `kw_low_confidence`, `follow_cut` | `match_news_disclosure.py` |
| `contract_amounts.csv` | `rcept_no` | `corp_name`, `rcept_date`, `report_nm`, `is_amended`, `amount_krw`, `amount_basis`, `original_date` (정정 대상 제출일), `before_amount_krw`, `counterparty`, `note` | `extract_contract_amounts.py` ([CONTRACT_AMOUNTS](../03_data/CONTRACT_AMOUNTS.md)) |
| `eda_spikes.csv` | `series` × `scope` × `peak_week` | `start_week`, `end_week`, `weeks`, `peak_count`, `baseline`, `z`, `total_in_episode`, `peak_day`, `peak_day_count`, `top_terms`, `evidence_articles` (` / ` 구분 `제목 (매체) URL`), `disclosures` (` / ` 구분 `YYYY-MM-DD [분류] 보고서명 URL`) | `eda.py` |
| `summary_cards.json` | 카드 `id` | `basis`, `built_at`, `conclusion`, `label_counts`, `cards[]` = {`id`, `type` (기회/위험), `title`, `desc`, `screen` (상세 화면 url_path), `n_articles`, `tags` {`companies`, `keywords`, `start`, `end`}, `evidence[]` {`kind` (기사/공시), `title`, `press`, `date`, `url`}} | `build_summary_cards.py` |

**규칙:** 실패한 행은 지우지 않고 `error` 칸에 이유를 남긴다. 화면은 `error` 가 빈 행만 쓴다. 같은 `model`·`prompt_version` 으로 성공한 행은 다시 실행할 때 건너뛴다.

## 3. 대시보드 조회 인터페이스 (`dashboard/core/data.py`)

**필터 값** — 모든 함수가 받는 `filters` 는 `{"period": (date, date), "companies": [기업명…], "keywords": ["CDMO …"…]}` 이다 (`st.session_state["filters"]`, 순서는 IA 4-1절).

| 함수 | 입력 | 반환 | 캐시 | 쓰는 화면 |
|---|---|---|---|---|
| `connect()` | — | SQLite 읽기 전용 연결 (`mode=ro`). DB가 없으면 `FileNotFoundError` | — | 내부 |
| `meta()` | — | `{period_start, period_end, built_at, dup_rule}` (실패 시 빈 dict) | ✓ | 공통(필터 범위, 한계 문구) |
| `news_frame()` | — | 중복 제외 기사 9,142행: `news_id, origin, published_date, published_at, title, url, press, lang, title_ko, cdmo_kw_basis, title_clean, date, origin_ko` | ✓ | S1·S2·S5, 근거 기사 |
| `news_keywords()` / `news_companies()` | — | 기사×키워드(`is_primary`) / 기사×기업(제목·본문 언급만) | ✓ | 필터 |
| `filter_news(filters)` | 필터 | `news_frame()` 을 UI_SPECIFICATION 4-2절 규칙으로 거른 표 | — | S0·S1·S2·S5 |
| `spikes_frame()` / `filter_spikes(filters)` | (필터) | 급증 67행 + `spike_id`, `event`(행사 주간) / 4-2절 규칙으로 거른 표 | ✓ / — | S1 |
| `spike_evidence(row)` | 급증 1행 | (대표 기사 최대 3건, 같은 시기 공시 목록) | — | S1 |
| `sentiment_frame()` | — | 감성 라벨 성공 행 (`url, label, reason, confidence, input_basis, model, prompt_version`) | ✓ | S0·S2 |
| `modality_frame()`, `filter_s3_news(filters)`, `s3_keywords(filters)` | (필터) | 기사×모달리티(기타 제외 7종), S3 대상 기사 | ✓ / — | S3 |
| `disclosures_frame()` / `filter_disclosures(filters, event_classes=None)` | (필터, 분류) | 공시 867행 (`rcept_no, rcept_date, corp_name, report_nm, event_class, is_amended, url, date`) / 기간·기업·분류로 거름 | ✓ / — | S3·S4·S5 |
| `keyword_events(filters)` | 필터 | 선택 카테고리에 대응하는 공시 분류 집합 (NEWS_DISCLOSURE_MATCHING 3-3절 대응표) | — | S4·S5 |
| `contract_amounts()` | — | (원공시 표 + 최신 정정 금액, 정정 공시 표) | ✓ | S4 |
| `links_frame()` / `filter_links(filters)` | (필터) | 뉴스-공시 연결 7,135행 + `keywords` 목록 / 4-2절 연결 규칙으로 거름 | ✓ / — | S0·S5 |

캐시는 `st.cache_data` 로 프로세스 안에서 유지된다. 데이터 파일을 바꾸면 대시보드를 다시 시작해야 반영된다.

**DB 뷰** — `v_documents`(뉴스·공시를 같은 열로), `v_company_daily`(기업×일자 건수). 정의와 조회 예시는 [DATABASE_SCHEMA](DATABASE_SCHEMA.md) 2·8절. 대시보드는 `v_company_daily` 를 쓰지 않는다 (기업명 검색으로만 걸린 기사까지 세기 때문, UI_SPECIFICATION 미결 Q2).

## 4. RAG 질의응답 (`rag/qa.py`)

### 4-1. 함수

```python
ask(question: str, corp_names: list | None = None, date_from: str | None = None, date_to: str | None = None) -> dict
```

| 입력 | 뜻 |
|---|---|
| `question` | 사용자 질문 (앞뒤 공백 제거) |
| `corp_names` | 검색할 기업 목록 (`None` 이면 5개사 전체). 질문 속 기업과 둘 다 있으면 겹치는 기업만 본다 — 겹치지 않으면 거절 |
| `date_from`, `date_to` | 접수일 범위 `YYYY-MM-DD` (`None` 이면 전체 기간) |

명령줄: `python rag/qa.py "질문"`.

### 4-2. 처리 단계 (LangChain `RunnableLambda` 체인)

| 단계 | 하는 일 | 거절 시 `stage` |
|---|---|---|
| `check_scope` | 질문의 기업 찾기. 5개사 밖 기업(론자 등)만 물으면 검색 전에 거절 (API 호출 없음) | `scope` |
| `retrieve` | 질문 임베딩 → 사건성 공시(수주·증설·M&A 등)에서 5개 + 전체에서 2개, 같은 공시는 2개까지, 정정 공시 우선 | `search` |
| `generate` | 발췌 최대 7개로 답변 생성(구조화 출력). 근거가 없으면 LLM이 거절 | `generate` |
| `verify` | 인용한 접수번호가 검색 결과에 있는지, 인용 구절이 원문에 있는지 확인. 하나라도 틀리면 거절. 공시명·제출일·링크는 LLM이 아니라 색인 메타데이터에서 채움 | `verify` |

LLM 출력 스키마: `{refused, answer, citations[{rcept_no, quote}], refusal_reason, judgment_declined, causality_unconfirmed}` (모두 필수, 추가 키 없음).

### 4-3. 반환값

| 키 | 뜻 |
|---|---|
| `refused` | 답하지 않으면 True (`answer` 에 거절 문구) |
| `stage` | `scope` / `search` / `generate` / `verify` / `answered` |
| `answer` | LLM 답변 원문 — 문장 끝에 `(접수번호)` |
| `answer_display` | 화면용 — `(접수번호)` 를 근거 번호 `[1]`, `[2]` 로 바꾼 것 (같은 공시는 같은 번호) |
| `refusal_reason` | 거절 이유 (답변이면 None) |
| `citations` | `[{n, rcept_no, corp_name, report_nm, is_amended, rcept_date, url, quote, quotes}]` — `n` 은 `answer_display` 의 번호, `quotes` 는 같은 공시의 인용 구절 전부 |
| `flags` | `{judgment_declined: 투자 판단을 요구해 판단하지 않음, causality_unconfirmed: "인과는 공시로 확인되지 않는다"를 덧붙임}` |
| `retrieved`, `top_similarity`, `filter`, `usage` | 검색 결과·유사도·적용 필터·토큰 사용량 (점검용) |

### 4-4. 오류

설정 문제나 API 실패는 거절이 아니라 예외 `QAError(code, message)` 로 알린다.

| `code` | 상황 | 대시보드 S6 표시 |
|---|---|---|
| `no_api_key` | `OPENAI_API_KEY` 없음 | "Q&A를 사용할 수 없습니다(설정 확인)" + 확인 방법 |
| `no_index` | `chroma_db/` 색인 없음 | 같음 |
| `api_error` | OpenAI 호출 실패 | 같음 |

대시보드에서의 상태별 표시(거절 3종, 판단 요구, 인과 미확인)는 [NEWS_DISCLOSURE_MATCHING](../04_ai/NEWS_DISCLOSURE_MATCHING.md) 4-8절과 `dashboard/views/s6_qa.py`.

### 4-5. 색인 (`rag/build_index.py`)

| 항목 | 값 |
|---|---|
| 대상 | 공시 원문 `seq = 1` 본문 864건 |
| 청크 | 1,000자, 겹침 150자 (`RecursiveCharacterTextSplitter`), 머리에 `[기업명 \| 보고서명 \| 접수일]` |
| 저장 | Chroma `chroma_db/`, 컬렉션 `disclosures` (cosine), ID `{rcept_no}-{seq}-{청크 번호}` |
| 메타데이터 | `rcept_no, seq, chunk_idx, corp_code, corp_name, rcept_date(정수 YYYYMMDD — 기간 필터용), report_nm, event_class, is_amended, url` — 검색 필터와 근거 표시에 씀 |
| 옵션 | `--dry-run`(비용 추정), `--event-class`, `--limit`, `--reset`, `--model`, `--chunk-size`, `--chunk-overlap`. 컬렉션의 모델·청크 설정과 다르면 멈춤 |
