# 뉴스 데이터 명세

> **상태:** 작성 완료 — 뉴스 출처 5종의 수집 방식·원본 형식·건수, 통합본 형식, 검색어, 데이터 품질 · **최종 갱신:** 2026-11-18
> **원본:** `docs/news_sort.md` 1·2·4·5절, `docs/data_schema.md` 1·5절, `collect/collect_news*.py`, `collect/config.py`
> **관련 문서:** [masterplan](../masterplan.md) · [NEWS_CLASSIFICATION](NEWS_CLASSIFICATION.md) (재분류 규칙) · [DART_DATA_SPEC](DART_DATA_SPEC.md) · [DATA_PIPELINE](DATA_PIPELINE.md) · [DATABASE_SCHEMA](../06_technical/DATABASE_SCHEMA.md)

---

- **기간:** 2023-10-19 ~ 2026-10-19 (제공 뉴스의 수집 기간. 모든 출처를 이 기간으로 맞춤, `collect/config.py` 의 `DB_START`·`DB_END`)
- **산출물:** `03_CDMO_news_3y/` (통합본 1개 + 키워드별 6개 CSV) → 통합 DB `news` 테이블
- **재현:** `python collect/collect_news_cdmo.py` → `python collect/collect_news_global.py` → `python analysis/build_cdmo_news.py` (기업명 뉴스는 `collect_news.py company`, `collect_news_selected.py`. 전체 순서는 README와 [DATA_PIPELINE](DATA_PIPELINE.md))

## 1. 출처 5종

| 수집출처 (DB `origin`) | 수집 방식 | 원본 위치 | 본문 | 기간 내 원본 | 통합본 |
|---|---|---|---|---|---|
| 제공 (`provided`) | 과제 제공 (네이버 뉴스, 바이오 키워드 5개) | `02_BIO_news_3y/*묶음*.csv` | 있음 | 2,792 | 2,792 |
| 팀원수집 (`team`) | 팀원이 CDMO 규제·투자유치로 검색해 수집 | `data/raw/cdmo_규제_20261113.csv`, `data/raw/cdmo_투자유치_20261113.csv` | 있음 | 1,357 | 1,306 |
| 기업명검색 (`google_company`) | 구글 뉴스 RSS, 5개사 기업명 | `data/raw/news/company_{5개사}.jsonl` | 없음 | 2,263 | 2,202 |
| CDMO검색 (`google_cdmo`) | 구글 뉴스 RSS, CDMO 검색어 25개 (2절) | `data/raw/news_cdmo/*.jsonl` | 없음 | 2,790 | 2,119 |
| 해외검색 (`google_global`) | 구글 뉴스 RSS **미국판**, 영어 검색어 4개 (2절) | `data/raw/news_global/*_en.jsonl` | 없음 | 800 | 797 |
| **합계** | | | | | **9,216** |

- **팀원수집 원본은 2,614행**이다. 두 파일에 같은 링크가 100건 있어 기사로는 2,514건이고, 이 중 기간 밖 1,157건(2023-10-19 이전 또는 2026-10-19 이후)을 뺀 1,357건이 대상이다.
- 기업명 검색 파일(`data/raw/news/`)에는 기업 선정 단계에서 함께 받은 후보 14개사와 바이오 키워드 4개 검색 결과도 있다. 통합본에는 5개사 파일만 쓴다.
- 출처 간 겹침 처리는 3절, 출처별 키워드 분포는 [NEWS_CLASSIFICATION](NEWS_CLASSIFICATION.md) 4절에 있다.

### 구글 뉴스 RSS 수집 방식

