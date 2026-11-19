# UI 명세

> **상태:** 🔶 초안(2026-11-17) — 디자인 토큰·테마(라이트/다크), 공통 컴포넌트, 사이드바 필터, S0~S6 컴포넌트, 표시 규칙·안내 문구, AC 추적표 작성. [INFORMATION_ARCHITECTURE](INFORMATION_ARCHITECTURE.md) 8절 U1~U5는 "제안"대로 적고 해당 위치에 **팀 확인 전(U#)** 을 표시 · **최종 갱신:** 2026-11-19 (main 코드에 맞춤: 2절 테마·CSS를 DESIGN.md 리디자인 값으로, 3절 모듈 현황, 5-1 S0 결론 띠·지표·카드, 5-2 S1 토글 삭제·부상 이슈 구현, S2 번역·S3 태깅·S4 금액·S6 예시/근거 없음 표시, 9절 AC 상태, 10-2 Q4·Q5·Q6·Q16·Q18 해결; 앞서 4-1·4-4절 기업·카테고리 필터를 체크박스 드롭다운으로, 한국어 기간 빠른 선택 추가; 5-6절 S5-K 연결 없는 기사 비율 — Q12 기사 × 기업 단위로 해결)
> **원본:** 없음 (새로 작성). 근거: [PRD](../02_product-requirements/PRD.md) 2·3·4·5절, [ACCEPTANCE_CRITERIA](../02_product-requirements/ACCEPTANCE_CRITERIA.md), [INFORMATION_ARCHITECTURE](INFORMATION_ARCHITECTURE.md), [WIREFRAME](WIREFRAME.md), [NEWS_DISCLOSURE_MATCHING](../04_ai/NEWS_DISCLOSURE_MATCHING.md) 3·4·5절, [AI_EVALUATION](../04_ai/AI_EVALUATION.md) 4·6절, [eda_report](../eda_report.md) 4·6·7절, `rag/qa.py`, 설치된 `streamlit==1.67.0`·`plotly==7.1.0`
> **관련 문서:** [masterplan](../masterplan.md) · [INFORMATION_ARCHITECTURE](INFORMATION_ARCHITECTURE.md) · [WIREFRAME](WIREFRAME.md) · [PRD](../02_product-requirements/PRD.md) · [ACCEPTANCE_CRITERIA](../02_product-requirements/ACCEPTANCE_CRITERIA.md) · [TECH_STACK](../06_technical/TECH_STACK.md)

---

## 1. 이 문서가 다루는 것

화면 요소의 **동작·표시 규칙**을 정한다. 화면 목록·계층·이동 경로는 [INFORMATION_ARCHITECTURE](INFORMATION_ARCHITECTURE.md)(이하 IA), 화면 안의 배치는 [WIREFRAME](WIREFRAME.md)(이하 WF)가 정하고, 이 문서는 그 배치를 Streamlit·Plotly로 구현할 때 필요한 값(위젯 종류, 입력 데이터, 집계, 색, 문구, 상태)을 정한다.

| 문서 | 정하는 것 | 이 문서와의 관계 |
|---|---|---|
| [PRD](../02_product-requirements/PRD.md) | 기능 F1~F8, 비기능 N1~N7, 데이터 해석 규칙(4절), 한계(5절) | 4절 규칙은 6절 표시 규칙·9절 추적표에, 5절 한계는 7절 문구에 반영 |
| [ACCEPTANCE_CRITERIA](../02_product-requirements/ACCEPTANCE_CRITERIA.md) | AC-01~18, 2~5절 점검 항목 | 9절에서 항목마다 이 문서의 위치를 연결 |
| [IA](INFORMATION_ARCHITECTURE.md) | 화면 S0~S6, 필터 F7 적용 범위, 이동 L1~L9, U1~U5 | 4절 필터·5절 화면 명세가 따른다 |
| [WF](WIREFRAME.md) | 화면별 배치, 공통 상태(4절) | 5절 컴포넌트 ID가 WF 요소에 하나씩 대응 |
| [TECH_STACK](../06_technical/TECH_STACK.md) | 버전·도구 (현재 작성 전) | 버전은 `requirements.txt`·`.venv` 실측값(`streamlit==1.67.0`, `plotly==7.1.0`)을 썼다 |

**기호** (WF 1절과 같음): `[F#]` 기능, `(US-##)` 스토리, `{AC-##}` 검수 기준, `⏳` 데이터 없음(준비 중). 추가 기호:

- **팀 확인 전(U#)** — IA 8절 결정 필요 항목의 "제안"을 따른 부분. 팀이 대안을 고르면 그 부분만 바꾼다.
- **미결 Q#** — 이 문서를 쓰며 새로 찾은 미결 사항. 10절에 모았다. 구현은 표에 적은 "임시 동작"으로 한다.
- **준비** 열 — 2026-11-19 main 코드 기준 구현 상태("구현됨"). 남은 준비 중 항목은 없다 — S2-C3 해외 CDMO 언급 수(Q7)는 2026-11-19 화면에서 뺐다.
- **R1~R5** — [PRD](../02_product-requirements/PRD.md) 4절 "데이터 해석 규칙" 표의 5행을 이 문서에서 위에서부터 붙인 번호다(PRD에는 번호가 없다). R1 중복(`dup_of`) 제외, R2 기업 단위는 `match_field IN ('title','body')`, R3 본문 기반 분석은 `provided`·`team` 범위 표시, R4 `cdmo_kw_basis='query'` 신뢰도 낮음, R5 기사량은 `origin` 별 해석. 9-4절에 위치를 모았다.

**용어**

| 용어 | 뜻 |
|---|---|
| 적용 필터 | `st.session_state["filters"]` 에 들어 있는 기간·기업·카테고리 값. 모든 차트가 이 값으로 데이터를 거른다 |
| 5개사 | 삼성바이오로직스, SK바이오사이언스, 프레스티지바이오로직스, 에스티팜, 바이넥스 ([PRD](../02_product-requirements/PRD.md) 1절, IA 4-1절 순서) |
| 카테고리 | CDMO 키워드 6개 (`news_cdmo_keywords.keyword` 값 그대로). 상위 분류 `category` 는 `규제 및 정책`(규제·정책, 지정학) / `기술 및 트렌드`(모달리티) / `시장 및 경쟁`(생산능력, 수주, 경쟁 구도) ([news_sort](../news_sort.md) 11~18행) |
| 임시 이슈 | CDMO 키워드 × 기업 × 월. 이슈 단위 집계 전 L4·S5에서 쓰는 단위 (NEWS_DISCLOSURE_MATCHING D8, 팀 확정) |
| 주요 4분류 | 공시 `event_class` 중 수주·증설·M&A·구조개편·자금조달 ({AC-11}) |
| 표시용 제목 | `news_clean.title_clean` (없으면 `news.title`). DB 스키마가 화면 표시용으로 둔 정제 텍스트 |

## 2. 디자인 토큰과 테마

원칙 (2026-11-19 갱신, 루트 `DESIGN.md` 리디자인): 테마로 되는 값은 `.streamlit/config.toml`(2-6절)과 `dashboard/core/theme.py`(2-7절)에 둔다. 테마로 안 되는 부분만 CSS로 넣는다 — `dashboard/core/style.py`(카드 흰 면·그림자, 버튼 눌림·보조 버튼 초록 테두리, h1 제목 색, S0 결론 띠, 예시 질문 버튼, 폼 제출 버튼 줄바꿈 방지)와 `dashboard/app.py`(사이드바 맨 위 제목, 달력 머리 순서·영어 빠른 선택 숨김). CSS 색 값도 `theme.TOKENS` 에서 가져온다. 색은 라이트·다크 두 값을 따로 정하고, 다크 값은 라이트 값을 뒤집은 것이 아니라 어두운 배경에 맞춰 다시 고른 값이다.

### 2-1. UI 색 토큰

| 토큰 | 용도 | 라이트 | 다크 | config.toml 키 |
|---|---|---|---|---|
| `bg` | 본문 배경 (크림 캔버스 / House Green) | `#F2F0EB` | `#1E3932` | `backgroundColor` |
| `bg-subtle` | 카드·지표·입력칸 면, 표 머리 | `#FFFFFF` | `#2B5148` | `secondaryBackgroundColor` (표 머리 `dataframeHeaderBackgroundColor` 는 라이트 `#EDEBE9`, 다크 `#2B5148`) |
| 사이드바 | 사이드바 배경 | `#EDEBE9` | `#17302A` | `sidebar.backgroundColor` |
| `text` | 본문 글자 | `#1E1E1E` | `#F2F0EB` | `textColor` |
| `text-muted` | 보조 글자(차트 축 눈금, 출처 줄) | `#5C5A55` | `#B9C8C2` | (없음 — `theme.py` 에서 Plotly에 적용) |
| `border` | 테두리, 구분선, 차트 축선 | `#D6DBDE` | `#3E6359` | `borderColor` |
| `grid` | 차트 격자선 (장식용, 3:1 대상 아님) | `#E3E0D8` | `#2F5047` | (없음 — `theme.py`) |
| `primary` | 주 버튼 배경, 선택 상태 (Green Accent) | `#00754A` | `#00754A` | `primaryColor` |
| `link` | 링크 글자 (밑줄 없음) | `#00754A` | `#D4E9E2` | `linkColor`, `linkUnderline = false` |
| `heading` | h1 제목 색 (`style.py`) | `#006241` | `#D4E9E2` | (없음 — `theme.py`) |
| `band` / `band-text` / `band-muted` | S0 결론 띠 면 / 글자 / 보조 글자 (`style.py`) | `#1E3932` / `#FFFFFF` / `#D4E9E2` | `#0F241F` / `#FFFFFF` / `#B9C8C2` | (없음 — `theme.py`) |
| `badge-blue` 글자/배경 | 기회·직접 배지 | `#1D5FB3` / `#E8F1FC` | `#A9CDF5` / `#1D3A4A` | `blueTextColor` / `blueBackgroundColor` |
| `badge-red` 글자/배경 | 위험 배지 | `#A92A2A` / `#FCEBEB` | `#F2A0A0` / `#4A2A27` | `redTextColor` / `redBackgroundColor` |
| `badge-gray` 글자/배경 | 중립·정정·번역·신뢰도 낮음·AI 생성 배지 | `#4A4A48` / `#EDEBE9` | `#D0DAD6` / `#2B5148` | `grayTextColor` / `grayBackgroundColor` |
| `badge-green` 글자/배경 | 지표 증감 배지 등 Streamlit 초록 요소 | `#006241` / `#D4E9E2` | `#D4E9E2` / `#24463E` | `greenTextColor` / `greenBackgroundColor` |

- 2026-11-17 초안 값(흰 배경 `#FFFFFF`·`#0E1117`, primary `#1F4E79`)은 2026-11-19 `DESIGN.md` 리디자인에서 위 값으로 바뀌었다. 데이터 색(2-2절)은 바꾸지 않았다. 2-3절 대비 표는 데이터 색 기준이며, 새 배경색으로 다시 계산하지 않았다(미결 Q15).
- EDA 차트의 기본 막대 색 `#1F4E79` 는 `series-volume` 토큰(다크 `#6FA8DC`)으로 남겼다.
- `st.warning`(주황·노랑 계열), 초록·보라 계열 색은 Streamlit 기본값을 쓴다(키를 지정하지 않음).

### 2-2. 데이터 색

글자는 데이터 색을 쓰지 않는다. 값·라벨·범례 글자는 `text`·`text-muted` 이고, 색은 그 옆의 막대·선·점·배지 배경만 칠한다. 예외: 히트맵 칸 안 글자는 칸 색 위에 놓이므로 검정·흰색 중 대비가 맞는 값을 쓴다(2-3절, 5-4절 S3-C2).

**기업 색 (고정 매핑)** — 기업이 색으로 구분되는 모든 차트에서 같은 색을 쓴다. 필터로 기업 수가 바뀌어도 남은 기업의 색은 바뀌지 않는다.

| 순서 | 기업 | 라이트 | 다크 | 계열 |
|---|---|---|---|---|
| 1 | 삼성바이오로직스 | `#513BB2` | `#6148D1` | 남보라 |
| 2 | SK바이오사이언스 | `#049A78` | `#12AF7D` | 청록 |
| 3 | 프레스티지바이오로직스 | `#9A1B71` | `#B6127D` | 자주 |
| 4 | 에스티팜 | `#A06B01` | `#946823` | 황토 |
| 5 | 바이넥스 | `#AF54D3` | `#B37BCC` | 연보라 |

- 기회(파랑)·위험(빨강)과 겹치지 않도록 파랑·빨강·주황 계열을 뺐고, 빨강·초록 쌍이 없다. 5색 모두 서로 어느 쌍이든 색각 이상 시뮬레이션에서 구분된다(2-3절).

**감성 색 (기회/위험/중립)**

| 라벨 | 라이트 | 다크 | 글자 표시(배지) | 기호 |
|---|---|---|---|---|
| 기회 | `#2A78D6` | `#3987E5` | `:blue-badge[▲ 기회]` | ▲ |
| 위험 | `#E34948` | `#E66767` | `:red-badge[▼ 위험]` | ▼ |
| 중립 | `#858C97` | `#5F6673` | `:gray-badge[● 중립]` | ● |

- 파랑↔빨강은 색각 이상에서도 구분되는 대비 쌍이다. 라벨 문구와 기호를 항상 함께 둬서 색만으로 판단하지 않게 한다 (8절).
- 한국 증시 관례(상승 빨강·하락 파랑)와 반대로 읽힐 수 있다 (미결 Q14).

**범주 색 (기업이 아닌 명목 계열)** — 출처(`origin`), 공시 분류(`event_class`), S3 키워드 2계열에 쓴다. `config.toml` 의 `chartCategoricalColors` 에도 이 순서로 넣는다.

| 슬롯 | 라이트 | 다크 | 출처(S1 누적 막대) | 공시 분류(S4·S5) | S3 키워드 |
|---|---|---|---|---|---|
| 1 | `#716DF6` | `#737AFC` | 제공 | 수주 | CDMO 모달리티 |
| 2 | `#A20519` | `#BA2B2E` | 키워드 검색(팀원수집, S1에서는 늘 제외) | 증설 | — |
| 3 | `#11598F` | `#0A67A9` | 기업명검색 | M&A·구조개편 | CDMO 생산능력 |
| 4 | `#B0698C` | `#EA589A` | CDMO검색 | 자금조달 | — |
| 5 | `#C68206` | `#D79628` | 해외검색 | — | — |
| 기타 | 중립 회색(감성 중립과 같은 값) | | — | 주요 4분류 밖 공시 | — |

- 출처 이름은 화면용 한글명(제공·키워드 검색·기업명검색·CDMO검색·해외검색)을 쓴다. `team` 은 `eda.py`·문서에서는 "팀원수집", 화면에서는 2026-11-19부터 "키워드 검색"(`data.ORIGIN_KO`).
- 슬롯 5는 처음에 초록(`#507B07` / `#497C14`)으로 정했으나, S1 출처 누적 막대에서 5계열을 모두 색으로 구분해야 하는데 슬롯 2(빨강)와의 녹색 약시 거리가 라이트 7.0·다크 0.6이라 호박색으로 바꿨다(2-3절).
- S4 화면에는 기업 색(묶음 막대)과 범주 색(타임라인)이 함께 나온다. 두 팔레트 사이 최소 거리는 2-3절에 적었고, 타임라인은 y축 위치로도 분류를 구분한다.

**단일 계열·순차 색**

| 토큰 | 용도 | 라이트 | 다크 |
|---|---|---|---|
| `series-volume` | 기사량 단일 계열(S1 전체·키워드 소형 다중 차트, S5 기사량 막대) | `#1F4E79` | `#6FA8DC` |
| `mark-spike` | 급증 시점 표시(세로 점선·● 표식) | `text` 값 | `text` 값 |
| 순차 10단계 | 히트맵(S3-C2) | `#CDE2FB` → `#0D366B` | `#0D366B` → `#CDE2FB` (낮은 값이 배경 쪽) |

순차 10단계 값은 2-6절 `chartSequentialColors` 에 있다.

### 2-3. 대비·색각 검증 결과

2026-11-17 계산. 글자 대비는 WCAG 2.x 상대 휘도 공식(`.venv/Scripts/python.exe -I` 로 계산), 차트 색은 OKLab 거리(×100)와 Machado(2009) 색각 이상 시뮬레이션(적색·녹색 약시 중 작은 값)으로 검사했다. 기준: 글자 4.5:1 이상, 차트 표식 3:1 이상, 색각 이상 시뮬레이션 거리 8 이상(6~8은 보조 표시가 있을 때만 허용), 정상 시각 거리 15 이상.

**글자 대비 (WCAG)**

| 글자 → 배경 | 라이트 | 다크 | 판정 |
|---|---|---|---|
| `text` → `bg` | 16.51 | 15.54 | 통과 |
| `text` → `bg-subtle` | 15.25 | 13.54 | 통과 |
| `text-muted` → `bg` | 6.15 | 8.08 | 통과 |
| `text-muted` → `bg-subtle` | 5.68 | 7.04 | 통과 |
| `link` → `bg` | 8.66 | 9.10 | 통과 |
| `link` → `bg-subtle` | 8.00 | 7.93 | 통과 |
| 흰 글자 → `primary` (주 버튼) | 8.66 | 5.22 | 통과 |
| `badge-blue` 글자 → 배경 | 5.51 | 8.01 | 통과 |
| `badge-red` 글자 → 배경 | 5.97 | 7.52 | 통과 |
| `badge-gray` 글자 → 배경 | 6.79 | 8.42 | 통과 |
| S3-C2 히트맵 칸 글자: 검정 `#000000` → 순차 1~7단계 칸(`#CDE2FB`~`#2A78D6`) | 15.87 ~ 4.76 | 같음(같은 칸 색) | 통과 |
| S3-C2 히트맵 칸 글자: 흰색 `#FFFFFF` → 순차 8~10단계 칸(`#256ABF`~`#0D366B`) | 5.39 ~ 11.95 | 같음 | 통과 |

- 히트맵 칸 글자는 칸 색에 따라 검정·흰색을 고른다(5-4절 S3-C2). `text` 값을 그대로 쓰면 라이트 `#1A1F29` 는 7~10단계 칸에서 3.74·3.06·2.04·1.38, 다크 `#E6E9EF` 는 1~8단계 칸에서 1.09~4.44로 4.5:1에 못 미친다. 7단계 칸 `#2A78D6` 은 `#1A1F29`(3.74)·흰색(4.42) 모두 미달이라 검정(4.76)을 쓴다.

**테두리 대비 (참고, 3:1 기준 미달)**

| 대상 | 라이트 | 다크 | 판정 |
|---|---|---|---|
| `border` → `bg` | 1.41 | 1.56 | 3:1 미달 |
| `border` → `bg-subtle` | 1.30 | 1.36 | 3:1 미달 |
| 입력 위젯 채움(`bg-subtle`) → `bg` | 1.08 | 1.15 | 3:1 미달 |

- `border` 는 구분선·차트 축선·카드 테두리에 쓰는 장식용 값으로 두고 3:1 대상에서 뺀다(`grid` 와 같음). 다만 입력 위젯(`showWidgetBorder = true`)은 이 테두리가 거의 유일한 경계라, 위젯 위의 라벨 글자로 위젯을 알아볼 수 있는지 실행 화면에서 확인한다(미결 Q15). 부족하면 `border` 를 3:1 이상으로 진하게 바꾸고 이 표를 다시 계산한다.

**차트 표식 대비 (배경 `bg` 기준, 3:1 이상)**

| 팔레트 | 라이트 | 다크 |
|---|---|---|
| 기업 5색 | 8.02 / 3.56 / 7.58 / 4.57 / 4.17 | 3.02 / 6.71 / 3.03 / 3.84 / 5.96 |
| 감성 기회 / 위험 / 중립 | 4.42 / 3.95 / 3.39 | 5.19 / 5.85 / 3.27 |
| 범주 슬롯 1~5 | 4.02 / 8.16 / 7.37 / 4.00 / 3.18 | 5.33 / 3.13 / 3.17 / 5.72 / 7.45 |
| `series-volume` | 8.66 | 7.48 |
| `primary` (선택 표시 등 비글자 요소) | 8.66 | 3.62 |

**구분 가능성 (OKLab 거리 ×100)**

| 검사 | 라이트 | 다크 | 판정 |
|---|---|---|---|
| 기업 5색, 모든 쌍 — 색각 이상 최소 | 10.9 (바이넥스↔삼성) | 11.7 (바이넥스↔SK) | 통과 |
| 기업 5색, 모든 쌍 — 정상 시각 최소 | 17.3 (바이넥스↔프레스티지) | 19.3 (바이넥스↔삼성) | 통과 |
| 감성 3색, 모든 쌍 — 색각 이상 최소 | 11.4 (위험↔중립) | 10.0 (위험↔중립) | 통과 |
| 감성 3색, 모든 쌍 — 정상 시각 최소 | 15.7 (중립↔기회) | 17.9 (중립↔기회) | 통과 |
| 기회↔위험 (정상 / 색각 이상) | 32.3 / 21.6 | 29.0 / 19.2 | 통과 |
| 범주 5색, 모든 쌍(S1 출처 누적 막대, 범례로 5계열 구분) — 색각 이상 / 정상 | 11.3 (슬롯 3↔4) / 17.0 (슬롯 4↔5) | 8.4 (슬롯 3↔4) / 17.1 (슬롯 1↔3) | 통과 |
| 범주 슬롯 1~4, 모든 쌍(공시 분류) — 색각 이상 / 정상 | 11.3 / 18.9 | 8.4 / 17.1 | 통과 |
| 범주 슬롯 1~4 ↔ 중립 회색(주요 4분류 밖 공시, S4-C2·S5-C1) — 색각 이상 최소 / 정상 최소 | 2.5 (슬롯 4, 녹색 약시) / 10.6 (슬롯 4) | 8.2 (슬롯 4, 적색 약시) / 10.9 (슬롯 3) | 기준 미달. 두 차트는 y축 위치(분류 이름)가 주 인코딩이고 색은 보조이므로 허용 (8절) |
| 기업 색 ↔ 기회·위험, 정상 시각 최소 | 15.3 (삼성↔기회) | 15.1 (삼성↔기회) | 통과 (15 이상) |
| 기업 색 ↔ 기회·위험, 색각 이상 최소 | 3.7 (바이넥스↔기회) | 4.2 (바이넥스↔기회) | 같은 차트에 함께 쓰지 않으므로 허용. 감성은 항상 라벨·기호와 함께 표시 |
| 기업 색 ↔ 범주 색, 정상 시각 최소 | 9.3 (에스티팜↔슬롯 5) | 12.2 (바이넥스↔슬롯 1) | 같은 차트에 함께 쓰지 않음. S4에서는 위치(x·y축)로도 구분 |

- 중립 회색은 의도적으로 채도가 없다(검사 도구의 채도 하한 검사는 중립에 적용하지 않음).
- 색을 바꾸면 이 표를 다시 계산한다. 같은 검사를 데이터 시각화 팔레트 검사 스크립트(`validate_palette.js`, OKLab·Machado 기준)로도 확인했다.

### 2-4. 타이포그래피

| 역할 | Streamlit 요소 | 크기 | 굵기 | 비고 |
|---|---|---|---|---|
| 화면 제목 | `st.title` (h1) | 2rem (32px) | 700 | `headingFontSizes[0]` |
| 결론 질문 줄 | `st.subheader` (h3) | 1.25rem (20px) | 600 | |
| 차트·목록 제목 | `st.markdown("#### …")` (h4) | 1.125rem (18px) | 600 | |
| 본문 | `st.markdown`, `st.write` | 1rem (16px) | 400 | `baseFontSize = 16` |
| 보조 글(필터 상태 줄, 출처 줄, 안내 문구) | `st.caption` | Streamlit 기본(약 0.875rem) | 400 | 색은 Streamlit이 정함 (대비 미확인, 미결 Q15) |
| 지표 값 | `st.metric` 값 | 1.75rem (28px) | Streamlit 기본 | `metricValueFontSize` |
| 차트 축 눈금·범례·주석 | Plotly | 12px | 400 | `text-muted`(눈금), `text`(범례) |
| 차트 호버 | Plotly | 13px | 400 | |

- 글꼴: `Noto Sans KR`(Google Fonts) → 실패 시 시스템 `sans-serif`. 오프라인 실행이면 대체 글꼴로 보인다. Plotly 글꼴 목록은 `"Noto Sans KR", "Malgun Gothic", "Apple SD Gothic Neo", sans-serif`.
- 숫자를 세로로 비교하는 표(`st.dataframe`)는 숫자 열을 오른쪽 정렬한다(`column_config.NumberColumn` 기본).

### 2-5. 간격·라운드·테두리·크기

| 토큰 | 값 | 적용 |
|---|---|---|
| 간격 단위 | 4px 배수 (4·8·12·16·24·32) | 직접 px를 쓰지 않고 Streamlit `gap` 값으로: 같은 묶음 안 `gap="small"`, 영역 사이 `gap="medium"`, ①~④ 영역 사이 `st.divider()` |
| 라운드 | `baseRadius = "0.75rem"` (12px), `buttonRadius = "full"` (알약) | 카드·입력창 12px, 버튼 알약 (`DESIGN.md` 4절) |
| 테두리 | 1px `border` 색, `showWidgetBorder = true`, `showSidebarBorder = false` | 카드는 `ui.card()` (= `st.container(border=True, key="card_N")`). 라이트에서는 테두리 대신 그림자, 다크에서는 테두리 (`style.py`) |
| 그림자 | 카드·지표: `0 0 0.5px rgba(0,0,0,0.14), 0 1px 1px rgba(0,0,0,0.24)` (라이트만) | `style.py` (`DESIGN.md` 6절) |
| 차트 높이 | 주 차트 360px, 보조 차트 280px, 소형 다중 차트 한 칸 200px | `st.plotly_chart(height=…)` 대신 `fig.update_layout(height=…)` |
| 차트 여백 | `margin = l 8, r 8, t 8, b 8` (px) + 축 글자 자동 | 차트 제목은 Plotly title이 아니라 h4로 위에 둔다 |
| 표식 | 선 2px, 점 8px(급증 ● 10px), 누적 막대 조각 사이 배경색 1px 선, 막대 간격 `bargap 0.25`·`bargroupgap 0.1` | |

### 2-6. `.streamlit/config.toml`

저장소 루트에 둔다(`streamlit run dashboard/app.py` 를 루트에서 실행할 때 읽힌다). 아래는 2026-11-19 main 의 파일 그대로다 (`DESIGN.md` 리디자인. 2026-11-17 초안 값은 git 기록 참고).

```toml
# 대시보드 테마 — 루트 DESIGN.md(따뜻한 크림 캔버스 · 초록 4단계 · 알약 버튼 · 12px 카드)를 따름 (starbucks-design 브랜치).
# 차트 데이터 색(chartCategoricalColors·chartSequentialColors)은 UI_SPECIFICATION 2-6절 값 그대로 둔다 (색각 대비 검증값).
# 테마로 안 되는 부분(카드 그림자·버튼 눌림·제목 색·S0 결론 띠)은 dashboard/core/style.py 의 CSS.
# 저장소 루트에서 `streamlit run dashboard/app.py` 로 실행할 때 읽힌다.
[theme]
font = "Noto Sans KR:https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700&display=swap, sans-serif"
baseFontSize = 16
headingFontSizes = ["2rem", "1.5rem", "1.25rem", "1.125rem", "1rem", "0.875rem"]
headingFontWeights = [600, 600, 600, 600, 600, 600]   # DESIGN.md 3절: 위계는 크기보다 굵기·색으로
metricValueFontSize = "1.75rem"
baseRadius = "0.75rem"        # 카드 12px
buttonRadius = "full"         # 모든 버튼 알약 모양 (DESIGN.md 4절)
showWidgetBorder = true
showSidebarBorder = false
linkUnderline = false

[theme.light]
primaryColor = "#00754A"                  # Green Accent — 버튼·선택
backgroundColor = "#F2F0EB"               # Neutral Warm — 페이지 캔버스
secondaryBackgroundColor = "#FFFFFF"      # 입력칸·카드 면
textColor = "#1E1E1E"                     # Text Black (검정 87%)
borderColor = "#D6DBDE"
linkColor = "#00754A"
dataframeHeaderBackgroundColor = "#EDEBE9" # Ceramic
greenBackgroundColor = "#D4E9E2"          # Green Light
greenTextColor = "#006241"                # Starbucks Green
blueBackgroundColor = "#E8F1FC"
blueTextColor = "#1D5FB3"
redBackgroundColor = "#FCEBEB"
redTextColor = "#A92A2A"
grayBackgroundColor = "#EDEBE9"
grayTextColor = "#4A4A48"
chartCategoricalColors = ["#716DF6", "#A20519", "#11598F", "#B0698C", "#C68206"]
chartSequentialColors = ["#CDE2FB", "#9EC5F4", "#86B6EF", "#6DA7EC", "#5598E7", "#3987E5", "#2A78D6", "#256ABF", "#184F95", "#0D366B"]

[theme.light.sidebar]
backgroundColor = "#EDEBE9"               # Ceramic
secondaryBackgroundColor = "#FFFFFF"

[theme.dark]
primaryColor = "#00754A"
backgroundColor = "#1E3932"               # House Green
secondaryBackgroundColor = "#2B5148"      # Green Uplift — 입력칸·카드 면
textColor = "#F2F0EB"
borderColor = "#3E6359"
linkColor = "#D4E9E2"
dataframeHeaderBackgroundColor = "#2B5148"
greenBackgroundColor = "#24463E"
greenTextColor = "#D4E9E2"
blueBackgroundColor = "#1D3A4A"
blueTextColor = "#A9CDF5"
redBackgroundColor = "#4A2A27"
redTextColor = "#F2A0A0"
grayBackgroundColor = "#2B5148"
grayTextColor = "#D0DAD6"
chartCategoricalColors = ["#737AFC", "#BA2B2E", "#0A67A9", "#EA589A", "#D79628"]
chartSequentialColors = ["#0D366B", "#184F95", "#256ABF", "#2A78D6", "#3987E5", "#5598E7", "#6DA7EC", "#86B6EF", "#9EC5F4", "#CDE2FB"]

[theme.dark.sidebar]
backgroundColor = "#17302A"
secondaryBackgroundColor = "#1E3932"
```

- `[theme.light]`·`[theme.dark]` 는 `[theme]` 값을 확장한다(설치본 설명문). `base` 는 `[theme]` 에서만 쓸 수 있는 키이며 지정하지 않는다. 두 모드를 모두 정의했을 때 사용자 설정 메뉴의 밝기 전환 동작은 실행 화면에서 확인한다(미결 Q15).
- 헤딩 크기는 `[theme.sidebar]` 로 상속되지 않는다(설치본 설명문). 사이드바 헤딩은 Streamlit 기본 크기를 쓴다.

### 2-7. Plotly 템플릿과 적용 방법

`dashboard/core/theme.py` 에 있다.

| 이름 | 내용 |
|---|---|
| `TOKENS[mode]` | 2-1절 토큰 값 (`mode` = `"light"` / `"dark"`) |
| `COMPANY_COLOR[mode][기업명]` | 2-2절 기업 색 |
| `SENTIMENT_COLOR[mode][라벨]` | 2-2절 감성 색 |
| `ORIGIN_COLOR`, `EVENT_COLOR`, `KEYWORD_COLOR` | 2-2절 범주 색 매핑 (`EVENT_COLOR` 에 없는 분류는 중립 회색) |
| `current_mode()` | `st.context.theme.type` 값. 값이 없으면 `"light"`. 첫 접속·테마 전환 직후에는 틀릴 수 있다고 설치본 설명문에 적혀 있다(미결 Q15) |
| `style(fig, kind)` | 아래 레이아웃을 적용하고 `fig` 를 돌려준다. `kind` = `"time"`(시계열) / `"bar"` / `"scatter"` / `"heatmap"` |
| `show(fig, *, key, alt, on_select="ignore", selection_mode="points")` | `st.plotly_chart(fig, theme="streamlit", width="stretch", key=key, alt=alt, on_select=on_select, selection_mode=selection_mode, config=PLOTLY_CONFIG)` 를 부른다. 모든 차트는 이 함수로만 그린다 (설치본 `selection_mode` 기본값은 `("points", "box", "lasso")` 라 명시해 넘긴다) |

`style(fig, kind)` 가 정하는 값:

| 항목 | 값 |
|---|---|
| 배경 | `paper_bgcolor`·`plot_bgcolor` = 투명(`rgba(0,0,0,0)`) — 캔버스·카드 어느 쪽에 놓여도 바탕을 따른다 (2026-11-19) |
| 글꼴 | `font.family` 2-4절 목록, `font.size` 12, `font.color` = `text` |
| 격자 | 값 축(y)만 격자선 1px `grid`, 범주·시간 축(x)은 격자 없음. `zeroline` 끔. 축선 1px `border`, 눈금 글자 `text-muted` 12px |
| 범례 | 계열 2개 이상일 때만. 차트 위 왼쪽 가로 배치: `orientation="h"`, `x=0`, `xanchor="left"`, `y=1.02`, `yanchor="bottom"`, 범례 제목 없음 |
| 호버 | `kind="time"` 은 `hovermode="x unified"`, 그 밖은 `"closest"`. `hoverlabel` 배경 `bg-subtle`, 테두리 `border`, 글자 `text` 13px |
| 호버 형식 | 건수 `%{y:,}건`, 월 `%{x\|%Y-%m}`, 일 `%{x\|%Y-%m-%d}` (세로선 앞 역슬래시는 표 문법용이며 실제 코드에는 넣지 않는다), 비율 `%{y:.1f}%`. 계열 이름은 `<b>%{fullData.name}</b>` |
| 시간 축 눈금 | 월 단위 `tickformat="%Y-%m"`, 주·일 단위 `"%Y-%m-%d"` |
| 막대 | `bargap 0.25`, `bargroupgap 0.1`, 누적 막대는 `marker.line` 1px `bg` 색 |
| 높이·여백 | 2-5절 |
| 크기 고정 | `fig.update_layout(uirevision=key)` — 필터 변경 시 확대 상태를 유지하지 않고 다시 그리므로 `key` 에 적용 필터 해시를 포함 |

`PLOTLY_CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]}`.

- `theme="streamlit"` 은 배경·글꼴을 현재 Streamlit 테마에 맞추고(설치본 설명문: `chartCategoricalColors`·`chartSequentialColors`·글꼴 반영), `style()` 이 명시한 레이아웃 값과 트레이스 색이 그 위에 적용된다. 기업·감성처럼 고정 매핑이 있는 계열은 트레이스에 색을 직접 넣는다(`color_discrete_map`).
- 계열 4개 이하는 선 끝에 계열 이름을 직접 붙인다(범례와 함께). 모든 점에 숫자를 붙이지 않는다.
- 두 개의 y축(이중 축)은 쓰지 않는다. 단위가 다른 두 값은 위아래 부분 차트(`make_subplots(rows=2, shared_xaxes=True)`)로 나눈다.

## 3. 공통 레이아웃과 공통 컴포넌트

### 3-1. 앱 골격

| 파일 | 역할 | 현재 상태 |
|---|---|---|
| `dashboard/app.py` | `st.set_page_config(page_title="CDMO 이슈 대시보드", layout="wide", initial_sidebar_state="expanded")` → `ui.reset_cards()`·`style.inject()` → 사이드바 제목·달력 CSS → 사이드바 필터(4절) → `st.navigation(...).run()` | 있음 |
| `dashboard/core/ui.py` | 3-2절 공통 컴포넌트 | 있음 |
| `dashboard/core/filters.py` | 4절 필터 위젯·적용 함수 | 있음 |
| `dashboard/core/theme.py` | 2-7절 토큰·Plotly 스타일 | 있음 |
| `dashboard/core/style.py` | 2절 원칙의 CSS (`inject()`) | 있음 (2026-11-19) |
| `dashboard/core/data.py` | DB·CSV 읽기 (`st.cache_data`), 필터 적용 질의 | 있음 |
| `dashboard/views/s0_summary.py` ~ `s6_qa.py` | 화면 7개 | 있음 |

메뉴 (IA 3절): `st.navigation({"": [요약], "산업 흐름": [이슈·트렌드, 규제·정책, 기술·생산], "경쟁": [기업 비교], "근거 확인": [뉴스-공시 연계, 공시 Q&A]}, position="sidebar")`. 요약(S0)은 `st.Page(..., default=True)`. 사이드바 맨 위 문구는 "CDMO 이슈 대시보드" (WF 2절) — 메뉴 위에 CSS(`stSidebarNav::before`)로 붙이고, 사이드바 폭에 맞춰 한 줄로 보이게 글자 크기를 메뉴 폭에 비례(`10.8cqi`, 0.875~1.5rem)시킨다.

화면 공통 순서 (WF 2절): ① `ui.header` → ② `ui.kpis`(S0은 자체 머리·결론 띠 → `ui.kpis`, 5-1절) → ③ 본문 → ④ `ui.limits`. ①~② 와 ③ 사이, ③ 과 ④ 사이에 `st.divider()`.

### 3-2. 공통 컴포넌트

| 컴포넌트 | 입력 | 출력 | 사용 위젯 | 정상 표시 | 그 밖의 상태 |
|---|---|---|---|---|---|
| `ui.header(title, question, filters)` (현재 골격의 호출 형식 그대로) | 화면 이름, 핵심 질문, 적용 필터 dict | 없음 | `st.title`, `st.caption`, `st.subheader` | ① 제목 → 다음 줄 `현재 필터: <필터 상태 줄>` (4-5절) → ② 질문 1줄 | 필터 미설정(첫 실행 직후) — 기본값으로 채운 뒤 그린다 |
| `ui.kpis(items)` | `[{"label", "value", "help", "delta"?, "delta_color"?}]` 2~4개. 값은 미리 계산·형식화된 문자열 | 없음 | `st.columns(n, gap="small")` + `st.metric(label, value, help=…, border=True, height="stretch", delta=…)` (한 줄의 지표 높이를 맞춤) | 6-2절 숫자 형식 | 값 없음 → `"—"` 와 `help` 에 사유. ⏳ 항목은 `"준비 중"` |
| `ui.card()` | 없음 | 컨테이너 | `st.container(border=True, key=f"card_{n}")` (실행마다 `ui.reset_cards()` 로 번호를 0부터) | 카드 면·그림자는 `style.py` 가 `st-key-card_` 클래스로 칠한다 | — |
| `ui.conclusion(text, evidence)` | 결론 문장, 근거 링크 목록 | 없음 | `ui.card()` + `st.markdown` | 결론 1~2줄 + 근거 링크 | 현재 S0은 이 함수 대신 자체 결론 띠를 쓴다(5-1절) |
| `ui.pending(element, waiting_for)` (골격 호출 형식 그대로) | 요소 이름, 대기 대상 | 없음 | `st.info(icon=":material/hourglass_empty:")` | `**<요소>**` + `준비 중 — <대기 대상> 결과가 생성되면 표시됩니다.` | — |
| `ui.empty(kind, key)` | `"기사"` / `"공시"` / `"기사/공시"` / `"요약"`, 호출 위치마다 다른 `key`(예: 컴포넌트 ID `"S1-C1"`) | 없음 | `st.container(border=True)` + `st.markdown` + `st.button("필터 초기화", key=f"empty_reset_{key}", on_click=filters.reset)` — 한 화면에서 여러 번 불려도 버튼 key가 겹치지 않게 한다. 5절 표의 `ui.empty("기사")` 는 `kind` 만 적은 것이며, `key` 는 그 행의 컴포넌트 ID를 넘긴다 | 7-2절 문구. 빈 축을 그리지 않는다 | — |
| `ui.data_error(path, err)` | 읽지 못한 파일·DB 경로, 예외 | 없음 | `st.error` | 7-2절 문구 + `st.expander("오류 내용")` 안에 예외 메시지 | 다른 요소는 계속 그린다 |
| `ui.limits(extra=None)` (골격은 인자 없이 호출) | 화면별 추가 문구 목록 | 없음 | `st.expander("데이터 범위·한계", expanded=False)` | 7-1절 공통 문구 + `extra` + 데이터 기준 줄 | DB `meta` 를 못 읽으면 기준 줄만 `"—"` |
| `ui.sentiment_badge(label)` | `기회`/`위험`/`중립` | 마크다운 문자열 | `:blue-badge[▲ 기회]`, `:red-badge[▼ 위험]`, `:gray-badge[● 중립]` | 2-2절 | 그 밖의 값 → `:gray-badge[미분류]` |
| (`ui.flag_badges` — 구현하지 않음) | — | — | — | 배지는 화면마다 직접 붙인다(예: S2 `_article_row`) | — |
| `ui.news_line(row)` | 기사 1건 | 없음 | `st.markdown` | 6-5절 뉴스 출처 형식 | URL 없음 → 링크 자리에 `원문 없음` |
| `ui.disclosure_line(row, ask_button=False)` | 공시 1건 | 버튼 클릭 여부 | `st.markdown` + (선택) `st.button("이 공시에 질문 →")` | 6-5절 공시 출처 형식 | — |
| `ui.table_view(df, label)` | 차트에 쓴 집계 표 | 없음 | `st.expander("표로 보기")` + `st.dataframe` | 모든 차트 아래 (8절 접근성) | — |

**로딩:** 데이터를 처음 읽는 함수는 `@st.cache_data(show_spinner=False)` 로 감싸고, 화면에서 `with st.spinner("데이터를 불러오는 중"):` 안에서 부른다 (WF 4-1절).

### 3-3. 공통 상태 판정 순서

차트·목록 하나를 그릴 때 아래 순서로 판정한다.

1. 산출물 파일이 없거나 해당 단계가 미실행 → **준비 중**(`ui.pending`). 오류로 보이지 않게 `st.info`.
2. 파일·DB를 읽다가 예외 → **데이터 오류**(`ui.data_error`).
3. 적용 필터로 거른 결과 0건 → **빈 결과**(`ui.empty`).
4. 그 밖 → **정상**. 행 단위로 신뢰도 낮음 배지(6-6절)를 붙인다.

Q&A의 상태(입력 전·답변 생성 중·답변·거절·오류)는 5-7절에 있다.

## 4. 사이드바 필터 (F7)

### 4-1. 필터 위젯

| 필터 | 위젯 | 위젯 key | 선택지 (값 그대로) | 기본값 | 검증 |
|---|---|---|---|---|---|
| 기간 | `st.date_input("기간", value=(2023-10-19, 2026-10-19), min_value=2023-10-19, max_value=2026-10-19, format="YYYY-MM-DD")` (범위 선택) | `flt_period` | 2023-10-19 ~ 2026-10-19 (DB `meta.period_start`·`period_end`) | 전체 기간 | 시작일만 고른 상태(값 1개)면 적용 값을 바꾸지 않고 `st.caption("종료일을 고르면 적용됩니다")` |
| 기간 빠른 선택 | 기간 입력 바로 아래 `st.selectbox("기간 빠른 선택", options, label_visibility="collapsed")` | `flt_quick` | 전체 기간, 최근 1개월, 최근 3개월, 최근 6개월, 최근 1년, 최근 2년, 직접 지정. 종료일 = 데이터 마지막 날(`meta.period_end`), 시작일 = 종료일 − N개월(데이터 첫날보다 앞서지 않음). 예: 최근 1개월 = 2026-09-19 ~ 2026-10-19 | 전체 기간 | 적용 중인 기간이 어느 항목과도 같지 않으면 "직접 지정" 으로 보인다. "직접 지정" 을 고르면 아무것도 바꾸지 않는다 |
| 기업 | 체크박스 드롭다운: `st.popover("기업 · <기업 요약>", width="stretch")` 안에 항목마다 `st.checkbox(항목)`. 버튼 문구의 요약은 4-5절 필터 상태 줄과 같다(`5개사 전체` / `삼성바이오로직스 외 3` / `기업 없음`) | 체크박스 `flt_co_0`~`flt_co_4` (선택 목록은 `flt_companies`) | 삼성바이오로직스, SK바이오사이언스, 프레스티지바이오로직스, 에스티팜, 바이넥스 (IA 4-1절 순서) | 5개사 전체 | 0개면 `st.warning("기업을 1개 이상 고르세요")`, 화면은 빈 결과 상태 |
| 카테고리 | 체크박스 드롭다운: `st.popover("카테고리 · <카테고리 요약>", width="stretch")` 안에 항목마다 `st.checkbox(항목)`. 요약은 4-5절과 같다(`카테고리 6개 전체` / `규제·정책 외 4` / `카테고리 없음`) | 체크박스 `flt_kw_0`~`flt_kw_5` (선택 목록은 `flt_keywords`) | CDMO 규제·정책, CDMO 지정학, CDMO 모달리티, CDMO 생산능력, CDMO 수주, CDMO 경쟁 구도 | 6개 전체 | 0개면 `st.warning("카테고리를 1개 이상 고르세요")`, 화면은 빈 결과 상태 |
| 초기화 | `st.button("필터 초기화", on_click=filters.reset, width="stretch")` | `flt_reset` | — | — | — |

- 위젯은 `app.py` 에서 `st.navigation` 앞에 그린다. 매 실행마다 같은 key로 그려지므로 페이지를 옮겨도 값이 유지된다 (IA 4-1절).
- `on_change` 콜백이 위젯 값을 `st.session_state["filters"] = {"period": (date, date), "companies": [...], "keywords": [...]}` 로 옮긴다. 화면 코드는 위젯 key가 아니라 `filters` 만 읽는다 (현재 골격이 `st.session_state["filters"]` 를 읽음).
- 기업·카테고리는 `st.multiselect` 대신 체크박스 드롭다운을 쓴다. 항목을 하나 고를 때마다 목록이 닫히지 않게 하기 위해서다(팝오버는 안의 체크박스로 다시 실행돼도 열린 채로 있다). 체크박스 `on_change` 콜백은 체크된 항목을 선택지 순서대로 모아 `filters["companies"]`·`flt_companies`(카테고리는 `filters["keywords"]`·`flt_keywords`)에 함께 넣는다.
- 기업·카테고리의 기준값은 `filters` 이다. 체크박스 key(`flt_co_*`·`flt_kw_*`)는 매 실행 위젯을 그리기 전에 `filters` 에서 다시 채운다. 그래서 L1·L4 이동(4-4절)이나 초기화가 `filters` 를 바꾸면 체크 상태와 버튼 요약이 그대로 따라간다.
- `filters.reset()` 은 `flt_period`·`flt_companies`·`flt_keywords` 와 `filters` 를 기본값으로 되돌리고(체크박스는 위 규칙대로 다음 실행에 전체 선택으로 그려진다) 화면별 상태 key(4-4절)는 지우지 않는다.
- 기간 빠른 선택은 Streamlit 달력 아래 기본 빠른 선택('Date range': Past Month 등)을 대신한다. 기본 것은 영어로 고정돼 있고 **오늘부터** 거슬러 센 뒤 데이터 끝으로 잘라서, 예를 들어 Past Month가 2026-10-19 하루가 된다. 그래서 `app.py` 의 CSS(`[data-testid="stDateInputQuickSelect"] { display: none; }`)로 숨긴다. 같은 CSS가 달력 머리를 [연도][월] 순서로 보인다.
- 빠른 선택 `on_change` 콜백은 `flt_period` 와 `filters["period"]` 를 함께 바꾼다. 표시값 `flt_quick` 은 매 실행 위젯을 그리기 전에 `filters["period"]` 에서 다시 정한다(체크박스와 같은 방식). 그래서 달력 직접 선택·L1·L4·초기화 뒤에도 맞게 보인다.
- 위젯 아래 `st.caption("필터는 모든 차트에 적용됩니다. 화면별 적용 범위는 각 화면 상단을 보세요.")`.

### 4-2. 데이터에 적용하는 규칙

| 대상 | 기간 | 기업 | 카테고리 |
|---|---|---|---|
| 뉴스 (`news`, 항상 `dup_of IS NULL`) | `published_date` 가 범위 안 | 5개 전체면 거르지 않음 — 기업 언급이 없는 산업 기사도 포함. 일부만 고르면 `news_companies` 에서 `corp_code IN (선택)` 이고 `match_field IN ('title','body')` 인 기사만 — **팀 확인 전(U2)** | `news_cdmo_keywords.keyword IN (선택)` 인 키워드가 1개 이상 있는 기사. 6개 전체일 때 키워드가 없는 기사(`해당 없음`) 포함 여부는 **미결 Q1** — 임시 동작: 포함(U2와 같은 방식) |
| 감성·이슈 CSV (`sentiment_llm.csv`, `issues_llm.csv`) | `url` 로 `news` 에 조인한 뒤 뉴스 규칙 | 뉴스 규칙 | 뉴스 규칙 |
| 공시 (`disclosures`) | `rcept_date` 가 범위 안 | `corp_code IN (선택)` (공시는 항상 5개사 중 하나) | 화면별 (4-3절) |
| 뉴스-공시 연결 (`news_disclosure_links.csv`) | `published_date` 가 범위 안 | `corp_name IN (선택)` | `news_keyword` 를 `; ` 로 나눈 값 중 선택 키워드가 있는 행. 빈 값(리스크 공시 107행)은 카테고리 6개 전체일 때만 포함 (미결 Q8) |
| 급증 시점 (`eda_spikes.csv`) | `peak_week` 가 범위 안 | `series='기업'` 행은 `scope IN (선택)`, `산업 전체` 행은 5개 전체일 때만 — **팀 확인 전(U2)** | `series='키워드'` 행은 `scope IN (선택)`, `산업 전체`·`기업` 행은 거르지 않음 |

### 4-3. 화면별 적용 범위 {AC-18}

IA 4-2절을 구현 단위로 옮긴 표이다. "반영"은 해당 컴포넌트의 데이터가 4-2절 규칙으로 걸러진다는 뜻이다.

| 화면 | 컴포넌트 | 기간 | 기업 | 카테고리 |
|---|---|---|---|---|
| S0 | S0-K, S0-C1~C3 | 카드 태그로 거르기 | 카드 태그로 거르기 | 카드 태그로 거르기 — **팀 확인 전(U1)** |
| S1 | S1-K, S1-C1, S1-C2, S1-C3, S1-C4 | 반영 | 반영 (U2) | 반영 |
| S2 | S2-K, S2-C1, S2-C2, S2-C3 | 반영 | 반영 (U2) | `CDMO 규제·정책`, `CDMO 지정학` 과 사이드바 선택의 교집합. 교집합이 없으면 화면 전체 빈 결과 + 7-3절 문구 |
| S3 | S3-K(기사 지표), S3-C1, S3-C2 | 반영 | 반영 (U2) | `CDMO 모달리티`, `CDMO 생산능력` 과 교집합(S2와 같은 방식). 교집합이 없으면 화면 전체 빈 결과 + 7-3절 문구 |
| S3 | S3-K `증설 공시` 지표, S3-C3 증설 공시 | 반영 | 반영 | 위와 같은 교집합 규칙(IA 4-2절 "S2와 같은 방식"). 교집합이 1개 이상이면 `event_class='증설'` 공시를 모두 보이고(대응표상 모달리티·생산능력 둘 다 증설과 연결), 없으면 화면 전체 빈 결과에 함께 포함 |
| S4 | S4-K, S4-C1, S4-C2, S4-C3(금액 차트·금액 미추출 수주 공시 표) | 반영 | 반영 | 선택 키워드 → NEWS_DISCLOSURE_MATCHING 3-3절 대응표의 직접·후속 열을 합친 `event_class` 집합으로 거름(미결 Q8). S4-C3은 이 집합에 `수주` 가 있을 때만 표시. `CDMO 규제·정책`·`CDMO 지정학` 은 후속 창 대응(수주, 증설, M&A·구조개편)을 쓰고, 둘 중 하나 이상이 선택에 포함되면 7-3절 "인과 아님" 문구 표시 — **팀 확인 전(U3)** |
| S5 | S5-K, S5-C1(기사 막대), S5-C2 | 반영 | 반영 | 기사 쪽에 반영. 공시는 연결 결과를 따르고, S5-C1 공시 표식은 S4와 같은 대응표 |
| S6 | 질문 범위 | 기본값으로 표시, 해제 가능 | 기본값으로 표시, 해제 가능 | 적용 안 함 — **팀 확인 전(U4)** |

### 4-4. 화면 이동과 상태 key

IA 5절 L1~L9의 구현. 필터를 바꾸는 이동은 위젯 key(`flt_*`)와 `filters` 를 함께 바꾼 뒤 `st.switch_page` 를 부른다. 사용자는 이동 후 사이드바에서 바뀐 값을 보고 되돌릴 수 있다.

- 사이드바 위젯은 `app.py` 에서 페이지 코드보다 먼저 그려지므로(4-1절), 페이지 코드 본문에서 `st.session_state["flt_*"]` 에 값을 넣으면 `StreamlitWidgetAlreadyInstantiatedError` 가 난다(설치본 `streamlit/errors.py`: 위젯을 만든 뒤에는 바꿀 수 없고 `on_change`·`on_click` 콜백에서 바꾸라고 안내). 그래서 L1·L4 버튼은 `st.button(..., key=..., on_click=콜백, args=(...))` 로 만들고, 콜백 안에서 `flt_*`·`filters`(L4는 `s5_issue` 도)를 쓴다. 콜백은 다음 실행 전에 돌므로 위젯이 새 값으로 그려진다. 페이지 코드는 버튼이 `True` 를 돌려줄 때 `st.switch_page(대상)` 만 부른다.
- 같은 이유로 페이지 위젯 key(예: `s4_company`)를 코드에서 바꿀 때는 그 위젯을 그리기 전에 바꾼다.

| # | 구현 |
|---|---|
| L1 | [자세히 →] `on_click` 콜백이 카드 태그의 기간·기업·키워드를 `flt_*`·`filters` 에 넣고, 버튼이 `True` 면 카드의 출처 화면으로 `st.switch_page` |
| L2·L5·L6·L9 | 외부 링크(새 탭). 6-5절 |
| L3 | S1 안에서 `s1_spike` 를 바꿈 (페이지 이동 없음) |
| L4 | [관련 공시 →] `on_click` 콜백이 `flt_*`·`filters` 에 기업·기간(그 달 1일~말일)·키워드를 넣고 `s5_issue` 에 임시 이슈 키를 넣은 뒤, 버튼이 `True` 면 S5로 `st.switch_page`. IA L4는 출발점을 S1·S2·S3 이슈로 적었지만 WF는 [관련 공시 →] 를 S1 부상 이슈(S1-C4)에만 두었고, 이 문서도 S1-C4에만 둔다. 구현(2026-11-19): 선택한 이슈의 최근 기사에 나온 기업과 최근 3개월로 필터를 바꾸고 S5로 간다. 이슈 자체는 넘기지 않는다(S5는 키워드 × 기업 × 월로 묶음) (Q18 해결) |
| L7 | S4 안에서 `s4_company` 를 바꿈 |
| L8 | `qa_scope_override = {"corp_names": [기업], "date_from": 제출일, "date_to": 제출일}` 를 넣고 S6으로 이동. 사이드바 필터는 바꾸지 않는다(미결 Q11) |

화면별 상태 key (모두 `st.session_state`, 저장하지 않음):

| key | 화면 | 값 |
|---|---|---|
| `filters`, `flt_period`, `flt_quick`, `flt_companies`, `flt_keywords`, `flt_co_0`~`flt_co_4`, `flt_kw_0`~`flt_kw_5` | 공통 | 4-1절 (빠른 선택·체크박스 key는 `filters` 에서 매 실행 다시 채움) |
| `s1_unit`, `s1_series`, `s1_spike`, `s1_issue` | S1 | 단위(월/주), 계열(출처별/키워드별), 선택한 급증 시점, 선택한 부상 이슈 (팀원수집 제외 토글 `s1_excl_team` 은 2026-11-19 삭제) |
| `s2_label`, `s2_lang`, `s2_rows` | S2 | 라벨·언어 목록 필터, 표시 행 수 |
| `s4_company`, `s4_rcept` | S4 | 타임라인 기업, 선택한 공시 `rcept_no` |
| `s5_company`, `s5_issue` | S5 | 차트 기업, 선택한 임시 이슈 |
| `qa_use_period`, `qa_use_companies`, `qa_scope_override`, `qa_last`, `qa_history` | S6 | 5-7절 |

### 4-5. 필터 상태 줄

형식: `<시작일> ~ <종료일> · <기업 요약> · <카테고리 요약>` (IA 4-2절 예시 형식).

| 경우 | 기업 요약 | 카테고리 요약 |
|---|---|---|
| 전체 | `5개사 전체` | `카테고리 6개 전체` |
| 1개 | 기업명 | 키워드에서 `CDMO ` 를 뺀 이름 (예: `규제·정책`) |
| 2개 이상 | `<IA 순서상 첫 기업> 외 n` (예: `삼성바이오로직스 외 1`) | `<첫 키워드> 외 n` |
| 0개 | `기업 없음` | `카테고리 없음` |

S2·S3·S4·S6처럼 화면이 범위를 바꾸면 같은 줄 끝에 ` · 이 화면: <화면 고정 범위>` 를 덧붙인다 (예: S2 `· 이 화면: 규제·정책, 지정학`, S6 `· 이 화면: 카테고리 미적용`).

## 5. 화면별 명세

각 화면은 두 표로 적는다. "구성" 표는 무엇을 어떤 데이터로 그리는지, "동작" 표는 표시·상호작용·상태·연결이다. P는 스토리 우선순위([USER_STORIES](../02_product-requirements/USER_STORIES.md)), 준비는 IA 7절 기준이다. 모든 화면은 ①`ui.header`, ④`ui.limits` 를 가지며 표에서 생략한다.

### 5-1. S0 요약 — [F6]

머리는 `ui.header` 대신 자체 배치: 왼쪽 `st.title("요약")` + caption `현재 필터: <필터 상태 줄>`, 오른쪽 공시 검색창(`st.form("s0_qa_form")` 안 가로 컨테이너: `st.text_input(placeholder="공시에 물어보기…", width="stretch")` + `st.form_submit_button("질문", type="primary", width="content")` — 좁은 창에서도 "질문" 글자가 잘리지 않게 버튼은 글자 폭만큼, 2026-11-19). 제출하면 질문을 `qa_pending` 에 넣고 S6으로 이동.

**구성** (2026-11-19 main 기준, `dashboard/views/s0_summary.py`)

| ID | 요소 | 컴포넌트 | 입력 데이터 | 변환·집계 |
|---|---|---|---|---|
| S0-C1 | 결론 띠: `지금 CDMO 시장 현황은 우호적` + 기회·위험 두 줄 + 수치 상자 + 출처 줄 | `st.container(key="s0_hero")`(진녹색 면, `style.py`) 안에 `st.title`, `st.markdown`, `st.container(border=True, key="s0_hero_stats")` + `st.caption` | `data/processed/summary_cards.json` (`label_counts`, `conclusion`, `basis`) — `analysis/build_summary_cards.py` 가 만듦 | 판단 단어: 기회 ≥ 위험 × 2 → `우호적`(밝은 파랑), 위험 ≥ 기회 × 2 → `비우호적`(밝은 빨강), 그 밖 → `중립`(회색). 기회·위험 두 줄은 `conclusion` 둘째 문장("기회는 …, 위험은 …")을 나눠 항목을 ` · ` 로 이음. 수치 상자 = `기회 기사가 위험 기사의 n배 · 기회 n건 · 위험 n건 · CDMO 뉴스 n건 · 기간`. 출처 줄 = `AI 활용 · 근거: …`. 전체 기간 고정 요약 — 필터로 다시 쓰지 않음 (**팀 확인 전(U1)**) |
| S0-K | 지표 [▲ 기회 기사] [▼ 위험 기사] [연결 공시] [급증 시점] + 최근 3개월 증감 | `ui.kpis` (`delta`) | DB `news` ⨝ `sentiment_llm.csv`, `news_disclosure_links.csv`, `eda_spikes.csv` | 필터 후 건수. 증감 = 필터 기간 끝에서 최근 3개월(91일) − 직전 3개월. 위험은 늘면 빨강(`delta_color="inverse"`), 급증 시점 증감 자리는 "최근 3개월 n회" |
| S0-C4 | 월별 기회 vs 위험 (묶음 막대) | `ui.card()` + Plotly, `st.columns([2, 1])` 왼쪽 | 같음 | 월 × 기회·위험 건수 + `ui.table_view` |
| S0-C5 | 공시에 물어보기 카드 | `ui.card()`, 오른쪽 | S6 `EXAMPLES` | 예시 질문 3개를 짧은 이름(굵은 기업명 + 묻는 것, 예: **바이넥스** 오송공장 투자 금액·기간)으로 표시, 마우스를 올리면 전체 질문(`help`), 누르면 전체 질문을 S6에 보냄 |
| S0-C2 | ▲ 기회 요인 카드 (현재 5개) | `:blue-badge[▲ 기회 요인] n` 머리 + 3열 `ui.card()` | `summary_cards.json` `cards` | 카드 태그(기업·키워드·기간)가 적용 필터와 겹치는 카드만 — **팀 확인 전(U1)**. 근거 0개 카드 제외(N6) |
| S0-C3 | ▼ 위험 요인 카드 (현재 3개) | `:red-badge[▼ 위험 요인] n` + 같음 | 같음 | 같음 |
| S0-C6 | 최근 주요 공시 표 | `st.dataframe(selection_mode="single-row")` | DB `disclosures`, 연결 CSV | 수주·증설·M&A·자금조달 중 최근 10건(정정 제외), 열: 제출일·기업·공시명·분류·연결 기사·DART. 행을 고르면 [이 공시에 질문 → 공시명] = L8 |

카드 필드 (`summary_cards.json`): `id`, `type`(기회/위험), `title`, `desc`, `tags`(companies·keywords·start·end), `evidence`(kind 기사/공시, title, date, url, press), `n_articles`, `screen`(출처 화면).

**동작**

| ID | 표시 | 상호작용 | 빈·대기 상태 | 연결 | P | 준비 |
|---|---|---|---|---|---|---|
| S0-C1 | 머리 바로 아래 결론 띠. 1366×768에서 스크롤 없이 보임 | — | `summary_cards.json` 없음 → `ui.pending("기회·위험 결론 문장과 카드 (근거 뉴스·공시 링크 포함)", "analysis/build_summary_cards.py")` | (US-01) {AC-01} | P0 | 구현됨 (2026-11-19 문구) |
| S0-K | 6-2절 형식, 한 줄 4개 높이 같음 | `help` 에 정의 | 0건 → `0건` | (US-01) | P0 | 구현됨 |
| S0-C2·C3 | 카드: 제목(굵게) → caption `기사 n건 · 기업 · 시작월 ~ 끝월` → [근거 n] 팝오버(설명 + 기사·공시 링크) · [자세히 →] | [자세히 →] = L1 (카드 태그를 필터로 넣고 출처 화면으로). 근거 링크 = L2 | 필터 후 카드 0개 → `현재 필터에 해당하는 요약 없음` + [필터 초기화] — **팀 확인 전(U1)** | (US-02) {AC-02}, N6 | P0 | 구현됨 |
| S0-C5 | 버튼 왼쪽 정렬, 기업명 한 줄·묻는 것 한 줄 | 클릭 → S6에서 바로 질문 | — | (US-16) | P0 | 구현됨 |
| S0-C6 | 표 아래 caption | 행 선택 → 질문 버튼 = L8 | 0건 → `ui.empty("공시")` | (US-16) | P0 | 구현됨 |

### 5-2. S1 이슈·트렌드 — [F1]

`ui.header("이슈·트렌드", "지금 가장 많이 다뤄지는 이슈는?", filters)` (WF 문구).

**구성**

| ID | 요소 | 컴포넌트 | 입력 데이터 | 변환·집계 |
|---|---|---|---|---|
| S1-K | [기사 n건(중복 제외)] [급증 시점 n회] [최근 급증: YYYY-MM-DD] | `ui.kpis` | DB `news`, `eda_spikes.csv` | 기사 = 필터 후 기사 수(키워드 검색 = `origin='team'` 기사 제외). 급증 = 필터 후 `eda_spikes` 행 수. 최근 급증 = 그 중 최대 `peak_week` |
| S1-C1 | 기사량 추이 | `st.segmented_control("단위", ["월", "주"], key="s1_unit", default="월", required=True)`, `st.segmented_control("계열", ["출처별", "키워드별"], key="s1_series", default="출처별", required=True)` (설치본 `required` 기본값이 `False` 라 선택된 항목을 다시 누르면 `None` 이 되므로 `True` 로 둔다) + Plotly | DB `news`(`dup_of IS NULL`, `origin`, `published_date`), `news_cdmo_keywords`(키워드별). 필터를 반영해야 하므로 `eda_news_monthly.csv`·`eda_weekly.csv` 대신 DB에서 집계하고, 두 CSV는 기본 필터일 때의 검증값으로만 쓴다 | 월 = `published_date` 의 `YYYY-MM`. 주 = 월요일 시작 주(`eda_weekly.csv` 와 같은 기준). 출처별 = `origin` 별 건수(키워드 검색 제외 4개 출처). 키워드별 = 대표 키워드(`is_primary=1`), `cdmo_kw_basis='query'`·키워드 검색 제외(`eda_keyword_monthly.csv` 와 같은 기준) |
| S1-C2 | 급증 시점 목록 | `st.dataframe(on_select="rerun", selection_mode="single-row", key="s1_spike_tbl")` | `eda_spikes.csv` (`series`, `scope`, `peak_week`, `peak_count`, `baseline`, `z`, `top_terms`) | 4-2절 규칙으로 거름. 정렬 `peak_week` 내림차순 |
| S1-C3 | 선택한 급증 시점의 대표 기사·같은 시기 공시 | `st.container(border=True)` + `ui.news_line`·`ui.disclosure_line` | `eda_spikes.csv` `evidence_articles`, `disclosures` | `evidence_articles` 를 ` / ` 로 나누고 항목마다 `제목 (매체) URL` 을 정규식 `^(.*) \((.+?)\) (https?://\S+)$` 로 읽는다. 일자는 URL로 DB `news` 에 조인해 `published_date` 를 붙인다. `disclosures` 열은 ` / ` 로 나눈 `YYYY-MM-DD [분류] 보고서명 URL` |
| S1-C4 | 부상 이슈 (직전 3개월 대비) | `st.dataframe(on_select="rerun", selection_mode="single-row", key="s1_issue_tbl")` + 표 아래 선택 행용 `st.button("대표 기사")`·`st.button("관련 공시 →", on_click=…)` (S5-C2와 같은 행 선택 방식. 표 셀에는 버튼·배지를 넣지 않는다) | `issues_llm.csv` + `issue_groups.csv` (대표 이슈 이름) | 필터 기간 끝에서 최근 91일 vs 직전 91일. 최근 기사 5건 이상이면서 늘어난 이슈만, 증가 건수 순. 증가율 = (최근 − 직전) ÷ 직전, 직전 0건이면 `신규`. 필터 기간이 6개월 미만이면 계산하지 않음 (Q6 해결, 2026-11-19) |

**동작**

| ID | 표시·인코딩 | 상호작용 | 빈·대기 상태 | 연결 | P | 준비 |
|---|---|---|---|---|---|---|
| S1-K | `9,142건` 형식 | `help`: "중복(`dup_of`) 제외" / "급증 판정: 주별 z ≥ 3, eda_report 4절" | 0건 → 값 `0건` | (US-03) | P0 | 준비됨 |
| S1-C1 출처별 | 누적 막대: x = 월(또는 주), y = 건수, 색 = 출처(범주 슬롯 1~5). 팀원수집(화면 표기 `키워드 검색`, 2026년에 몰림)은 늘 뺀다 — 2026-11-19 토글을 없앴고, 나머지 출처는 범례 클릭으로 켜고 끈다(eda_report 6절). 높이 360px. WF 배치도 제목은 "선"이지만 같은 칸에 "출처(origin)별 누적"을 적었으므로, 출처별 조각의 합이 그 기간 기사량이 되도록 누적 막대로 그린다(R5) | 호버(x unified): 기간, 출처별 건수, 합계 | 0건 → `ui.empty("기사")` | (US-03) {AC-03}, PRD 4절 R1·R5 | P0 | 준비됨 |
| S1-C1 키워드별 | 소형 다중 차트 2×3: 칸마다 키워드 1개의 선(`series-volume`), 같은 y축 범위. 사이드바에서 고른 키워드 칸만 그린다 | 호버: 기간, 키워드, 건수 | 선택 키워드 0개 → 빈 결과 | (US-03) {AC-03} | P0 | 준비됨 |
| S1-C1 급증 표시 | 급증 시점마다 세로 점선 + 위쪽 ● 표식(`mark-spike`, 10px)을 x 위치에만 표시(급증은 정해진 계열에서 판정한 값이라 막대 높이에 얹지 않는다). 월 단위에서는 `peak_week` 가 속한 월. 행사 주간(산업 전체 급증 중 2025-06-16·2026-06-22 바이오 USA, 2025-10-27·2026-10-05 CPHI — eda_report 4-1절)은 ● 옆에 `행사` 주석 | ● 클릭(`on_select="rerun"`, `selection_mode="points"`) → `s1_spike` 설정 = L3 | 필터 후 급증 0건 → 표시 없음 + caption "선택한 범위에 급증 시점이 없습니다" | (US-03, US-05) {AC-03} | P0 | 준비됨 |
| S1-C2 | 열: 주간(`peak_week`) · 대상(`scope`) · 기사 수(`peak_count`) · 평소(`baseline`, 소수 1자리) · z(소수 1자리) · 상위어(`top_terms` 앞 5개) | 행 선택 → `s1_spike` = L3 | 0건 → `ui.empty("기사")` | (US-03, US-05) | P0 | 준비됨 |
| S1-C3 | 대표 기사 최대 3건: 6-5절 뉴스 형식. 같은 시기 공시: 6-5절 공시 형식 + `[분류]` 배지. 행사 주간이면 위에 caption "정기 행사 주간의 급증입니다 (바이오 USA 6월, CPHI 10월)" | 링크(새 탭) | 미선택 → caption "급증 시점을 고르면 대표 기사가 보입니다". 공시 값 없음(43행) → "같은 시기 공시 없음" | (US-05) {AC-05}, IA L3 | P1 | 준비됨 |
| S1-C4 | 열: 이슈명 · 증가율 · 증가 건수 · 기간 · 기사 수 · 직전 3개월. 표 위 caption에 비교 기간·기준과 "이슈 이름은 LLM 추출 결과입니다 (표본 사람 검수 이름 98.7%)" (기본 텍스트 열은 배지 문법을 글자 그대로 보이므로 배지를 셀에 넣지 않는다). WF 배치의 [대표 기사]·[관련 공시 →] 는 표 아래 버튼으로 둔다 | 행 선택 후 [대표 기사] → 그 이슈 기사 목록 펼치기(S1-C3 형식). [관련 공시 →] = L4 (4-4절 콜백 방식). 미선택이면 두 버튼 `disabled=True` | 계산 불가 → caption 사유("필터 기간이 6개월 이상이어야 계산합니다" / "최근 3개월 기사 5건 이상이면서 늘어난 이슈가 없습니다") | (US-04) {AC-04}, (US-15) | P1 | 구현됨 (2026-11-19) |

`ui.limits` 추가 문구: 7-1절 S1 항목.

### 5-3. S2 규제·정책 — [F2] [F8]

`ui.header("규제·정책", "정책·규제 변화는 CDMO 시장에 기회인가 위험인가?", filters)` (현재 골격 문구). 대상 기사 = 중복 제외 & `news_cdmo_keywords.category='규제 및 정책'` 키워드가 1개 이상 있는 기사. 기본 필터에서 1,628건(한국어 1,204 · 영어 424)이고, 모두 `sentiment_llm.csv` 라벨이 있다(중립 900 · 기회 632 · 위험 96; DB 2026-11-16 빌드 + `sentiment_llm.csv`, 2026-11-17 집계).

**구성**

| ID | 요소 | 컴포넌트 | 입력 데이터 | 변환·집계 |
|---|---|---|---|---|
| S2-K | [기회 n] [위험 n] [중립 n] + 라벨 정확도 | `ui.kpis` 3개 + `st.caption` | `sentiment_llm.csv` (`url`, `label`) ⨝ `news` | 필터 후 라벨별 건수 |
| S2-C1 | 월별 기사 수 — 기회/위험/중립 누적 막대 | Plotly 누적 막대 | 같음 + `published_date` | 월 × 라벨 건수 |
| S2-C2 | 정책·규제 타임라인 | `st.multiselect("라벨", ["기회","위험","중립"], key="s2_label")`, `st.segmented_control("언어", ["전체","한국어","영어"], key="s2_lang", default="전체", required=True)` + 행 목록(`st.container` 반복) + `st.button("더 보기")` | `news`(`published_date`, `title`, `title_ko`, `lang`, `press`, `url`, `cdmo_kw_basis`), `news_clean.title_clean`, `sentiment_llm.csv`(`label`, `reason`, `confidence`, `input_basis`) | 정렬 `published_date` 내림차순, 같은 날은 `published_at` 내림차순. 처음 20행, [더 보기]마다 20행 추가(`s2_rows`) |
| S2-C3 | 언급 기업 막대 (5개사, 본문 전체 폭) | Plotly 가로 막대 | 5개사: `news_companies`(`match_field IN ('title','body')`). 해외 CDMO 언급 수는 데이터 정의가 없어 2026-11-19 뺌 (Q7 종료) | 기업별 기사 수 |

**동작**

| ID | 표시·인코딩 | 상호작용 | 빈·대기 상태 | 연결 | P | 준비 |
|---|---|---|---|---|---|---|
| S2-K | 라벨마다 `help` 에 라벨 정의(6-4절). 지표 아래 caption: `라벨 정확도: 표본 85.0% (180건) · 층 가중 84.2%` — 7-1절 S2 문구 | — | 0건 → `0` | (US-07) {AC-07}, N3 | P1 | 준비됨 |
| S2-C1 | x = 월, y = 건수, 색 = 감성 색. 쌓는 순서 아래부터 기회 → 중립 → 위험, 범례 같은 순서. 높이 280px | 호버(x unified): 월, 라벨별 건수 | 0건 → `ui.empty("기사")` | (US-07) | P1 | 준비됨 |
| S2-C2 행 | 1줄: `YYYY-MM-DD` · 감성 배지 · 제목(링크) · 매체 · `[원문]`. 2줄(caption): 입력 범위 `제목만`/`제목+본문`, 신뢰도 배지(6-6절). 영어 기사는 6-5절 번역 표시. 행 아래 `st.expander("판단 이유")` 에 `reason` + `:gray-badge[AI 생성]` | 제목·[원문] = 원문 새 탭 (L5) | 0건 → `ui.empty("기사")`. 카테고리 교집합 없음 → 7-3절 문구 | (US-06) {AC-06}, (US-07) {AC-07}, (US-08) {AC-08}, PRD 4절 R3·R4 | P1 | 구현됨 |
| S2-C2 영어 기사 | `title_ko` 가 있으면 `:gray-badge[번역]` + 한국어 제목, 그 아래 `원제목: <title>`. 없으면 원제목 + `:gray-badge[번역 준비 중]` (현재 797건 모두 번역 있음 — `translate-v3`, 표본 30건 검수 30/30) | 같음 | — | (US-08) {AC-08}, N2 | P1 | 구현됨 |
| S2-C3 | 5개사는 기업 색, IA 순서 고정(값 순 정렬 안 함) | 호버: 기업, 건수 | — (해외 CDMO 부분은 2026-11-19 삭제) | (US-07) PRD F2 "관련 기업 언급" | P1 | 5개사 부분은 DB로 가능, 해외 부분 근거 없음 |

`ui.limits` 추가 문구: 7-1절 S2 항목. 이 화면은 카테고리가 고정이라 필터 상태 줄에 `· 이 화면: 규제·정책, 지정학` (4-5절).

### 5-4. S3 기술·생산 — [F3]

`ui.header("기술·생산", "어떤 모달리티·생산기술이 성장하는가?", filters)` (현재 골격 문구).

**구성**

| ID | 요소 | 컴포넌트 | 입력 데이터 | 변환·집계 |
|---|---|---|---|---|
| S3-K | [모달리티 기사 n] [증설 공시 n] [최다 증가 모달리티] | `ui.kpis` | `news_cdmo_keywords`(`CDMO 모달리티`), `disclosures`(`event_class='증설'`, `is_amended=0`) | 필터 후 건수. `증설 공시` 는 4-3절 S3 교집합 규칙을 따른다 |
| S3-C1 | 모달리티별 언급 추이 (소형 다중 선) | Plotly 선 | `modality_llm.csv` 모달리티 태그 (`modality-v2`, CDMO 모달리티·생산능력 카테고리 기사) | 월 × 모달리티 건수 (7종: 항체·ADC·mRNA·세포·유전자치료제·올리고·펩타이드·백신, `기타` 제외) |
| S3-C2 | 기업 × 모달리티 히트맵 | Plotly 히트맵 + `st.segmented_control("값", ["기사 수", "기업 내 비율"], key="s3_heat_value", label_visibility="collapsed")` | `modality_llm.csv` ⨝ `news_companies` | 행 = 5개사(IA 순서), 열 = 모달리티 7종, 값 = 기사 수 또는 기업 행 합계 대비 비율. 칸을 고르면 그 기업·모달리티 기사 목록 |
| S3-C3 | 증설 공시 목록 | `st.dataframe` + `st.column_config.LinkColumn(display_text="DART")` | `disclosures` (`rcept_date`, `corp_code`→기업명, `report_nm`, `is_amended`, `url`, `event_class='증설'`) | 정렬 `rcept_date` 내림차순. 기본 필터에서 5건(정정 3건 포함; DB 2026-11-16 빌드, 2026-11-17 집계) |

**동작**

| ID | 표시·인코딩 | 상호작용 | 빈·대기 상태 | 연결 | P | 준비 |
|---|---|---|---|---|---|---|
| S3-K | 증설 공시 라벨 `증설 공시 (정정 제외)` | — | 최다 증가 모달리티 = 최근 3개월 − 직전 3개월 증가 건수가 가장 큰 모달리티. 계산 불가면 `—` + `help` 에 사유 | (US-09, US-10) | P1 | 구현됨 |
| S3-C1 | 모달리티 7개 소형 다중 차트(4열, 같은 y축, 칸 제목에 합계 건수): x = 월, y = 건수, 선 `series-volume`. 범주 색이 5개뿐이라 한 그림에 7개 선을 겹치지 않는다 | 호버(x unified) | 교집합 키워드 0개 → 7-3절 문구 | (US-09) {AC-09}, PRD 5절 | P1 | 구현됨 (모달리티 태그) |
| S3-C2 | 순차 색(2-6절), 칸 안에 건수 글자. 글자 색은 칸 색으로 정한다: `#CDE2FB`~`#2A78D6`(순차 1~7단계) 칸은 검정 `#000000`, `#256ABF`~`#0D366B`(8~10단계) 칸은 흰색 `#FFFFFF` (2-3절, 다크 모드는 단계 순서가 반대라 번호가 아니라 칸 색으로 판정). 설치본 Plotly 7.1.0의 `heatmap.textfont.color` 는 칸마다 다른 값을 받지 않으므로 `texttemplate` 대신 칸마다 `fig.add_annotation(text=…, font_color=…, showarrow=False)` 로 쓴다 | 호버: 기업, 모달리티, 건수 | 0건 → `ui.empty("기사")` | (US-10) {AC-10} | P1 | 구현됨 |
| S3-C3 | 열: 제출일 · 기업 · 공시명 · 정정(`정정`/빈칸) · DART 링크 | 링크 = L6 (새 탭) | 0건 → `ui.empty("공시")` | (US-10) {AC-10} | P1 | 준비됨 |

`ui.limits` 추가 문구: 7-1절 S3 항목.

### 5-5. S4 기업 비교 — [F4]

`ui.header("기업 비교", "경쟁사의 수주·증설·투자는 어떻게 변하는가?", filters)` (WF 문구).

**구성**

| ID | 요소 | 컴포넌트 | 입력 데이터 | 변환·집계 |
|---|---|---|---|---|
| S4-K | [수주 공시 n] [증설 공시 n] [M&A n] [자금조달 n] (정정 제외) | `ui.kpis` 4개 | DB `disclosures` (`event_class`, `is_amended`, `rcept_date`, `corp_code`). IA 7절의 `dart_disclosures_weighted.csv` 는 14개사(선정 5 + 비교 9)·접수일 정수형이라, 5개사 필터 적용이 쉬운 DB를 쓰고 CSV는 검증값으로만 쓴다 | 주요 4분류별 `is_amended=0` 건수. 기본 필터 값: 수주 49 · 증설 2 · M&A·구조개편 6 · 자금조달 6 (DB 2026-11-16 빌드, 2026-11-17 집계) |
| S4-C1 | 5개사 × 공시 분류 묶음 막대 (같은 축) | Plotly 묶음 막대 | 같음 | 기업 × 주요 4분류 건수, `is_amended=0` |
| S4-C2 | [탭] 기업별 타임라인 | `st.tabs(["기업별 타임라인", "수주 금액 추이"])` 첫 탭. `st.selectbox("기업", 선택 기업, key="s4_company")` + Plotly 산점 | `disclosures` 전체 분류(정정 포함) | 선택 기업의 공시. 카테고리 필터는 4-3절 대응표 |
| S4-C3 | [탭] 수주 금액 추이 | 둘째 탭. Plotly 산점·선 + `st.dataframe`(금액 미추출 공시) | `data/processed/contract_amounts.csv` (`analysis/extract_contract_amounts.py`, 공시 원문 '계약금액' 칸 정규식, LLM 아님) | x = 제출일, y = 계약 금액(억 원). 정정 공시는 최신 정정본 금액(eda_report 5절) |

**동작**

| ID | 표시·인코딩 | 상호작용 | 빈·대기 상태 | 연결 | P | 준비 |
|---|---|---|---|---|---|---|
| S4-K | `help`: "정정 공시 제외 · 공시 건수는 금액이 아닙니다" | — | 0건 → `0` | (US-11) | P1 | 준비됨 |
| S4-C1 | x = 분류(수주·증설·M&A·구조개편·자금조달), y = 건수, 색 = 기업 색(5개사가 같은 y축). WF 배치도는 기업별 묶음으로 그렸지만, 기업 색 고정 규칙을 지키고 같은 분류 안에서 기업을 비교하도록 x를 분류로 둔다. 높이 360px | 호버: 기업, 분류, 건수 | 0건 → `ui.empty("공시")`. 카테고리 선택에 규제·정책·지정학이 하나 이상 포함되면(기본값 6개 전체 포함) 위에 7-3절 "인과 아님" 문구 — **팀 확인 전(U3)** | (US-11) {AC-11}, {AC-18} | P1 | 준비됨 |
| S4-C2 | x = 제출일, y = `event_class`(범주 축), 점 색 = 주요 4분류는 범주 슬롯 1~4, 그 밖 분류는 중립 회색. 정정 공시는 속 빈 원(`circle-open`)으로만 구분. 아래에 선택한 공시: 제출일 · 공시명 · `:gray-badge[정정]` · `[DART]` · `st.button("이 공시에 질문 →")` | 점 클릭(`on_select="rerun"`, `selection_mode="points"`) → `s4_rcept`. [이 공시에 질문 →] = L8. 기업 변경 = L7 | 선택 기업이 사이드바에서 빠지면 첫 선택 기업으로 바꿈(`s4_company` selectbox를 그리기 전에, 4-4절). 0건 → `ui.empty("공시")` | (US-12) {AC-12}, (US-16) | P1 | 준비됨 |
| S4-C3 | 금액 단위 `억 원`(6-2절). 금액 미추출 공시는 차트 아래 별도 표 "금액을 추출하지 못한 수주 공시 n건" | 호버: 제출일, 기업, 공시명, 금액 | 0건 → `ui.empty("공시")` | (US-13) {AC-13} | P2 | 구현됨 |

`ui.limits` 추가 문구: 7-1절 S4 항목.

### 5-6. S5 뉴스-공시 연계 — [F5]

`ui.header("뉴스-공시 연계", "뉴스의 변화가 공시로 확인되는가?", filters)` (현재 골격 문구). S5·S6을 두 화면으로 나눈 구성 — **팀 확인 전(U5)**.

**구성**

| ID | 요소 | 컴포넌트 | 입력 데이터 | 변환·집계 |
|---|---|---|---|---|
| S5-K | [연결된 기사 n] [연결 공시 n] [연결 없는 기사 비율 n%] | `ui.kpis` | `news_disclosure_links.csv` + 분모: DB `news` ⨝ `news_companies`(`match_field IN ('title','body')`) ⨝ `news_cdmo_keywords` (`data.filter_match_targets`) | 기사는 **기사 × 기업** 단위로 센다 (Q12 결정, 2026-11-19 — 여러 기업이 나온 기사는 기업마다 1건). 연결된 기사 = 필터 후 고유 (`url`, `corp_name`) 수, 연결 공시 = 고유 `rcept_no` 수, 비율 = 1 − 연결된 기사 ÷ 매칭 대상 기사 × 기업. 분모는 매칭 스크립트와 같은 조건(중복 제외, 기업명이 제목·본문)에 연결 표와 같은 필터 규칙(기간·기업, 선택 키워드 중 하나 이상, 키워드 없는 기사는 6개 전체일 때만). 기본 필터: 1,521 / 2,849 → 46.6% |
| S5-C1 | 기업별 기사량(막대, 주별) + 공시 시점(▼) | `st.selectbox("기업", 선택 기업, key="s5_company")` + Plotly `make_subplots(rows=2, shared_xaxes=True, row_heights=[0.75, 0.25])` | 기사: DB `news` ⨝ `news_companies`(`match_field IN ('title','body')`) ⨝ `news_cdmo_keywords`(카테고리). 공시: DB `disclosures` | 위: 주별 기사 수. 아래: 공시 접수일 표식(주요 4분류 + 실적·임상·허가·기술계약·리스크, 정정 포함). WF S5(212행)·PRD F4·F5·NEWS_DISCLOSURE_MATCHING 18행은 `v_company_daily` 를 들지만 이 뷰는 `match_field` 를 거르지 않고(`query` 포함) 키워드 열도 없어 PRD 4절 R2와 카테고리 필터를 지킬 수 없다 (미결 Q2) |
| S5-C2 | 이슈 ↔ 관련 공시 목록 | `st.columns([2, 3])`: 왼쪽 `st.dataframe(on_select="rerun", selection_mode="single-row")`, 오른쪽 공시 목록 | `news_disclosure_links.csv` (`url`, `published_date`, `corp_name`, `rcept_no`, `rcept_date`, `report_nm`, `window`, `day_gap`, `news_keyword`, `event_class`, `class_weight`, `is_amended`, `kw_low_confidence`, `follow_cut`) | 왼쪽: 임시 이슈 = `news_keyword`(`; ` 로 나눈 각 값) × `corp_name` × `published_date` 의 월, 열은 이슈 · 연결 기사 수 · 연결 공시 수, 정렬 연결 기사 수 내림차순. 오른쪽: 선택 이슈의 공시를 `rcept_no` 로 묶고 직접 → 후속, 그 안에서 `class_weight` 내림차순, `day_gap` 절댓값 오름차순 (NEWS_DISCLOSURE_MATCHING 3-5절) |

**동작**

| ID | 표시·인코딩 | 상호작용 | 빈·대기 상태 | 연결 | P | 준비 |
|---|---|---|---|---|---|---|
| S5-K | 비율은 소수 1자리 %. 비율 도움말에 분모·연결 없음 건수 | — | 분모 0건 → `–`. DB를 못 읽으면 비율만 `–` (앞 둘은 CSV로 표시) | (US-15) | P1 | 준비됨 (2026-11-19) |
| S5-C1 | 위: 막대 `series-volume`, y = 기사 수. 아래: ▼ 표식(`triangle-down`, 10px), y = 분류 이름, 색 = 범주 슬롯(주요 4분류)·중립 회색(그 밖), 정정은 속 빈 표식. 두 칸이 x축(주)을 공유하는 한 차트 — 이중 y축은 쓰지 않음 | 호버: 위 = 주, 기사 수 / 아래 = 제출일, 공시명, 분류. ▼ 클릭 → 아래에 `ui.disclosure_line(ask_button=True)` | 기사·공시 모두 0건 → `ui.empty("기사/공시")` | (US-14) {AC-14} | P1 | 준비됨 (DB) |
| S5-C2 왼쪽 | 이슈 표기 `CDMO 수주 · 에스티팜 · 2026-09` (WF 예시 형식). 표 위 caption "이슈 단위 집계 전이라 키워드 × 기업 × 월로 묶었습니다" | 행 선택 → `s5_issue`. L4로 들어오면 해당 이슈 선택 | 0건 → `ui.empty("기사/공시")` | (US-15) {AC-15} | P1 | 준비됨 |
| S5-C2 오른쪽 | 행: 배지 `:blue-badge[직접]` 또는 `:gray-badge[후속 +N일]` · 제출일 · 공시명 · `[분류]` · `:gray-badge[정정]` · `[DART]` · [이 공시에 질문 →]. `kw_low_confidence=1` 이면 `:gray-badge[검색어 근거]`, `follow_cut=1` 이면 `:gray-badge[후속 확인 불가]`. 목록 아래 7-3절 안내 문구 2개 | DART 링크(새 탭), [이 공시에 질문 →] = L8 | 미선택 → caption "왼쪽에서 이슈를 고르면 관련 공시가 보입니다" | (US-15) {AC-15}, (US-16), N6 | P1 | 구현됨 — 7,135쌍, 표본 50쌍 검수(2026-11-18) |

`ui.limits` 추가 문구: 7-1절 S5 항목.

### 5-7. S6 공시 Q&A — [F5]

`ui.header("공시 Q&A", "공시 원문에 근거해 답합니다.", filters)` (현재 골격 문구). 두 화면 분리 — **팀 확인 전(U5)**. Q&A는 질의 시점에 임베딩 1회 + 답변 1회를 호출한다(NEWS_DISCLOSURE_MATCHING D4, 팀 확정 해석). 그 밖의 화면은 LLM·번역을 호출하지 않는다(N1·N2).

**구성**

| ID | 요소 | 컴포넌트 | 입력 데이터 | 변환·집계 |
|---|---|---|---|---|
| S6-K | 범위 안내 + 질문 범위 | `st.caption("범위: 5개사 · 공시 원문 있는 공시")` + `st.checkbox("기간: <시작> ~ <끝>", key="qa_use_period", value=True)`, `st.checkbox("기업: <필터 상태 줄의 기업 요약>", key="qa_use_companies", value=True)` | 적용 필터, `qa_scope_override`(L8) | 체크 해제 = 해당 조건 `None`. L8로 들어오면 override 값을 쓰고 caption `공시 화면에서 넘어온 범위: <기업> · <제출일>` + `st.button("사이드바 범위로 돌아가기")` — **팀 확인 전(U4)** |
| S6-C1 | 예시 질문 버튼 | `st.button` 3개 (`st.container(horizontal=True)`) | RAG 평가에서 검색·핵심 값이 모두 맞은 A04·A06·A14 (2026-11-19 교체 — 원래 Q1~Q3 중 정책–공시 질문은 실행마다 답·거절이 갈림): "삼성바이오로직스가 2026년 10월에 자율공시한 의약품 위탁생산계약의 계약금액과 계약기간 종료일은?", "바이넥스의 오송공장 신규시설투자 금액과 투자기간은?", "SK바이오사이언스의 RSV 예방항체 기술도입 계약의 상대방과 총 계약금액은?" | 클릭 → 질문으로 바로 제출 |
| S6-C2 | 질문 입력 | `st.form("qa_form")` + `st.text_area("질문", placeholder="질문을 입력하세요", max_chars=300)` + `st.form_submit_button("질문하기", type="primary")` | — | 앞뒤 공백 제거, 빈 질문은 제출하지 않음 |
| S6-C3 | 답변 + 근거 공시 | `st.container(border=True)` + `st.markdown` + 근거 목록 | `rag/qa.py` `ask(question, corp_names, date_from, date_to)` 반환 dict: `refused`, `stage`, `answer`, `refusal_reason`, `citations[{rcept_no, quote, corp_name, report_nm, is_amended, rcept_date, url}]` | 답변 본문의 `(14자리 접수번호)` 를 `citations` 순서 번호 `[1]`, `[2]` 로 바꿔 표시(현재 프롬프트가 문장 끝에 `(rcept_no)` 를 붙임, `rag/qa.py` SYSTEM_PROMPT 2번). 같은 `rcept_no` 는 같은 번호 |
| S6-C4 | 이전 질문 (이번 접속 동안만) | `st.expander("이전 질문")` | `qa_history` | 최신 순, 최근 20개만 유지. 저장하지 않음 |

**호출 규칙:** `ask()` 는 `with st.spinner("공시를 찾는 중"):` 안에서 부른다. `corp_names` 는 기업 체크 시 선택 기업 목록(5개 전체여도 목록 그대로), `date_from`·`date_to` 는 `YYYY-MM-DD` 문자열. `ask()` 는 키·색인이 없으면 `sys.exit(...)` 를 부르므로 `except SystemExit` 와 `except Exception` 을 둘 다 잡는다. 결과는 `qa_last` 에 넣고 `qa_history` 맨 앞에 추가한다. 캐시하지 않는다.

**상태** (WF 4-2절을 `rag/qa.py` 반환값에 맞춤)

| 상태 | 판정 | 표시 |
|---|---|---|
| 입력 전 | `qa_last` 없음 | S6-K 범위 안내 + S6-C1 예시 질문 |
| 답변 생성 중 | 제출 직후 | `st.spinner("공시를 찾는 중")` |
| 답변 | `refused == False` 이고 `citations` 1개 이상 | 답변 본문 + `:gray-badge[AI 생성]` → `#### 근거 공시` → 근거마다 `[n] 공시명 · 제출일 · 기업 · [DART]` (정정이면 `:gray-badge[정정]`), 아래 `st.expander("인용 구절")` 에 `quote`. 근거 0개면 답변을 표시하지 않고 "거절 — 근거 없음"으로 처리 |
| 거절 — 범위 밖 | `stage == "scope"` | `st.warning`: 첫 줄 **이 대시보드는 5개사 공시만 다룹니다.** + 둘째 줄 `answer`(qa.py 문구 그대로, 대상 기업 목록 포함) |
| 거절 — 기업 범위 불일치 | `stage == "search"`, `refusal_reason` 이 "질문의 기업이 선택한 기업 필터 밖에 있다" | `st.warning`: **공시에서 근거를 찾지 못했습니다.** + `answer` + "질문 범위의 기업 조건을 해제하거나 질문 속 기업을 바꿔 보세요." |
| 거절 — 근거 없음 | `stage` 가 `search`(그 밖 사유)·`generate`·`verify` | 오류로 읽히지 않게 경고 대신 한 줄: `:gray-badge[공시 근거 없음] 이 질문에 해당하는 공시는 찾지 못해, 공시로 답하지 않았습니다.` 질문 단어가 제목에 든 관련 뉴스가 있으면 `st.info("**관련 뉴스 n건** — … (공시로 확인된 답은 아닙니다)", icon=":material/newspaper:")` 에 최대 5건(감성 배지·번역 배지·제목 링크·매체·일자, LLM 호출 없음). 없으면 `st.info` 로 기업명·기간·공시 종류를 넣어 다시 질문하라는 안내(`icon=":material/search:"`). 추측 답변을 쓰지 않는다 (2026-11-19) |
| 판단 요구 | 답변 본문에 "투자 판단은 하지 않는다" 가 있음 (반환값에 별도 표시가 없어 문구로 판정, 미결 Q3) | 답변 위 `st.info("판단은 하지 않고 공시 사실만 안내합니다")` |
| 인과 미확인 | 답변 본문에 "인과는 공시로 확인되지 않는다" 가 있음 (같음) | 답변 아래 `st.caption("인과는 공시로 확인되지 않음")` |
| 오류 | `SystemExit` 또는 예외 | `st.error("Q&A를 사용할 수 없습니다(설정 확인)")` + `st.expander("설정 확인")`: "`.env` 의 `OPENAI_API_KEY`, 색인 폴더 `chroma_db/` (`python rag/build_index.py` 로 생성)를 확인하세요." 다른 화면은 정상 동작 |

**동작**

| ID | 상호작용 | 연결 | P | 준비 |
|---|---|---|---|---|
| S6-K | 체크 해제·재설정 | (US-16), {AC-18} 해석 — **팀 확인 전(U4)** | P0 | — |
| S6-C1·C2 | 제출 → `ask()` | (US-16) | P0 | 준비됨 (`chroma_db/` 는 git에 없어 로컬 생성 필요) |
| S6-C3 | 근거 공시명·[DART] = L9 (새 탭) | (US-16) {AC-16}, (US-17) {AC-17} | P0 | 준비됨 |
| S6-C4 | 항목 클릭 → 그 결과를 S6-C3에 다시 표시(재호출 없음) | — | P0 | — |

`ui.limits` 추가 문구: 7-1절 S6 항목.

## 6. 표시 규칙

### 6-1. 날짜·시간

| 대상 | 형식 | 예 |
|---|---|---|
| 일 | `YYYY-MM-DD` | 2025-09-22 |
| 월 | `YYYY-MM` | 2026-09 |
| 주 | 주 시작 월요일 `YYYY-MM-DD` + `주` (표의 열 이름이 "주간"이면 생략) | 2025-05-19 주 |
| 분기 | `YYYYQn` (`eda_disclosure_quarterly.csv` 형식) | 2023Q4 |
| 기간 | `시작 ~ 끝` (물결 앞뒤 공백) | 2023-10-19 ~ 2026-10-19 |
| 시각 | 표시하지 않음. 같은 날 정렬에만 `news.published_at` 사용 | — |
| 빌드 일시 | `YYYY-MM-DD HH:MM` (KST) | 2026-11-16 09:48 |

- 시간대: DB 날짜는 모두 KST 기준 문자열(`db/schema.sql` 3행)이다. 변환하지 않는다. `dart_disclosures_weighted.csv` 의 정수형 접수일(`YYYYMMDD`)은 읽을 때 `YYYY-MM-DD` 로 바꾼다.
- 날짜 위젯은 `format="YYYY-MM-DD"` (설치본이 지원하는 하이픈 구분 형식).

### 6-2. 숫자·단위

| 대상 | 형식 | 예 |
|---|---|---|
| 건수 | 천 단위 쉼표 + `건` (지표·본문). 표 안 숫자 열은 `건` 없이 열 이름에 단위 | 9,142건 |
| 비율 | 소수 1자리 `%` | 85.0% |
| 증가율 | 부호 + 소수 1자리 `%`. 직전 기간 0건이면 `신규` | +34.5% |
| z, 평소 건수 | 소수 1자리 | 5.2 |
| 금액 | `억 원`, 천 단위 쉼표, 소수 1자리까지 | 1,234.5억 원 |
| 일 차이 | `+N일` / `−N일` | 후속 +34일 |
| 값 없음 | `—` | — |

공시 건수와 금액은 같은 차트·지표에 섞지 않는다(PRD 5절 "공시 건수는 금액이 아님").

### 6-3. 고정 순서·정렬

| 대상 | 규칙 |
|---|---|
| 기업 | IA 4-1절 순서(삼성바이오로직스, SK바이오사이언스, 프레스티지바이오로직스, 에스티팜, 바이넥스). 범례·선택지·히트맵 행 모두. 값 순으로 다시 정렬하지 않는다 (문서마다 순서가 달라 미결 Q10) |
| 카테고리 | 4-1절 순서 |
| 감성 | 기회 → 위험 → 중립(목록·배지), 누적 막대는 아래부터 기회 → 중립 → 위험 |
| 공시 분류 | 수주 → 증설 → M&A·구조개편 → 자금조달 → 그 밖(가나다순) |
| 출처 | 제공 → 키워드 검색(팀원수집) → 기업명검색 → CDMO검색 → 해외검색 |
| 기사·공시 목록 | 날짜 내림차순(최신 먼저) — WF S2 예시 행 순서. 예외: S5 관련 공시는 3-5절 규칙(5-6절) |
| 급증 시점 | `peak_week` 내림차순 |

### 6-4. 기회/위험 표시

- 문구는 항상 `기회` / `위험` / `중립` (라벨 값 그대로). "긍정/부정"은 쓰지 않는다 — 라벨은 "CDMO 시장 전체의 파이" 기준이다([AI_CLASSIFICATION](../04_ai/AI_CLASSIFICATION.md) 26~48행).
- `help` 툴팁 정의 문구(같은 문서 42~48행 요약): 기회 "CDMO 시장(위탁 수요·수주·투자·생산능력)이 커지는 사건이나 흐름", 위험 "CDMO 시장이 줄거나 위축되는 사건이나 흐름", 중립 "영향을 판단할 수 없거나 단순 사실 전달".
- 색·배지·기호는 2-2절. 색만 쓰지 않고 배지 글자와 ▲▼● 기호를 함께 둔다.

### 6-5. 출처 표기

| 종류 | 형식 | 링크 |
|---|---|---|
| 뉴스 (한국어) | `<표시용 제목> · <매체(news.press)> · <YYYY-MM-DD> · [원문]` | `news.url`, 새 탭 |
| 뉴스 (영어, 번역 있음) | `:gray-badge[번역] <title_ko> · <매체> · <YYYY-MM-DD> · [원문]` + 다음 줄 caption `원제목: <title>` | `news.url`, 새 탭 |
| 뉴스 (영어, 번역 없음 — 현재 해당 없음) | `<title> :gray-badge[번역 준비 중] · <매체> · <YYYY-MM-DD> · [원문]` | 같음 |
| 공시 | `<공시명(report_nm)> · <기업> · <제출일(rcept_date)> · [DART]` (+ 정정이면 `:gray-badge[정정]`) | `disclosures.url` = `https://dart.fss.or.kr/dsaf001/main.do?rcpNo=<14자리 접수번호>`. CSV처럼 URL 열이 없으면 `rcept_no` 로 같은 형식을 만든다 |
| 차트 호버 | 제목은 40자에서 자르고 `…` | 클릭 동작 없음 (목록에서 링크) |

- 외부 링크는 새 탭으로 연다(IA L2·L5). `st.link_button`·`LinkColumn` 을 우선 쓰고, 마크다운 링크의 새 탭 동작은 구현 시 확인한다(미결 Q15).
- 번역은 화면에서 만들지 않는다(N2, {AC-08}). `title_ko` 가 비어 있으면 번역을 호출하지 않고 위 "번역 없음" 형식으로 둔다.

### 6-6. 배지·표시

| 배지 | 조건 | 툴팁(`help` 또는 caption) |
|---|---|---|
| `:gray-badge[검색어 근거]` | `cdmo_kw_basis='query'` 또는 `kw_low_confidence=1` | "제목·본문에 키워드 단서가 없어 검색어로 분류한 기사입니다. 신뢰도가 낮습니다" (PRD 4절 R4) |
| `제목만` / `제목+본문` (caption 글자) | `input_basis` = `title` / `title+body`(감성), `body`(이슈) | "라벨을 붙일 때 본 범위" |
| `:gray-badge[확신도 낮음]` | `confidence='low'` | "LLM이 낮은 확신도로 붙인 라벨" |
| `:gray-badge[정정]` | `is_amended=1` | — |
| `:blue-badge[직접]` / `:gray-badge[후속 +N일]` | `window` = `direct` / `follow` | 직접 "기사 발행일 ±3일 안의 공시", 후속 "4~90일 뒤 공시 (가설, 검수 전)" |
| `:gray-badge[후속 확인 불가]` | `follow_cut=1` | "수집 끝(2026-10-19) 90일 이내 기사라 후속 공시를 아직 알 수 없습니다" |
| `:gray-badge[번역]` / `:gray-badge[번역 준비 중]` | 영어 기사 | 6-5절 |
| `:gray-badge[AI 생성]` / S0 `AI 활용` | LLM 결과(S2 판단 이유, S6 답변). S0 결론·카드는 출처 줄에 `AI 활용` (2026-11-19, 처음엔 `AI 초안 · 팀 검토`). S1 이슈명은 caption으로 표시 | 모델·프롬프트 버전 (예: `gpt-6-luna · sentiment-v3`) |
| `행사` (차트 주석) | 행사 주간 급증 | 5-2절 |

### 6-7. 자르기·줄바꿈

| 대상 | 규칙 |
|---|---|
| 목록 제목 | 자르지 않고 줄바꿈 |
| 표(`st.dataframe`) 제목 열 | 열 너비 `"large"`, 셀은 Streamlit 기본 말줄임 + 셀 펼침 |
| 상위어(`top_terms`) | 앞 5개 |
| 이슈명 | 자르지 않음 (규칙상 30자 이내, AI_CLASSIFICATION 218~220행) |
| 인용 구절(`quote`) | 자르지 않음 (프롬프트 규칙 80자 이내) |
| 판단 이유(`reason`) | 펼치기 안에 전체 |

## 7. 안내·한계 문구

### 7-1. 데이터 범위·한계 (`ui.limits`, 모든 화면 ④)

공통 문구 (순서대로, 각 항목 끝 괄호는 근거로 화면에는 쓰지 않음):

1. 뉴스는 국내 언론 중심입니다. 해외(영어) 뉴스 797건은 지정학 이슈(생물보안법·의약품 관세·미국/유럽 현지 생산)만 보강했습니다. (PRD 5절, AC 4절, news_sort 26~31행)
2. 구글 뉴스로 모은 기사(기업명검색·CDMO검색·해외검색)는 제목만 있습니다. 본문 기반 분석은 본문이 있는 출처(제공·키워드 검색) 범위입니다. (PRD 4절 R3, AC 4절)
3. 분석 기업은 국내 상장 5개사입니다. 론자·우시 등 해외 CDMO는 뉴스 언급으로만 다루고, 공시 비교는 5개사로 한정합니다. (PRD 5절)
4. 산업 보고서·경쟁사 홈페이지는 수집하지 않았습니다. 뉴스·공시로 한정합니다. (PRD 5절)
5. CDMO 키워드(카테고리) 분류는 규칙 기반이며 정확도를 검수하지 않았습니다. (PRD 5절)
6. 기사량은 중복 기사(정규화한 제목이 같고 7일 이내)를 빼고 셉니다. (PRD 4절 R1, DB `meta.dup_rule`)
7. 데이터 기준: `기간 <period_start> ~ <period_end> (KST) · DB 빌드 <built_at>` — DB `meta` 에서 읽음 (현재 2023-10-19 ~ 2026-10-19 · 2026-11-16 09:48)

화면별 추가 문구 (`ui.limits(extra=[...])`):

| 화면 | 문구 |
|---|---|
| S1 | 출처별 기사량은 따로 해석하세요. CDMO검색 기사는 2026년에 몰려 있습니다. (PRD 4절 R5) / 키워드 검색 1,306건(2026년에 몰려 있음)은 기사량 추이·지표·부상 이슈에서 제외했습니다. / 급증은 기사 건수 기준이며 기사 내용의 중요도가 아닙니다. 판정 기준(주별 z ≥ 3, 직전 26주 중앙값)은 민감도를 검증하지 않았습니다. / 2024-01 중순 이전은 급증을 판정하지 않습니다. / 급증 판정에서도 키워드 검색 1,306건은 제외했습니다. / 이슈 이름(LLM 추출)은 표본 30건 검수에서 98.7%(층 가중)가 정확했습니다. / 부상 이슈 기준 (eda_report 7절, AI_EVALUATION 9절) |
| S2 | 기회/위험 라벨은 LLM(gpt-6-luna, sentiment-v3)이 붙였습니다. 표본 180건 검수 정확도 85.0%(층 가중 84.2%, 모두 "기회"로 찍을 때 47.2%). 정답 22건은 이전 버전 결과를 본 뒤 고쳐 수치가 높게 나왔을 수 있습니다. / 라벨은 제목만 보고 붙인 기사가 3,505건, 제목+본문 1,222건입니다(전체 4,727건). / 해외 뉴스는 지정학 이슈만 보강되었습니다. (AI_EVALUATION 4-2절, AC 4절) |
| S3 | 모달리티 태그는 LLM(gpt-6-luna, modality-v2)이 붙였고 표본 80건 검수 정밀도 91.7%·재현율 98.1%. / 제목만 있는 기사는 태그가 적게 잡힘. / 히트맵 칸의 뜻과 여러 기업 기사. / CDMO 모달리티·생산능력 카테고리 기사만 셈. / '기타' 태그 비표시 (`s3_tech.py` `LIMITS_S3`) |
| S4 | 공시 건수는 금액이 아닙니다. 건수는 정정 공시를 빼고 셉니다. / 계약 금액은 원문 '계약금액' 칸을 정규식으로 읽었고(LLM 아님) 최신 정정본 금액을 씁니다. 계약 기간 전체 금액이며 한 해 매출이 아닙니다. / 프레스티지바이오로직스는 매출 규모가 작아(125억 원) 소규모 계약도 공시 대상이 됩니다. (PRD 5절, PRODUCT_BRIEF 44행) |
| S5 | 뉴스-공시 연결은 규칙 기반입니다(직접 ±3일, 후속 4~90일). 표본 50쌍 검수: 직접·당일 10/15, 직접·±1~3일 2/15, 후속 같은 사건 0/20·관련 13/20 — 후속은 '이후 사업 활동'으로 읽으세요. / 5개사가 언급되지 않은 기사(해외 CDMO, 정책 기사 대부분)는 공시와 연결되지 않습니다. / 연결의 91%가 삼성바이오로직스입니다. (NEWS_DISCLOSURE_MATCHING 3-2·8절) |
| S6 | 답변은 LLM이 공시 원문 발췌로 만듭니다. 근거 공시 원문을 확인하세요. / 색인 범위: 원문이 있는 공시 864건. / 평가(질문 20개): 검색 12/14, 거절 6/6, 근거 일치 12/13. (AI_EVALUATION 6절) |

### 7-2. 상태 문구 (정확한 텍스트)

| 상태 | 문구 |
|---|---|
| 로딩 | `데이터를 불러오는 중` |
| 빈 결과 | `현재 필터에 해당하는 {대상}가 없습니다` + [필터 초기화]. `{대상}` 은 `기사`, `공시`, `기사/공시` 중 하나 (`ui.empty` 의 `kind`) |
| 빈 결과(S0) | `현재 필터에 해당하는 요약 없음` — **팀 확인 전(U1)** |
| 준비 중 | `준비 중 — {대기 대상} 결과가 생성되면 표시됩니다.` |
| 데이터 오류 | `데이터를 읽지 못했습니다: {경로}` + 다음 줄 `README의 실행 순서에 따라 데이터를 먼저 만드세요.` |
| Q&A | 5-7절 상태 표 |

### 7-3. 화면 안 안내 문구

| 위치 | 문구 | 근거 |
|---|---|---|
| S2·S3 카테고리 교집합 없음 | `이 화면은 {화면 고정 카테고리} 기사만 다룹니다. 사이드바 카테고리에 이 중 하나 이상을 넣으세요.` | IA 4-2절 |
| S4 카테고리 선택에 규제·정책·지정학이 하나 이상 포함(기본값 포함) | `※ 정책 이후 사업 활동이며 인과가 아님` — **팀 확인 전(U3)** | IA 8절 U3, NEWS_DISCLOSURE_MATCHING 3-3절 |
| S5 관련 공시 목록 아래 | `※ 후속 창 연결은 선후 관계이며 인과가 아님` / `※ 수집 끝 90일 이내 기사는 "후속 확인 불가"` | WF S5, NEWS_DISCLOSURE_MATCHING 3-3·3-5절 |
| S1 행사 주간 급증 | `정기 행사 주간의 급증입니다 (바이오 USA 6월, CPHI 10월)` | eda_report 4-1·6절 |
| S1 부상 이슈 표 위 | `최근 3개월 … vs 직전 … · 최근 기사 5건 이상, 증가 건수 순 · 이슈 이름은 LLM 추출 결과입니다 (표본 사람 검수 이름 98.7%)` | AI_EVALUATION 9절 |
| S5 이슈 표 위 | `이슈 단위 집계 전이라 키워드 × 기업 × 월로 묶었습니다` | NEWS_DISCLOSURE_MATCHING D8 |
| S6 범위 | `범위: 5개사 · 공시 원문 있는 공시` | WF S6 |
| AI 생성 결과 옆 | `:gray-badge[AI 생성]` | N6, N3 |

## 8. 접근성·반응형

| 항목 | 규칙 |
|---|---|
| 색만으로 구분하지 않기 | 감성은 배지 글자 + ▲▼●, 공시 분류는 y축 위치 + 호버, 정정은 속 빈 표식 + 배지, 계열 2개 이상은 범례(4개 이하면 선 끝 직접 라벨도) |
| 대비 | 2-3절 표. 글자 4.5:1, 차트 표식 3:1 이상. 색을 바꾸면 다시 계산 |
| 링크 | 2026-11-19 리디자인에서 밑줄을 없앴다(`linkUnderline = false`, `DESIGN.md`). 링크는 초록 글자색과 제목·`[원문]`·`[DART]` 같은 위치로 알아본다 — 색만으로 구분하는 부분이라 재검토 대상(미결 Q15) |
| 표 보기 | 모든 차트 아래 `ui.table_view` (기본 접힘) — 색을 구분하지 못해도 값 확인 가능 |
| 차트 대체 텍스트 | `st.plotly_chart(alt=...)` 에 "무엇을 어떤 기준으로 보여 주는지" 한 문장 (예: `"2023-10 ~ 2026-10 월별 기사 수, 출처별 누적, 중복 제외"`) |
| 글자 크기 | 차트 안 글자 12px 이상, 본문 16px |
| 키보드 | Streamlit 기본 위젯만 사용. S6 관련 뉴스 줄과 S0 결론 띠의 색 머리말에만 `unsafe_allow_html` 스팬을 쓰고 입력 컨트롤은 만들지 않는다 |
| 레이아웃 | `layout="wide"`. 본문 2열(`st.columns`)은 Streamlit이 좁은 화면에서 세로로 쌓는다 |
| 지원 너비 | 1024px 이상을 기준으로 설계. 첫 화면 결론(S0-C1)이 스크롤 없이 보이는지는 1366×768 화면에서 확인 {AC-01} (기준 해상도는 이 문서의 가정) |
| 모바일 | 기준 외. 깨지지 않는 것만 확인 |
| 다크 모드 | 2-1·2-2절 다크 값. 첫 접속 시 Plotly 색 모드가 틀릴 수 있음(미결 Q15) |

## 9. AC 추적표

### 9-1. 기능별 검수 기준 (AC-01~18)

| AC | 기준 요지 | 이 문서의 위치 | 상태 |
|---|---|---|---|
| AC-01 | 스크롤 없이 상단에 기회·위험 결론 | 5-1 S0-C1, 8절 지원 너비 | 구현됨 (`summary_cards.json`) |
| AC-02 | 카드마다 근거 링크 1개 이상 + 상세 화면 이동, 근거 없는 카드 비표시 | 5-1 S0-C2·C3, 4-4 L1·L2 | 구현됨 |
| AC-03 | 월별 기사량(중복 제외) + 급증 시점 + 근거 설명 | 5-2 S1-C1·C2·C3 | 준비됨 |
| AC-04 | 부상 이슈: 이슈명·증가율·기간 | 5-2 S1-C4, 6-2 증가율 | 구현됨 (Q6 해결, LLM 이슈 3개월 비교) |
| AC-05 | 이슈 선택 → 대표 기사 제목·매체·일자·링크 | 5-2 S1-C3, 6-5 | 준비됨 |
| AC-06 | 정책·규제 타임라인: `규제 및 정책` 기사, 날짜순 | 5-3 S2-C2, 6-3 | 준비됨 |
| AC-07 | 기회/위험 라벨 + 표본 검수 정확도 | 5-3 S2-K·C2, 7-1 S2 | 준비됨 |
| AC-08 | 영어 기사 한국어 제목 + 원문 링크, 실시간 번역 없음 | 5-3 S2-C2 영어 기사, 6-5 | 구현됨 — `title_ko` 797건, 표본 30/30 (Q4 해결) |
| AC-09 | 모달리티별 언급 추이 차트 | 5-4 S3-C1 | 구현됨 (모달리티 태그) |
| AC-10 | 기업 × 모달리티 히트맵 + 증설 공시 목록(공시명·제출일·링크) | 5-4 S3-C2·C3 | 구현됨 |
| AC-11 | 5개사 수주·증설·M&A·자금조달 건수, 같은 축, 정정 제외 | 5-5 S4-K·C1 | 준비됨 |
| AC-12 | 기업 선택 → 공시 타임라인 | 5-5 S4-C2 | 준비됨 |
| AC-13 | 수주 계약 금액 시계열 + 미추출 공시 별도 표시 | 5-5 S4-C3 | 구현됨 (`contract_amounts.csv`) |
| AC-14 | 기업별 기사량과 공시 시점을 한 차트에 | 5-6 S5-C1 | 준비됨 |
| AC-15 | 이슈마다 같은 기업·인접 시점 관련 공시 | 5-6 S5-C2 | 준비됨 (임시 이슈) |
| AC-16 | Q&A 답변에 근거 공시명·제출일·DART 링크 | 5-7 S6-C3, 6-5 | 준비됨 |
| AC-17 | 근거 없는 질문 거절 | 5-7 상태 표(거절 3종) | 준비됨 |
| AC-18 | 필터를 바꾸면 모든 차트가 바뀜 | 4-2·4-3절 (화면·컴포넌트별 적용 범위 — S1~S5의 K·C 컴포넌트 모두, S4-C3 포함), 2-7 `uirevision` | 점검 완료 — 필터 조합 17개 × 7화면 = 119회 실행, 오류 0 (`tests/check_dashboard_filters.py`). S0은 U1, S6은 U4 해석 |

### 9-2. 사용자·질문 반영 (AC 2절)

| 항목 | 위치 |
|---|---|
| 첫 화면에서 Core Question 답 | 5-1 S0-C1·C2·C3 |
| 영역별 핵심 질문 5개 각각 화면으로 답함 | 5-2~5-7 각 화면 ① 질문 (IA 6절 대응) |
| SQ 5개 각각 화면으로 답함 | 같음 (SQ1 S1, SQ2 S2·S3, SQ3 S4, SQ4 S5·S6, SQ5 S0) |
| Pain Point P1~P4 해소 | P1 4절 공통 필터·통합 조회, P2 5-3 감성 라벨·5-2 이슈, P3 5-5 같은 축 비교, P4 5-6 관련 공시·5-7 DART 근거 |
| 대표 시나리오를 대시보드 안에서 수행 | 4-4 L1~L9 (S2 → S1 → S4 → S5 → S6 → S0). L4는 S1 부상 이슈에서만 출발한다 (Q18 해결) |
| 처음 보는 사람이 결론 이해 | 5-1 S0-C1, 7절 문구 (Day 7 확인) |

### 9-3. 근거 제시 (AC 3절)

| 항목 | 위치 |
|---|---|
| 모든 이슈·요약 문장에 출처(뉴스 URL 또는 DART 링크) | 6-5 출처 표기, 5-1 카드 근거, 5-2 S1-C3·C4 |
| RAG 답변은 근거와 링크를 함께 | 5-7 답변 상태 |
| 근거 없는 LLM 결과는 요약 카드에 비표시 | 3-2 `ui.conclusion`, 5-1 S0-C2·C3 |

### 9-4. 데이터 해석 (AC 4절, PRD 4절 R1~R5)

| 규칙 | 위치 |
|---|---|
| R1 기사량은 중복(`dup_of`) 제외 | 4-2절 뉴스 규칙(항상 `dup_of IS NULL`), 5-2 S1-K·C1, 7-1 공통 6 |
| R2 기업 단위 분석은 `match_field IN ('title','body')` | 4-2절 기업 규칙(U2), 5-3 S2-C3, 5-6 S5-C1 (`v_company_daily` 대신 기본 테이블, Q2) |
| R3 본문 기반 분석은 `provided`·`team` 범위임을 화면에 표시 | 7-1 공통 2, 6-6 `제목만`/`제목+본문`, 5-3 S2-C2 |
| R4 `cdmo_kw_basis='query'` 는 신뢰도 낮음 | 6-6 `검색어 근거` 배지, 5-3 S2-C2, 5-6 S5-C2 |
| R5 기사량 추이는 `origin` 별로 해석 | 5-2 S1-C1 출처별 누적·키워드 검색(팀원수집) 늘 제외, 7-1 S1 |
| 해외 뉴스는 지정학만 보강되었음을 표시 | 7-1 공통 1, 7-1 S2 |

### 9-5. 과제 제출 전 점검 (AC 5절)

| 항목 | 위치 / UI 관련 여부 |
|---|---|
| 공시 수집 코드 재실행, 기간 정렬 | UI 아님 |
| 대시보드가 API를 직접 호출하지 않고 저장 결과 조회 | 5절 전체(사전 생성 파일·DB 조회만), 예외는 5-7 Q&A(D4) |
| LLM 분류 결과 표본 검수·정확도 기록 | UI 아님(기록은 AI_EVALUATION). 화면 표시는 5-3 S2-K, 7-1 S2 |
| 공시 Q&A 답변에 근거 공시 표시 | 5-7 |
| 필터가 모든 차트에 반영 | 4-3절 |
| 대시보드에 결론 명시 | 5-1 S0-C1 |
| 키가 저장소·발표자료에 없음 | UI 아님. 오류 문구(5-7)에 키 값을 출력하지 않는다 |
| 조원 모두 설계 판단 설명 | UI 아님 |

## 10. 미결 사항

### 10-1. 결정 필요 U1~U5 (IA 8절, 팀 확인 전)

| # | 이 문서에서 따른 제안 | 적용 위치 |
|---|---|---|
| U1 | S0 카드는 전체 기간 기준 사전 생성, 필터는 태그로 거르기만. 없으면 "현재 필터에 해당하는 요약 없음" | 4-3, 5-1 S0-C1·C2·C3, 7-2 |
| U2 | 기업을 일부만 고르면 기업 언급 기사만, 5개 전체면 산업 기사 포함 | 4-2, 4-3 S1·S2·S3 |
| U3 | S4에서 규제·정책·지정학은 후속 창 대응표 + "인과 아님" 문구 | 4-3 S4, 5-5 S4-C1, 7-3 |
| U4 | S6은 사이드바 기간·기업을 기본값으로 보여 주고 해제 가능, 카테고리 미적용 | 4-3 S6, 5-7 S6-K |
| U5 | F5를 S5·S6 두 화면으로 | 5-6, 5-7 |

### 10-2. 새로 찾은 미결 사항

| # | 내용 | 임시 동작 |
|---|---|---|
| Q1 | 카테고리 6개 전체일 때 CDMO 키워드가 없는 기사를 넣을지. 또 S1 기사량의 기준 집합이 정해져 있지 않다: `eda_news_monthly.csv` "전체"는 중복 제외 전체 기사, 급증 판정(`eda_spikes.csv`)은 CDMO 관련 기사·팀원수집 제외 기준 | 포함(U2와 같은 방식). 급증 표식은 막대 높이가 아니라 x 위치에만 표시 |
| Q2 | `v_company_daily` 가 `match_field` 를 거르지 않아 PRD 4절 R2와 맞지 않는다(예: 프레스티지 뉴스 351 vs title/body·중복 제외 69; DB 2026-11-16 빌드, 2026-11-17 집계). 뷰를 고칠지 | S5-C1은 기본 테이블로 집계 |
| Q3 | `rag/qa.py` 입출력 맞추기: 답변의 `(rcept_no)` 표기를 화면에서 `[n]` 으로 바꿈 / "판단 요구"·"인과 미확인"을 나타내는 반환 키가 없어 답변 문구로 판정 / 키·색인 없음이 `sys.exit` 라 `SystemExit` 을 잡아야 함 / 로컬에 `chroma_db/` 없음 / 범위 밖 안내 문구의 기업 순서가 IA 순서와 다름 | 5-7절대로 화면에서 처리. 반환 키 추가 여부는 RAG 담당과 협의 |
| Q4 | **해결 (2026-11-19).** `translate-v3` 로 797건 번역, 표본 30건 30/30. 영어 기사 번역 미실행: `news.title_ko` 797건 모두 NULL, 번역 파일 없음. DB를 다시 빌드하면 `title_ko` 가 비워진다(`docs/data_schema.md` 63행). AC-08을 현재 데이터로 충족할 수 없다 | 원제목 + `번역 준비 중` |
| Q5 | **해결 (2026-11-18~19).** `data/processed/summary_cards.json` (`analysis/build_summary_cards.py`), 지표는 기회·위험 기사·연결 공시·급증 시점. S0 결론·카드 산출물의 파일명·스키마, S0 지표 "분석 기사·연결 공시" 정의 | 5-1절 필드 목록을 산출물 정의에 쓰도록 제안. 화면은 준비 중 |
| Q6 | **해결 (2026-11-19).** LLM 이슈(대표 이름), 최근 91일 vs 직전 91일, 최근 5건 이상, 증가 건수 순. 부상 이슈 증가율: 직전 기간 길이, 이슈 최소 기사 수(AI_CLASSIFICATION 346행 미정), LLM 이슈와 임시 이슈 중 무엇을 쓸지. WF는 LLM 이슈 전에 임시 이슈 증가율로 대체하라고 적었다 | 준비 중 (WF 대체 표시도 이 값이 정해진 뒤, 5-2 S1-C4) |
| Q7 | S2 "언급 기업 막대"의 해외 CDMO 언급 수를 셀 데이터 정의가 없다 | **해결 (2026-11-19).** 해외 부분은 화면에서 뺌 — 5개사만 표시 (DECISIONS D-38) |
| Q8 | 카테고리 → `event_class` 거르기에 대응표 직접·후속 열을 합쳐 쓰는 해석, 리스크 공시(키워드 빈 값) 처리 | 4-2·4-3절 표대로 (S3 증설 공시는 IA 4-2절대로 S3 교집합 규칙을 따름) |
| Q9 | 행사 주간 표기 기준이 산업 전체 급증 4건(eda_report 4-1절)에만 있다. 키워드·기업 급증의 행사 판정 기준 없음 | 산업 전체 4건만 `행사` 주석 |
| Q10 | 5개사 표기 순서가 문서·코드마다 다르다(IA·PRD, `collect/config.py`·DB, `rag/qa.py`) | IA 4-1절 순서 |
| Q11 | L8("이 공시에 질문")이 사이드바 필터를 바꿀지, S6 전용 범위만 바꿀지 (IA 5절은 "필터 값을 바꾼 뒤 이동"이라 적음) | S6 전용 범위(`qa_scope_override`)만 바꿈 |
| Q12 | 연결된 기사 수가 CSV 고유 URL 기준 1,441건(`data/processed/news_disclosure_links.csv` 7,135행, 2026-11-17 집계), NEWS_DISCLOSURE_MATCHING 3-2절은 1,521건(53.4%)으로 다르다. "연결 없는 기사 비율"의 분모(매칭 대상 기사 2,849건)가 CSV에 없다 | **해결 (2026-11-19).** 두 수는 단위 차이였다: 매칭 스크립트 요약은 (url, 기업) 쌍, 화면은 고유 url로 셌다(2개 이상 기업과 연결된 기사 66건). **기사 × 기업 단위로 통일** — 연결 1,521 / 대상 2,849, 연결 없음 46.6%. 분모는 DB에서 필터를 적용해 계산 (5-6절 S5-K) |
| Q13 | 감성 검수자 일치도 수치가 AI_EVALUATION과 `data/eval/sentiment_eval_result.md` 에서 다르다 | 화면에 일치도는 표시하지 않음 |
| Q14 | 기회 파랑·위험 빨강이 한국 증시 관례(상승 빨강·하락 파랑)와 반대로 읽힐 수 있다 | 2-2절 색 + 라벨·기호 병기 |
| Q15 | 실행 화면에서 확인할 것: `st.context.theme.type` 첫 접속 정확도, 라이트/다크 전환 메뉴 동작, `st.caption` 글자 대비, 마크다운 링크의 새 탭 열림, `border`(3:1 미달, 2-3절)만으로 입력 위젯 경계를 알아볼 수 있는지 | 구현 후 확인해 이 문서에 기록 |
| Q16 | **해결.** 골격·S1~S6 뷰 모두 main 에 있음. 골격 파일: `dashboard/app.py`·`core/ui.py` 없음, S1·S4 뷰 없음, 뷰 5개는 스테이징만 되어 있고 작업 기록이 없다 | 3-1절 구성으로 작성 |
| Q17 | **해결 (2026-11-19).** IA·WF·이 문서를 main 코드에 맞춰 함께 갱신함. 문서 정리: WF ⏳ 표시의 IA 7절 반영, TECH_STACK 작성 전 (masterplan 3-2절 상태·WF 상태 줄은 2026-11-17 갱신함) | 담당 문서에서 갱신 |
| Q18 | **부분 해결 (2026-11-19).** S1-C4 구현으로 L4 출발점이 생김. S2·S3 출발점은 두지 않음. IA L4는 "관련 공시" 출발점을 S1·S2·S3 이슈(또는 임시 이슈)로 적었지만, WF는 [관련 공시 →] 를 S1 부상 이슈에만 그렸다. S2·S3에 L4 출발점(예: S2-C2 행, S3-C1·C3)을 둘지 정해야 한다. 또 S1-C4가 준비 중(Q6)인 동안은 L4 출발점이 하나도 없다 | S1-C4에만 둠. 그전에는 S5를 직접 연다. 결정 후 IA L4 또는 WF S2·S3을 담당 문서에서 맞춘다 |
