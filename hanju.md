## 2026-11-13 — 해외(영어) 뉴스 본문 수집 스크립트 추가

- **브랜치**: `main`
- **버전**: 기준 `13efd42` (태그 없음) → 결과 미커밋
- **요청 내용**: 제목만 있는 기존 영어 기사(구글 뉴스 수집분)의 본문도 수집할 수 있는 코드 작성
- **진행 사항**:
  - `collect/collect_news_global_body.py` 추가: 구글 뉴스 리다이렉트 링크를 원문 URL로 디코딩(예전 형식은 base64, 새 형식 `AU_yqL…` 은 batchexecute 호출) → 기사 페이지에서 본문 추출(JSON-LD `articleBody` → `<article>` 문단 → 문단이 가장 많은 블록) → `data/raw/news_global/_bodies.jsonl` 에 guid 단위로 저장. 이어받기, `--retry`, `--limit` 지원
  - `analysis/build_cdmo_news.py` 가 `_bodies.jsonl` 의 성공 건 본문과 원문 URL을 통합본에 채우도록 수정
  - README 실행 순서에 5-1단계 추가

### 원본 대비 변경사항

`git diff --stat`: 2 files changed, 27 insertions(+), 3 deletions(-) (새 파일·이 기록 제외)

| 파일 | 구분 | 원본 | 변경 후 |
|------|------|------|---------|
| `collect/collect_news_global_body.py` | 추가 | (없음) | 영어 기사 원문 URL 디코딩 + 본문 추출, `_bodies.jsonl` 저장 (대상 803건, guid 기준) |
| `analysis/build_cdmo_news.py` | 수정 | 해외검색 기사 `body=None`, `url`=구글 뉴스 링크 | 본문 수집 성공 건은 `body`=본문, `url`=원문 URL |
| `README.md` | 수정 | 5. 해외 뉴스 수집 → 6. 통합본 | 사이에 5-1. 해외 뉴스 본문 수집 추가 |

```diff
# analysis/build_cdmo_news.py
+def load_global_bodies() -> dict:
+    """collect_news_global_body.py 가 받은 영어 기사 본문 (guid -> 기록). 성공(ok)한 마지막 기록만 쓴다."""
 def load_global_raw() -> list:
+    bodies = load_global_bodies()
-            row = by_guid.setdefault(r["guid"] or r["link"], {
-                ..., "body": None, "url": r["link"], ...
+            key = r["guid"] or r["link"]
+            got = bodies.get(key, {})
+            row = by_guid.setdefault(key, {
+                ..., "body": got.get("body"), "url": got.get("url") or r["link"], ...
```

- **비고**: 실제 네트워크 수집은 실행하지 않음(세션 권한에서 차단). 오프라인 검증만 함: 예전 형식 URL 디코딩, 새 형식 미디코딩 판정, 본문 추출 3경로(JSON-LD·article·문단 블록)와 짧은 구독벽 페이지 판정, 대상 803건 로드, `build_cdmo_news.py` 컴파일. `_bodies.jsonl` 은 아직 없으므로 통합본(`03_CDMO_news_3y/`)은 다시 만들지 않음. 본문 수집 후 `build_cdmo_news.py` → `db/build_db.py` 재실행 필요. 본문이 생기면 영어 기사도 본문 기준 CDMO 관련성·키워드 분류가 적용되어 분류 결과가 바뀔 수 있음.

## 2026-11-13 — 영어 본문 추출 규칙 수정 (Contract Pharma 0자 문제)

- **브랜치**: `main`
- **버전**: 기준 `13efd42` → 결과 미커밋
- **요청 내용**: 10건 시험 수집 결과 확인 (http_403 4건, short 4건, ok 2건)
- **진행 사항**: 구글 링크 → 원문 URL 디코딩은 10건 모두 성공 확인. Fierce Pharma(전체 803건 중 194건)는 사이트의 봇 차단(403)이라 우회하지 않고 제목만 유지하기로 함. Contract Pharma(58건)는 페이지 수신(200, `<p>` 54개)에도 0자 → 본문을 감싼 `header`·`aside`·`form` 등을 노이즈로 지운 것이 원인으로 보고 지우는 태그를 줄임

