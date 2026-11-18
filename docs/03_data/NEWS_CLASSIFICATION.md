# 뉴스 분류

> **상태:** 작성 완료 — 카테고리 체계, CDMO 키워드 6개 정의, 규칙 기반 재분류(관련성 게이트·키워드 규칙·임계값), 근거 컬럼과 신뢰도, 중복 판정, 분류 결과, 알려진 오분류 · **최종 갱신:** 2026-11-18
> **원본:** `docs/news_sort.md` 1·3·4·5절, `analysis/build_cdmo_news.py`, `docs/data_schema.md` 3절, `db/build_db.py`
> **관련 문서:** [masterplan](../masterplan.md) · [NEWS_DATA_SPEC](NEWS_DATA_SPEC.md) (출처·검색어) · [DATABASE_SCHEMA](../06_technical/DATABASE_SCHEMA.md) · [AI_CLASSIFICATION](../04_ai/AI_CLASSIFICATION.md) (LLM 분류)

---

이 문서는 **규칙 기반 분류**(LLM 아님)를 다룬다. 기사마다 CDMO 관련 여부와 CDMO 키워드(카테고리)를 붙이며, 대시보드 사이드바의 "카테고리" 필터가 이 결과다. LLM이 붙이는 감성·이슈·모달리티는 [AI_CLASSIFICATION](../04_ai/AI_CLASSIFICATION.md)에 있다.

## 1. 카테고리 체계

**가이드의 카테고리와 바이오 키워드 (제공 뉴스).** 제공 뉴스는 과제 가이드 2-3의 바이오 키워드 5개로 수집되어 있고, 원래 키워드는 DB `news_keywords` 에 남는다 (제공 뉴스만).

| 바이오 키워드 | 카테고리 | 제공 뉴스 기사 수 |
|---|---|---|
| 바이오 규제 | 규제 및 정책 | 425 |
| 바이오 특허 | 기술 및 트렌드 | 264 |
| 바이오 R&D | 기술 및 트렌드 | 1,790 |
| 바이오 M&A | 시장 및 경쟁 | 304 |
| 바이오 투자 유치 | 시장 및 경쟁 | 68 |

가이드의 네 번째 카테고리인 "공급망 및 인프라"에는 제공 키워드가 없다. 이 프로젝트에서는 공급망 이슈를 "CDMO 지정학"(규제 및 정책), 생산 인프라를 "CDMO 생산능력"(시장 및 경쟁)으로 다룬다.

**CDMO 키워드 6개 (조에서 정의).** 분석 범위를 바이오 전체에서 CDMO로 좁히면서 키워드를 다시 정했다. 모든 출처의 뉴스를 이 6개로 재분류한다. 정의는 `collect/config.py` 의 `CDMO_KEYWORDS`.

| 키워드 | 카테고리 | 주요 이슈 |
|---|---|---|
| CDMO 규제·정책 | 규제 및 정책 | CDMO 특별법, 국가바이오위원회, GMP·FDA 실사, 품질관리 규제 |
| CDMO 지정학 | 규제 및 정책 | 미국 생물보안법, 의약품 관세, 미국 현지 생산 |
| CDMO 모달리티 | 기술 및 트렌드 | ADC, 세포·유전자치료제, mRNA, 항체 |
| CDMO 생산능력 | 시장 및 경쟁 | 공장 증설·착공, 해외 거점, 정책금융 |
| CDMO 수주 | 시장 및 경쟁 | 대형 수주, 빅파마 고객, 실적 |
| CDMO 경쟁 구도 | 시장 및 경쟁 | 신규 진입과 M&A, 론자·우시 등 해외 경쟁사 |

키워드별 검색어는 [NEWS_DATA_SPEC](NEWS_DATA_SPEC.md) 2절에 있다.

## 2. 규칙

LLM을 쓰지 않은 규칙 기반 분류이다. 재실행하면 같은 결과가 나온다. 규칙은 `analysis/build_cdmo_news.py` 의 `GATE`, `RULES`(한국어)와 `GATE_EN`, `RULES_EN`(영어)에 있다.