| 항목 | 내용 | 근거 |
|---|---|---|
| 검색 문법 | `{검색어} after:{시작일−1} before:{끝일+1}` (구간 양 끝 포함) | `collect/collect_news.py` `fetch()` |
| 지역·언어 | 국내: `hl=ko&gl=KR&ceid=KR:ko` / 해외: `hl=en-US&gl=US&ceid=US:en` | 같은 파일 `LOCALE_KO`, `LOCALE_EN` |
| 구간 | 기업명 30일, CDMO·해외 검색 30일, (기업 선정 단계의 바이오 키워드 7일) | `collect()` 의 `step`, `STEP = 30` |
| 100건 제한 | 한 번에 최대 100건. 100건에 닿으면 구간을 반으로 나눠 다시 검색한다 | `LIMIT = 100` |
| 호출 간격 | 1초, 실패 시 대기 후 재시도 | `DELAY = 1.0` |
| 이어받기 | 끝난 구간을 `_done.txt` 에 적고, 다시 실행하면 이어서 받는다 | `DONE` |
| 기업명 검색어 | 기업명을 큰따옴표로 묶어 정확히 일치 검색 (`"바이넥스"`) | `collect()` 호출부 |
| 기간 보충 | 기업명 검색은 처음 2023-11-13 ~ 2026-11-12(`START`~`END`)로 받았고, 제공 뉴스 기간 중 앞쪽(2023-10-19 ~ 11-12)만 `collect_news_selected.py` 로 보충했다. `DB_END` 이후 기사는 적재할 때 거른다 | `collect/collect_news_selected.py` |

CDMO·해외 검색 원본은 6,018행·1,004행이고, 100건 제한에 걸린 채 남은 구간(`truncated=true`)은 없다 (2026-11-18 확인).

## 2. 검색어

### CDMO 키워드별 검색어 (국내, `CDMO_QUERIES`)

| 키워드 | 카테고리 | 주요 이슈 | 구글 뉴스 검색어 |
|---|---|---|---|
| CDMO 규제·정책 | 규제 및 정책 | CDMO 특별법, 국가바이오위원회, GMP·FDA 실사, 품질관리 규제 | `CDMO 특별법`, `CDMO 국가바이오위원회`, `CDMO GMP`, `CDMO FDA 실사`, `위탁생산 품질관리 규제` |
| CDMO 지정학 | 규제 및 정책 | 미국 생물보안법, 의약품 관세, 미국 현지 생산 | `CDMO 생물보안법`, `CDMO 의약품 관세`, `CDMO 미국 현지 생산` |
| CDMO 모달리티 | 기술 및 트렌드 | ADC, 세포·유전자치료제, mRNA, 항체 | `CDMO ADC`, `CDMO 세포유전자치료제`, `CDMO mRNA`, `CDMO 항체의약품` |
| CDMO 생산능력 | 시장 및 경쟁 | 공장 증설·착공, 해외 거점, 정책금융 | `CDMO 증설`, `CDMO 공장 착공`, `CDMO 생산능력`, `CDMO 정책금융` |
| CDMO 수주 | 시장 및 경쟁 | 대형 수주, 빅파마 고객, 실적 | `CDMO 수주`, `CDMO 위탁생산 계약`, `CDMO 빅파마`, `CDMO 실적` |
| CDMO 경쟁 구도 | 시장 및 경쟁 | 신규 진입과 M&A, 론자·우시 등 해외 경쟁사 | `CDMO 인수`, `CDMO 진출`, `CDMO 론자`, `CDMO 우시`, `CDMO 경쟁` |

키워드 이름 그대로는 기사에 잘 쓰이지 않아, 주요 이슈 표현으로 검색했다. 정의는 `collect/config.py` 의 `CDMO_KEYWORDS`, `CDMO_QUERIES` 에 있다.

### 해외(영어) 검색 — "글로벌" 범위 보완 (`GLOBAL_QUERIES`)

위 검색은 모두 한국어라 국내 언론 기사만 모인다. 지정학 이슈는 미국·유럽 정책이 출발점이므로, 같은 이슈를 **구글 뉴스 미국판(영어)** 으로 따로 검색했다. 기사는 영어 원문으로 두고(`언어=en`), 한국어 번역은 대시보드에 보여줄 때 쓰도록 미리 만들어 둔다(번역은 아직 미실행 — [DATABASE_SCHEMA](../06_technical/DATABASE_SCHEMA.md) 6절).