### 원본 대비 변경사항

| 파일 | 구분 | 원본 | 변경 후 |
|------|------|------|---------|
| `collect/collect_news_global_body.py` | 수정 | 노이즈 태그 12종 삭제 후 문단 추출 | `nav`·`footer`·`script` 등 8종만 삭제 |

```diff
# collect/collect_news_global_body.py
-NOISE = ("script", "style", "noscript", "header", "footer", "nav", "aside", "form", "figure",
-         "button", "iframe", "svg")
+NOISE = ("script", "style", "noscript", "nav", "footer", "button", "iframe", "svg")
```

- **비고**: 합성 HTML(본문이 `<header>` 안)로만 검증. 실제 Contract Pharma 페이지 재확인은 사용자 노트북에서 진행 필요. 이후 `--retry` 로 실패 건 재수집.

## 2026-11-13 — 영어 본문 추출 규칙 재수정 (깨진 HTML 대응)

- **브랜치**: `main`
- **버전**: 기준 `13efd42` → 결과 미커밋
- **요청 내용**: 직전 수정 후에도 Contract Pharma 본문 0자 — 진단 결과 확인
- **진행 사항**: 진단 셀 결과, Contract Pharma 페이지는 HTML 이 깨져 파서가 모든 `<p>`(메뉴 설명·본문·저작권)를 `header > div.header-container` 아래에 둠. 본문 1,099자 문단은 존재하나 `nav` 등 노이즈 태그 삭제 시 함께 지워진 것으로 판단. 태그 삭제를 보이지 않는 태그(script·style 등)로 줄이고, 마지막 단계를 "긴 문단(150자 이상) 길이 합이 가장 큰 직속 부모 블록" 선택으로 변경

### 원본 대비 변경사항

| 파일 | 구분 | 원본 | 변경 후 |
|------|------|------|---------|
| `collect/collect_news_global_body.py` | 수정 | `nav`·`footer`·`button` 삭제, 문단 글자 수 합이 가장 큰 블록 선택 | 삭제 안 함, 150자 이상 문단 길이 합이 가장 큰 직속 부모 블록 선택 |

```diff
-NOISE = ("script", "style", "noscript", "nav", "footer", "button", "iframe", "svg")
+NOISE = ("script", "style", "noscript", "iframe", "svg")
+LONG_P = 150
-    best = max((paragraphs(c) for c in parents.values()), key=len, default="")
+        score[id(p.parent)] = score.get(id(p.parent), 0) + (n if n >= LONG_P else 0)
+    best = parents[max(score, key=score.get)]
+    return paragraphs(best), "paragraphs"
```

- **비고**: 진단 결과를 본뜬 합성 HTML(닫히지 않은 header/nav 안에 메뉴 35개 + 본문)로 검증 — 본문만 추출되고 메뉴·저작권 문구는 제외됨. 실제 페이지 확인은 사용자 노트북에서 필요.
- **추가 수정(같은 작업)**: 150자 이상 문단이 없는 일반 기사가 0자가 되는 회귀를 발견해, 블록 점수를 (긴 문단 길이 합, 40자 이상 문단 길이 합) 순서로 비교하도록 보완. 합성 HTML 4종(깨진 HTML, 메뉴+짧은 문단 기사, 일반 기사, 구독벽) 모두 기대대로 동작 확인.

## 2026-11-13 — 네이버 API 기사 수집에 발행일 추가