### 2-1. CDMO 관련성 게이트 (`GATE`)

업종 용어와 CDMO가 주력인 국내외 기업명이다. 제목 또는 본문에서 찾는다.

| 묶음 | 표현 |
|---|---|
| 업종 용어 | CDMO, CMO, CDO, 위탁개발생산, 위탁생산, 위탁개발, 위탁제조, 수탁생산 |
| 국내 기업 | 삼성바이오로직스, 삼성바이오(삼성바이오에피스 제외), 삼바, 롯데바이오로직스, 셀트리온바이오솔루션스, SK팜테코, 에스티팜, 바이넥스, 프레스티지바이오로직스, 에스티젠바이오, 마티카 |
| 해외 기업 | 론자, 우시, 후지필름, 캐털런트 |

영어 게이트(`GATE_EN`)는 CDMO·CMO·CDO, contract (development and) manufacturing, outsourcing, 국내외 CDMO 기업 영문명(Samsung Biologics, Lonza, WuXi, Fujifilm Diosynth, Catalent, Thermo Fisher, AGC Biologics 등)이다.

### 2-2. 키워드 규칙 (`RULES`)

조에서 정한 "주요 이슈"를 기사 표현으로 옮긴 정규식이다.

| 키워드 | 한국어 표현 (요약) | 영어 표현 (요약) |
|---|---|---|
| CDMO 규제·정책 | 특별법, 바이오위원회, GMP, 실사, 품질관리, 규제, 식약처, 법안·입법·국회, 지원법·육성법, 경고서한·워닝레터, 인허가 | FDA, EMA, GMP, inspection, warning letter, regulat-, compliance, guidance, approval, legislation, Congress, Senate, bill, law |
| CDMO 지정학 | 생물보안법·바이오보안법, 관세, 현지 생산, 미국 공장, 트럼프, 미중, 탈중국, 리쇼어링·온쇼어링, 공급망, 지정학 | BIOSECURE, tariff, onshoring·reshoring·nearshoring, domestic/US manufacturing, supply chain, geopolitics, China, Trump, Section 232, decoupling, Europe·EU |
| CDMO 모달리티 | ADC, 항체-약물 접합체, 세포·유전자, CGT, mRNA, 올리고, 이중항체, AAV, 벡터, CAR-T, 펩타이드, 모달리티, 항체의약품, 오가노이드, 플라스미드, 줄기세포 | ADC, cell & gene, gene/cell therapy, mRNA, oligonucleotide, bispecific, AAV, viral vector, CAR-T, peptide, modality, monoclonal, antibody, plasmid, GLP-1 |
| CDMO 생산능력 | 증설, 착공, 준공, 신공장, N공장, 공장 건설·인수, 생산능력, 캐파, 만 리터, 플랜트, 캠퍼스, 정책금융, 시설·설비투자, 부지, 생산시설·거점 | expansion, capacity, new plant/facility/site, campus, groundbreaking, construction, investment, liters |
| CDMO 수주 | 수주, 공급계약, 위탁생산 계약, 계약 체결, 빅파마, 고객사, 실적, 매출, 영업이익, 흑자·적자, 어닝 | contract, deal, agreement, order, partnership, signs, award, revenue, earnings, quarter, profit, sales, guidance |
| CDMO 경쟁 구도 | 인수, M&A, 합병, 진출, 출사표, 론자, 우시, 후지필름, 캐털런트, 써모피셔, 경쟁, 점유율, 신규 진입, 출범, 도전장, 분할 | acquisition, merger, M&A, buyout, takeover, Lonza, WuXi, Fujifilm, Catalent, Thermo Fisher, market share, competition, rival, enter market, launch, spin-off |

정확한 정규식은 `analysis/build_cdmo_news.py` 44~86행.

### 2-3. 판정 순서와 임계값