| 키워드 | 세부 이슈 | 영어 검색어 |
|---|---|---|
| CDMO 지정학 | 생물보안법 | `CDMO BIOSECURE Act` |
| CDMO 지정학 | 의약품 관세 | `CDMO pharmaceutical tariffs` |
| CDMO 지정학 | 미국 현지 생산 | `CDMO US manufacturing` |
| CDMO 지정학 | 유럽 현지 생산 | `CDMO Europe manufacturing` |

세부 이슈는 통합본의 `원수집키워드` 와 DB의 `news.search_terms` 에 남는다.

## 3. 겹침 처리 (통합 단계)

- **겹침 기준:** 링크가 같거나, 정규화 제목(한글·영문·숫자만 남긴 제목)이 같으면 같은 기사로 본다.
- **우선순위:** 제공 > 팀원수집 > 기업명검색 > CDMO검색 > 해외검색. 본문이 있는 쪽을 남기기 위해서다. 제공 뉴스는 서로 겹쳐도 전부 유지한다 (제공 뉴스끼리의 중복은 DB에서 `dup_of` 로 표시 — [NEWS_CLASSIFICATION](NEWS_CLASSIFICATION.md) 5절).
- **매체명 꼬리 제거:** 구글 뉴스 제목 끝의 ` - 매체명` 을 지운다. 매체명이 두 번 붙는 매체도 있어 반복해서 지운다 (`analysis/build_cdmo_news.py`).

| 제외된 쪽 | 겹친 상대 | 건수 |
|---|---|---|
| 팀원수집 | 제공 | 12 |
| 팀원수집 | 팀원수집 (같은 제목) | 39 |
| 기업명검색 | 제공 | 13 |
| 기업명검색 | 팀원수집 | 22 |
| 기업명검색 | 기업명검색 (같은 제목) | 26 |
| CDMO검색 | 제공 | 24 |
| CDMO검색 | 팀원수집 | 133 |
| CDMO검색 | 기업명검색 | 499 |
| CDMO검색 | CDMO검색 (같은 제목) | 15 |
| 해외검색 | 해외검색 (같은 제목) | 3 |

## 4. 원본 형식

| 원본 | 형식 | 컬럼·필드 |
|---|---|---|
| 제공 뉴스 `02_BIO_news_3y/` | CSV (UTF-8 BOM). 묶음 1개 + 키워드별 5개 | `제목, 본문전문, 원문URL, 발행일, 매체명, 문서종류, 수집키워드` |
| 팀원수집 `data/raw/cdmo_*.csv` | CSV (UTF-8 BOM), 제공 뉴스와 같은 컬럼 | 같음 (`수집키워드` 는 팀원이 쓴 검색어, 예: `CDMO 유상증자`) |
| 구글 뉴스 `data/raw/news*/*.jsonl` | 한 줄에 기사 1건 JSON | `kind` (company / cdmo / global / keyword), `name` (기업명·키워드), `category`, `query` (검색어), `window_start`, `window_end` (검색 구간), `truncated` (100건 제한에 걸렸는지), `title`, `source` (매체명), `pub_date` (UTC ISO), `link` (구글 뉴스 링크), `guid` |

### 통합본 `03_CDMO_news_3y/03_CDMO_묶음_CDMO_9216건_2023-10-19~2026-10-19.csv` (UTF-8 BOM)