- **브랜치**: `main`
- **버전**: 기준 `13efd42` → 결과 미커밋
- **요청 내용**: 네이버 API 수집 결과(`company_news_20261113.csv`, 1,368건)에 발행일 추가
- **진행 사항**: API 응답의 `pubDate` 를 한국시간 `YYYY-MM-DDTHH:MM:SS`(제공 뉴스와 같은 형식)로 바꿔 `발행일` 칼럼으로 저장하도록 수정. 본문을 다시 받지 않고 기존 CSV 에 발행일만 채우는 `--add-date` 모드 추가

### 원본 대비 변경사항

| 파일 | 구분 | 원본 | 변경 후 |
|------|------|------|---------|
| `Claude outputs/naver_company_news.py` (미추적 파일) | 수정 | 칼럼 제목·본문·원본링크·키워드, `pubDate` 버림 | 칼럼에 `발행일` 추가(원본링크와 키워드 사이), `to_kst()`·`add_dates()` 추가, `--add-date <CSV>` 실행 모드 |
| `company_news_20261113.csv` | 변경 없음 | 1,368건, 4칼럼 | (사용자가 `--add-date` 실행 시 5칼럼으로 덮어씀) |

```diff
-COLUMNS = ["제목", "본문", "원본링크", "키워드"]
+COLUMNS = ["제목", "본문", "원본링크", "발행일", "키워드"]
-            articles[link] = {"제목": title, "원본링크": link,
+            articles[link] = {"제목": title, "원본링크": link, "발행일": to_kst(it.get("pubDate")),
+def add_dates(filename):  # API 를 기업당 1,000건까지 다시 검색해 원본링크로 발행일 매칭, 빈칸만 채움
```

- **비고**: 실제 API 호출은 하지 않음(키 없음). 가짜 API 응답과 CSV 사본으로 검증 — 날짜 변환(UTC→KST), 칼럼 순서, 본문 불변, 매칭 실패 건 빈칸, 재실행 시 기존 값 유지 확인. 최신순 검색이라 오래된 기사는 날짜를 못 찾을 수 있음.

## 2026-11-13 — 네이버 API 대상 5개사 기사 수집 코드 추가

- **브랜치**: `main`
- **버전**: 기준 `13efd42` → 결과 미커밋
- **요청 내용**: 5개사 기사를 네이버 API로 수집해 제공 뉴스와 같은 칼럼(제목·본문전문·원문URL·발행일·매체명·문서종류·수집키워드)의 CSV로 저장
- **진행 사항**: `collect/collect_news_naver.py` 새로 작성. 기업별로 최신순·정확도순 각 최대 1,000건 검색 → 제목·요약에 기업명(`COMPANY_PATTERNS`)이 있고 DB 기간(2023-10-19~2026-10-19) 안의 기사만 남김 → 원문URL 기준 중복 합침 → 네이버 뉴스 페이지(없으면 원문)에서 본문·매체명 추출. 본문은 `_pages.jsonl` 에 캐시해 이어받기

### 원본 대비 변경사항

| 파일 | 구분 | 원본 | 변경 후 |
|------|------|------|---------|
| `collect/collect_news_naver.py` | 추가 | (없음) | 네이버 API 5개사 수집 → `data/raw/news_naver/naver_company_YYYYMMDD.csv` (7칼럼, utf-8-sig) |
| `.env.example` | 수정 | DART·Anthropic 키 2개 | `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` 추가 |
| `README.md` | 수정 | 5-1 다음 6. 통합본 | 5-2. 네이버 수집 단계 추가 |

```diff
# .env.example
 DART_OPEN_API=
 ANTHROPIC_API_KEY=
+NAVER_CLIENT_ID=
+NAVER_CLIENT_SECRET=
```

- **비고**: 실제 API·페이지 호출은 하지 않음. 가짜 API 응답·페이지로 검증 — KST 변환, 기간 밖·기업명 없는 기사 제외, 원문URL 중복 시 수집키워드 합침, 네이버 로고 alt / og:site_name 매체명, 사진설명 제거, 7칼럼 순서. 네이버 페이지의 언론사명 위치(`.media_end_head_top_logo img`)는 실제 페이지로 확인 필요. API 호출은 5개사 × 2정렬 × 10회 = 최대 100회. 기존 `Claude outputs/naver_company_news.py`·`company_news_20261113.csv` 는 그대로 둠. 통합본(`build_cdmo_news.py`)에는 아직 합치지 않음.