| 단계 | 판정 | 임계값 (`BODY_GATE_MIN, BODY_RULE_MIN, BODY_STRONG, BODY_TOP = 3, 3, 5, 2`) |
|---|---|---|
| 1. CDMO 관련 여부 (`CDMO관련근거`) | `title`: 제목에 게이트 표현 / `body`: 제목에 없고 본문에 게이트 표현이 3회 이상 / `query`: 제목·본문에 없으나 CDMO 검색어로 수집 / `none`: 관련 없음 → 키워드 `해당 없음` | 본문 3회 |
| 2. 키워드 (`키워드근거`) | `title`: 제목에 키워드 표현이 있으면 그 키워드. 본문에서 5회 이상 다룬 키워드가 있으면 함께 붙인다 | 본문 5회 |
| | `body`: 제목에는 없고 본문에 3회 이상 나온 키워드 중 상위 2개 (긴 기사의 과다 분류 방지) | 본문 3회, 상위 2개 |
| | `query`: 제목만으로 판정되지 않아 구글 뉴스 수집에 쓴 검색어의 키워드를 따랐다 | — |
| | `none`: CDMO 관련 기사이나 6개 이슈에 해당하지 않는다 → `해당 없음` | — |
| 3. 대표 키워드 (`대표키워드`) | 제목 일치를 우선해 가장 많이 일치한 1개 (점수 = 100 × 제목 일치 수 + 본문 일치 수) | — |

- 한 기사에 키워드가 여러 개 붙을 수 있다. 실제로는 키워드 1개 2,758건, 2개 1,505건, 3개 322건, 4개 이상 144건이다 (DB 2026-11-17 빌드).
- 팀원수집의 검색어(`CDMO 유상증자` 등)는 6개 키워드와 이름이 달라 분류에 쓰지 않고 `원수집키워드` 에만 남겼다. 본문이 있으므로 규칙만으로 분류한다.
- 해외검색(영어) 기사는 같은 6개 이슈를 영어 표현으로 옮긴 규칙(`GATE_EN`, `RULES_EN`)으로 분류한다. 제목만 있으므로 판정은 제목 기준이고, 단서가 없으면 검색 키워드(`CDMO 지정학`)를 따른다(`query`).

## 3. 근거 컬럼의 의미와 신뢰도

| 값 | `CDMO관련근거` (`cdmo_rel_basis`) | `키워드근거` (`cdmo_kw_basis`) | 신뢰도 |
|---|---|---|---|
| `title` | 3,266 | 3,015 | 높음 — 제목에 직접 표현 |
| `body` | 712 | 669 | 중간 — 본문 반복 언급 (본문 있는 제공·팀원수집만 가능) |
| `query` | 1,487 | 1,045 (해외검색 159건 포함) | **낮음** — 검색어를 그대로 따름 |
| `none` | 3,751 | 4,487 (`해당 없음`) | — |

(DB 2026-11-17 빌드, 전체 9,216건)

- `키워드근거 = query` 는 제목에 단서가 없어 검색어를 그대로 따른 것이다. 구글 검색은 본문까지 걸리므로 CDMO와 무관한 기사도 섞여 있다.
- 특히 `CDMO관련근거` 와 `키워드근거` 가 **모두 `query` 인 576건**(해외검색 79건 포함)은 제외하고 쓰는 것을 권장한다. EDA의 산업 전체 급증 판정은 이 기사를 뺐다 (`analysis/eda.py` 252~253행).
- 대시보드는 `cdmo_kw_basis='query'` 기사에 "검색어 근거" 배지를 붙인다 (UI_SPECIFICATION 6-6절, PRD 4절 R4).

## 4. 분류 결과