| 컬럼 | 설명 |
|---|---|
| 제목, 본문전문, 원문URL, 발행일, 매체명, 문서종류 | 제공 뉴스와 같은 형식. 구글 뉴스 수집분은 본문전문이 비어 있다. 발행일은 `YYYY-MM-DDTHH:MM:SS` (한국시간)로 통일했다 |
| 수집키워드 | **재분류한 CDMO 키워드.** 여러 개면 `; ` 로 구분, 없으면 `해당 없음` |
| 대표키워드, 카테고리 | 대표 키워드 1개와 그 카테고리 |
| CDMO관련근거, 키워드근거 | `title` / `body` / `query` / `none` ([NEWS_CLASSIFICATION](NEWS_CLASSIFICATION.md) 3절) |
| 원수집키워드 | 제공 뉴스는 원래 키워드(바이오 R&D 등), 팀원수집은 검색어, 기업명검색은 기업명, CDMO검색은 검색 키워드, 해외검색은 세부 이슈(생물보안법 등) |
| 수집출처 | `제공` / `팀원수집` / `기업명검색` / `CDMO검색` / `해외검색` |
| 언어 | `ko` / `en` (해외검색만 `en`, 영어 원문) |

키워드별 파일 6개는 통합본에서 해당 키워드가 붙은 행만 뽑은 것이다. `해당 없음` 기사는 통합본에만 있다. 통합 DB는 이 통합본을 그대로 적재한다 (컬럼 대응은 [DATABASE_SCHEMA](../06_technical/DATABASE_SCHEMA.md) 2절 `news`).

## 5. 데이터 품질과 유의점

- **구글 뉴스 수집분에는 본문이 없다.** 제목·매체·일자·링크만 있다 (기업명·CDMO·해외 검색 5,118건). 본문 기반 분석(감성 분류 등)은 `provided`·`team` 또는 제목 기준으로 범위를 정해야 한다.
- **팀원수집은 2026년에 몰려 있다.** 1,306건 중 2026년이 1,162건이다(2023년 9건, 2024년 71건, 2025년 64건). 검색어마다 최신순 300건씩 받은 자료로 보인다.
- **구글 뉴스 CDMO검색도 최근에 치우쳐 있다.** 2023년 63건, 2024년 463건, 2025년 663건, 2026년 930건. 기사량 추이를 볼 때 `수집출처` 별로 나눠 봐야 한다.
- **팀원수집에는 CDMO와 거리가 먼 기사가 섞여 있다.** 의료기기 허가, 식약처 예산처럼 검색어 일부만 걸린 기사가 있고, 본문에 CDMO 표현이 3회 이상 나오면 관련 기사로 분류된다. 324건은 `해당 없음` 으로 걸러졌다.
- **해외검색은 영어 전문지 중심이다.** Fierce Pharma 194건, Contract Pharma 57건 등 업계 전문지가 많다. 연도별로는 2023년 32건, 2024년 237건, 2025년 278건, 2026년 250건이다.
- **해외검색은 국내 기사와 겹침 판정이 사실상 되지 않는다.** 언어가 달라 같은 사건을 다룬 한국어 기사와 정규화 제목이 일치하지 않는다. 같은 사건이 국내·해외 기사로 각각 남는다.
- **구글 뉴스 검색은 한 번에 최대 100건**이다. 구간을 나눠 다시 검색하지만, 삼성바이오로직스는 하루 100건에 닿은 날이 있어 일부 누락이 있을 수 있다.
- **구글 뉴스 링크는 원문 주소가 아니라 구글 뉴스 중계 주소**(`news.google.com/rss/articles/...`)다. 원문 본문을 자동으로 받으려면 원문 주소를 따로 풀어야 하며, 이 프로젝트는 하지 않았다.
- **구글 뉴스 RSS는 같은 검색을 다시 해도 같은 결과를 보장하지 않는다.** 그래서 받은 원본을 git에 보관하고, 통합 이후 단계만 다시 돌린다 ([DATA_PIPELINE](DATA_PIPELINE.md) 7절).
- **뉴스는 국내 언론 중심이다.** 해외(영어) 뉴스 797건은 지정학 이슈만 보강했다 (대시보드 한계 문구 1번).
- **통합 DB(`data/db/bio_cdmo.sqlite`)는 통합본을 그대로 적재한다.** 통합본을 다시 만들면 `python db/build_db.py` 도 다시 실행해야 한다.