## 2026-11-13 — 구글 뉴스(한국어) 본문 수집 코드 추가

- **브랜치**: `main`
- **버전**: 기준 `13efd42` → 결과 미커밋
- **요청 내용**: 제목만 있는 구글 뉴스 한국어 기사(기업명검색·CDMO검색)의 본문 수집 코드 작성
- **진행 사항**: `collect/collect_news_google_body.py` 추가 — 영어 본문 수집의 디코딩·추출(`process`)을 재사용. 대상은 통합본에 들어간 본문 없는 기업명검색·CDMO검색 기사 4,321건(`--all` 이면 원본 기간 내 4,537건). 공통 추출기에 `<br>` 로만 나뉜 국내 언론 본문용 마지막 단계(직속 글자가 가장 많은 블록) 추가. `build_cdmo_news.py` 가 한국어 본문을 기업명검색·CDMO검색 기사에 채우도록 수정

### 원본 대비 변경사항

| 파일 | 구분 | 원본 | 변경 후 |
|------|------|------|---------|
| `collect/collect_news_google_body.py` | 추가 | (없음) | 한국어 구글 뉴스 본문 수집 → `data/raw/news_body_ko/_bodies.jsonl` |
| `collect/collect_news_global_body.py` | 수정 | 문단 블록 단계에서 종료 | 문단 본문이 300자 미만이면 `text_block`(직속 텍스트 최대 블록) 시도 |
| `analysis/build_cdmo_news.py` | 수정 | 기업명검색·CDMO검색 `body=None` | `load_ko_bodies()`·`fill_bodies()` 로 본문·원문 URL 채움. CDMO검색 정렬을 본문 채우기 전 구글 링크 기준으로 고정 |
| `README.md` | 수정 | 5-1 다음 5-2 | 5-1-2 한국어 본문 수집 단계 추가 |

```diff
# analysis/build_cdmo_news.py (main)
-    for r in sorted(load_google(), key=lambda r: (r["published_at"], r["url"])):
+    ko_bodies = load_ko_bodies()
+    google = sorted(load_google(), key=lambda r: (r["published_at"], r["url"]))
+    for r in fill_bodies(google, ko_bodies):
-    raw = load_cdmo_raw()
+    raw = fill_bodies(sorted(load_cdmo_raw(), ...), ko_bodies)
-    for r in sorted(raw, key=lambda r: (r["published_at"], r["url"])):
+    for r in raw:  # 위에서 구글 링크 기준으로 정렬해 두었다
```

- **비고**: 네트워크 수집은 실행하지 않음. 오프라인 검증 — 대상 건수 4,321/4,537, `<br>` 본문 추출, 구독벽 미추출, `fill_bodies` 병합, 컴파일. 국내 언론사 사이트별 실제 추출 품질은 `--limit 10` 시험 수집으로 확인 필요. 본문이 채워지면 해당 기사의 CDMO 관련성·키워드 분류가 본문 기준으로 바뀔 수 있음.

## 2026-11-13 — [커밋] 해외(영어) 뉴스 본문 수집 결과 반영

- **브랜치**: `main`
- **버전**: 기준 `13efd42` → 결과 이 기록을 포함한 커밋
- **요청 내용**: 영어 본문 수집이 끝나면 영어 관련 변경만 커밋
- **진행 사항**: 영어 기사 803건(guid) 본문 수집 완료. 위 기록 중 영어 본문 수집 관련 변경만 커밋에 포함. 한국어 본문 수집(`collect_news_google_body.py`, `build_cdmo_news.py` 의 `load_ko_bodies`·`fill_bodies`, README 5-1-2)과 네이버 수집 코드는 커밋하지 않고 로컬에 남김(네이버는 사용하지 않기로 함)