| 키워드 (복수 포함) | 전체 | 제공 | 팀원수집 | 기업명검색 | CDMO검색 | 해외검색 |
|---|---|---|---|---|---|---|
| CDMO 규제·정책 | 897 | 66 | 367 | 30 | 377 | 57 |
| CDMO 지정학 | 831 | 33 | 130 | 20 | 260 | 388 |
| CDMO 모달리티 | 1,387 | 97 | 352 | 180 | 689 | 69 |
| CDMO 생산능력 | 1,126 | 61 | 347 | 112 | 348 | 258 |
| CDMO 수주 | 1,507 | 87 | 434 | 262 | 563 | 161 |
| CDMO 경쟁 구도 | 1,595 | 149 | 420 | 127 | 685 | 214 |
| 해당 없음 | 4,487 | 2,543 | 324 | 1,620 | 0 | 0 |
| **기사 수** | **9,216** | **2,792** | **1,306** | **2,202** | **2,119** | **797** |

| CDMO 키워드 | 기사 수 | 대표 키워드인 기사 |
|---|---|---|
| CDMO 규제·정책 | 897 | 718 |
| CDMO 지정학 | 831 | 602 |
| CDMO 모달리티 | 1,387 | 996 |
| CDMO 생산능력 | 1,126 | 644 |
| CDMO 수주 | 1,507 | 893 |
| CDMO 경쟁 구도 | 1,595 | 876 |

CDMO 키워드가 붙은 기사는 4,729건(키워드 매핑 7,343행)이다. 이 중 중복을 뺀 4,727건이 LLM 감성·이슈·모달리티 분류의 대상이다 ([AI_CLASSIFICATION](../04_ai/AI_CLASSIFICATION.md)).

## 5. 중복 판정

| 단계 | 기준 | 처리 |
|---|---|---|
| 통합(출처 간) | 링크가 같거나, 정규화 제목이 같으면(정규화 제목 8자 이상일 때) 같은 기사 | 우선순위(제공 > 팀원수집 > 기업명검색 > CDMO검색 > 해외검색)대로 한 건만 남김. 건수는 [NEWS_DATA_SPEC](NEWS_DATA_SPEC.md) 3절 |
| DB 적재(남은 기사) | **정규화 제목이 같고 발행일이 7일 이내** | 삭제하지 않고 `news.dup_of` 에 대표 기사 번호를 표시. 74건, 모두 제공 뉴스끼리 (통합 단계가 제공 뉴스끼리의 겹침은 지우지 않기 때문) |

- 정규화 제목: 한글·영문·숫자만 남긴 제목 (`news.title_norm`).
- 대시보드와 분석은 항상 `dup_of IS NULL` 기사만 센다 (PRD 4절 R1, DB `meta.dup_rule`).
- 제목 기준이라, 제목을 바꿔 실은 통신사 전재 기사는 잡지 못한다.

## 6. 한계와 알려진 오분류

- **정확도를 검수하지 않았다.** 표본을 눈으로 훑어 규칙을 한 차례 조정했을 뿐, 정답 표본과 비교한 수치는 없다. 가이드 3-1의 표본 검수는 LLM 감성 분류로 했고([AI_EVALUATION](../04_ai/AI_EVALUATION.md) 4절), 이 규칙 분류의 검수는 아직 없다 (대시보드 한계 문구 5번).
- **제공 뉴스의 91%(2,543건)는 `해당 없음`** 이다. 제공 뉴스가 바이오 전반 키워드로 수집되어 CDMO 기사가 적기 때문이다.
- **기업명만으로 CDMO 관련으로 본다.** 그래서 에스티팜·SK바이오사이언스의 자체 신약·백신 기사가 `CDMO 모달리티` 로 잡힌다.
- **`실적`·`매출` 표현은 수주와 무관한 실적 기사도 `CDMO 수주` 로 묶는다.**
- **영어 규칙은 넓게 잡았다.** `Europe`·`China`·`contract`·`deal` 같은 표현은 범위가 넓어, 해외 기사가 지정학·수주로 과다 분류될 수 있다.
- **팀원수집에는 CDMO와 거리가 먼 기사가 섞여 있다.** 본문에 CDMO 표현이 3회 이상 나오면 관련 기사로 분류되어, 의료기기 허가·식약처 예산 같은 기사가 남는다. 324건은 `해당 없음` 으로 걸러졌다.
- **`query` 근거 기사(1,045건)는 신뢰도가 낮다** (3절).