### 원본 대비 변경사항

`git diff --cached --stat`: 5 files (코드 2, 문서 2, 데이터 1)

| 파일 | 구분 | 원본 | 변경 후 |
|------|------|------|---------|
| `collect/collect_news_global_body.py` | 추가 | (없음) | 구글 뉴스 링크 디코딩 + 본문 추출(JSON-LD → article → 긴 문단 블록 → `<br>` 텍스트 블록) |
| `data/raw/news_global/_bodies.jsonl` | 추가 | (없음) | 811줄 / 803 guid. ok 466, http_403 279(Fierce Pharma 194 등), short 47, http_401 6, http_429 2, fetch_fail 2, http_402 1. 성공 본문 평균 6,131자 |
| `analysis/build_cdmo_news.py` | 수정 | 해외검색 `body=None` | `load_global_bodies()` 로 성공 건 본문·원문 URL 채움 |
| `README.md` | 수정 | 5 → 6 | 5-1 영어 본문 수집 단계 추가 |
| `hanju.md` | 수정 | 빈 파일 | 이 세션 기록 |

- **비고**: 통합본(`03_CDMO_news_3y/`)과 DB 는 아직 다시 만들지 않음 → `build_cdmo_news.py` → `db/build_db.py` 재실행 필요(영어 기사 466건에 본문이 생겨 분류 결과가 바뀔 수 있음). 크롤링한 기사 본문의 저작권은 언론사에 있으므로 LLM 입력·공개 범위는 과제 기준 확인 필요. push 하지 않음(원격 main 에 `e2e09f2` 가 있어 pull 후 push).

## 2026-11-16 — 뉴스 본문 수집 되돌림 (제목 기반 분류로 전환)

- **브랜치**: `main`
- **버전**: 기준 `ba50d61` → 결과 (이 커밋)
- **요청 내용**: LLM 분류를 기사 제목만으로 하기로 해서 본문 수집을 쓰지 않음. 영어 본문 추가분을 원래 상태로 되돌리고 커밋
- **진행 사항**: `git revert --no-commit ba50d61` 로 영어 본문 수집 커밋의 코드·데이터를 되돌림. `hanju.md` 의 기존 기록은 규칙에 따라 유지. 커밋하지 않았던 한국어 본문 수집 코드(`collect_news_google_body.py`, `build_cdmo_news.py` 수정분, README 5-1-2)와 10건 테스트 결과(`data/raw/news_body_ko/`)는 삭제

### 원본 대비 변경사항

`git diff --cached --stat`: 4 files changed, 3 insertions(+), 1081 deletions(-)

| 파일 | 구분 | 원본 (`ba50d61`) | 변경 후 (`13efd42` 와 동일) |
|------|------|------|---------|
| `collect/collect_news_global_body.py` | 삭제 | 영어 기사 본문 수집 코드 | (없음) |
| `data/raw/news_global/_bodies.jsonl` | 삭제 | 811줄 / 803 guid, 본문 성공 466건 | (없음) |
| `analysis/build_cdmo_news.py` | 수정 | `load_global_bodies()` 로 해외검색 본문·원문 URL 채움 | 해외검색 `body=None` (원래대로) |
| `README.md` | 수정 | 5-1 영어 본문 수집 단계 있음 | 5-1 단계 제거 |

- **비고**: 통합본·DB 는 본문 반영 전 상태라 재생성 불필요. 검수 표본 추출 코드 `analysis/sample_review.py`(영어 50 + 한국어 50 제목, 기회/위험/중립 드롭다운 엑셀 `data/processed/review_sample/분류표본_영어50_한국어50.xlsx`)는 이 커밋에 넣지 않음. push 하지 않음(원격 main 에 `e2e09f2`, `51a648b` 가 있어 pull 후 push).

## 2026-11-16 — 이슈 급증 시점 분석 코드 커밋

- **브랜치**: `main`
- **버전**: 기준 `94d6796` → 결과 (이 커밋)
- **요청 내용**: 커밋되지 않았던 이슈 급증 시점 분석 코드를 커밋
- **진행 사항**: `analysis/issue_trend.py` 만 커밋. 내용이 같은 루트의 중복본 `issue_trend.py`(추적 안 됨)는 삭제. 커밋 전 팀원 브랜치·기록 파일 점검 — 같은 파일이나 급증 분석 코드는 없음(문서에 요구사항만 있음). 통합 DB로 실행해 동작 확인

### 원본 대비 변경사항

| 파일 | 구분 | 원본 | 변경 후 |
|------|------|------|---------|
| `analysis/issue_trend.py` | 추가 | (없음) | 기업별 일·주 기사량·공시 건수 집계, 급증 구간 탐지(직전 28일 평균·표준편차 기준 z ≥ 3 이고 하루 5건 이상, 2일 이내 급증일은 한 구간), 구간별 대표 기사 제목 3개와 앞뒤 3일 공시. 팀원 수집분(`origin='team'`)은 기본 제외 |

| 실행 결과 (`data/processed/issue_trend/`, 커밋 안 함) | 기사 | 공시 | 급증 구간 |
|------|------|------|------|
| 삼성바이오로직스 | 1,381 | 332 | 26 |
| SK바이오사이언스 | 607 | 167 | 17 |
| 에스티팜 | 476 | 189 | 13 |
| 프레스티지바이오로직스 | 339 | 95 | 0 |
| 바이넥스 | 131 | 84 | 1 |

- **비고**: 결과 파일(spikes.csv, daily/weekly_counts.csv, png)은 `.gitignore` 대상이 아니지만 요청 범위가 코드라 커밋하지 않음. `analysis/sample_review.py`·검수 표본 엑셀도 커밋하지 않음. push 하지 않음.

## 2026-11-16 — 감성 분류 표본 B 라벨 파일 추가

- **브랜치**: `main`
- **버전**: 기준 `58eb0b2` (원격 main `abd9f05` 병합 포함) → 결과 (이 커밋)
- **요청 내용**: B 담당으로 라벨을 단 표본 파일을 push
- **진행 사항**: 엑셀이 UTF-16 탭 구분 텍스트(`sentiment_sample_b.csv.txt`)로 저장한 파일을 팀 안내 형식(UTF-8 BOM CSV)으로 변환해 `data/eval/sentiment_sample_b.csv` 로 추가. 원본 `sentiment_sample.csv` 와 셀 단위로 대조해 `annotator_b` 외 모든 셀이 같음을 확인. 커밋 전 팀원 브랜치·기록 점검 — `data/eval/` 에 다른 라벨 파일 없음. 이전 세션의 이슈 급증 분석 커밋(`67a6588`)·원격 main 병합 커밋도 함께 push. 앞서 만든 영어50·한국어50 제목 표본(`analysis/sample_review.py`, 커밋 안 함)은 팀 표본을 쓰기로 해 삭제

### 원본 대비 변경사항

| 파일 | 구분 | 원본 | 변경 후 |
|------|------|------|---------|
| `data/eval/sentiment_sample_b.csv` | 추가 | (없음) | `sentiment_sample.csv` 와 같은 180행 × 16열, `annotator_b` 만 채움: 기회 113 · 중립 46 · 위험 21. `annotator_a`·`label_final`·`note` 는 빈칸 |

- **비고**: 공유 저장소에 올라가 A 담당이 라벨링 전에 B 답을 볼 수 있음(사용자 확인 후 진행). A 라벨이 끝나면 A 파일에 `annotator_b` 를 붙여 `label_final` 합의 후 `sentiment_sample.csv` 를 교체해야 함. 엑셀에 열려 있던 `sentiment_sample_b.csv.txt` 와 `data/processed/review_sample/` 엑셀은 잠겨 있어 지우지 못함(커밋 안 함).
