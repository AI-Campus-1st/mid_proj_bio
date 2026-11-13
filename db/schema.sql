-- 뉴스·공시 통합 스키마 (SQLite)
-- 기간: 제공 뉴스와 동일 (meta 테이블의 period_start ~ period_end)
-- 날짜는 모두 한국시간 기준 'YYYY-MM-DD' 문자열이다.

CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- 분석 대상 기업 (5개사)
CREATE TABLE companies (
    corp_code  TEXT PRIMARY KEY,      -- DART 고유번호 (8자리)
    corp_name  TEXT NOT NULL UNIQUE,  -- DART 회사명
    stock_code TEXT NOT NULL,         -- 종목코드 (6자리)
    corp_cls   TEXT,                  -- Y 유가증권, K 코스닥
    sector     TEXT                   -- 분석 범위 (CDMO)
);

-- 뉴스 (통합본 03_CDMO_news_3y 기준: 제공 + 팀원 수집 + 구글 뉴스 수집 + 해외 영어 뉴스)
CREATE TABLE news (
    news_id        INTEGER PRIMARY KEY,
    origin         TEXT NOT NULL
                   CHECK (origin IN ('provided', 'team', 'google_company', 'google_cdmo',
                                     'google_global')),
                                      -- provided: 제공 뉴스 / team: 팀원 수집 (둘 다 본문 있음)
                                      -- google_company: 5개사 기업명 검색 / google_cdmo: CDMO 키워드 검색 (제목만)
                                      -- google_global: 해외(영어) 검색, 구글 뉴스 미국판 (제목만)
    title          TEXT NOT NULL,
    body           TEXT,              -- 본문 전문. google_* 는 NULL
    url            TEXT NOT NULL UNIQUE,
    published_at   TEXT NOT NULL,     -- 'YYYY-MM-DDTHH:MM:SS' (KST)
    published_date TEXT NOT NULL,     -- 'YYYY-MM-DD' (KST)
    press          TEXT,              -- 매체명
    body_len       INTEGER NOT NULL DEFAULT 0,
    cdmo_mention   INTEGER NOT NULL DEFAULT 0,  -- 제목·본문에 CDMO/위탁(개발)생산 표현이 있으면 1
    title_norm     TEXT,              -- 중복 판정용 정규화 제목 (한글·영문·숫자만)
    dup_of         INTEGER REFERENCES news(news_id),
                                      -- 같은 정규화 제목이 7일 이내에 먼저 나온 기사의 news_id. 대표 기사는 NULL
    search_terms   TEXT,              -- 수집에 쓴 검색어·기업명 ('; ' 구분). 제공 뉴스는 NULL (news_keywords 참고)
    cdmo_rel_basis TEXT NOT NULL,     -- CDMO 관련 근거: title / body / query / none
    cdmo_kw_basis  TEXT NOT NULL,     -- CDMO 키워드 근거: title / body / query / none (query 는 신뢰도 낮음)
    lang           TEXT NOT NULL DEFAULT 'ko' CHECK (lang IN ('ko', 'en')),
                                      -- 기사 언어. en(해외 검색)은 대시보드에서 한국어로 번역해 보여준다
    title_ko       TEXT               -- 한국어 번역 제목 캐시 (en 기사용). 적재 시 NULL, 번역 단계에서 채운다
);
CREATE INDEX idx_news_date ON news(published_date);
CREATE INDEX idx_news_origin ON news(origin);
CREATE INDEX idx_news_lang ON news(lang);

-- 뉴스 ↔ CDMO 키워드 (조에서 정의한 6개, 규칙 기반 재분류 결과). 키워드가 없는 기사는 행이 없다
CREATE TABLE news_cdmo_keywords (
    news_id    INTEGER NOT NULL REFERENCES news(news_id),
    keyword    TEXT NOT NULL,         -- CDMO 규제·정책 / 지정학 / 모달리티 / 생산능력 / 수주 / 경쟁 구도
    category   TEXT NOT NULL,         -- 규제 및 정책 / 기술 및 트렌드 / 시장 및 경쟁
    is_primary INTEGER NOT NULL,      -- 대표 키워드이면 1 (기사당 1개)
    PRIMARY KEY (news_id, keyword)
);
CREATE INDEX idx_nck_kw ON news_cdmo_keywords(keyword);

-- 뉴스 ↔ 원래 수집 키워드 (가이드 2-3의 바이오 키워드). 제공 뉴스만 해당
CREATE TABLE news_keywords (
    news_id  INTEGER NOT NULL REFERENCES news(news_id),
    keyword  TEXT NOT NULL,           -- 바이오 규제 / 바이오 특허 / 바이오 R&D / 바이오 M&A / 바이오 투자 유치
    category TEXT NOT NULL,           -- 규제 및 정책 / 기술 및 트렌드 / 시장 및 경쟁
    PRIMARY KEY (news_id, keyword)
);

-- 뉴스 ↔ 기업. 한 기사가 여러 기업을 언급할 수 있다
CREATE TABLE news_companies (
    news_id     INTEGER NOT NULL REFERENCES news(news_id),
    corp_code   TEXT NOT NULL REFERENCES companies(corp_code),
    match_field TEXT NOT NULL CHECK (match_field IN ('title', 'body', 'query')),
                                      -- title: 제목에 기업명 / body: 본문에만 / query: 기업명 검색 결과이나 제목에는 없음
    PRIMARY KEY (news_id, corp_code)
);
CREATE INDEX idx_nc_corp ON news_companies(corp_code);

-- 공시 목록 (DART list.json)
CREATE TABLE disclosures (
    rcept_no     TEXT PRIMARY KEY,    -- 접수번호 (14자리)
    corp_code    TEXT NOT NULL REFERENCES companies(corp_code),
    rcept_date   TEXT NOT NULL,       -- 접수일 'YYYY-MM-DD'
    report_nm    TEXT NOT NULL,       -- 보고서명 (공백 정리)
    pblntf_ty    TEXT NOT NULL,       -- 공시 유형 코드 A~J
    pblntf_ty_nm TEXT NOT NULL,       -- 정기공시 / 주요사항보고 / 거래소공시 ...
    flr_nm       TEXT,                -- 제출인
    rm           TEXT,                -- 비고 (유: 유가증권시장본부 소관 등)
    is_amended   INTEGER NOT NULL,    -- 정정 공시이면 1
    event_class  TEXT NOT NULL,       -- 수주 / 증설 / M&A·구조개편 / 실적 / ... (analysis/disclosure_weights.py 규칙)
    event_weight INTEGER NOT NULL,    -- CDMO 사업 직접성 가중치 0~5 (정정 공시는 0)
    url          TEXT NOT NULL,       -- DART 뷰어 링크
    has_document INTEGER NOT NULL DEFAULT 0,  -- 원문을 확보했으면 1
    doc_chars    INTEGER NOT NULL DEFAULT 0   -- 원문 텍스트 글자 수 (첨부 포함)
);
CREATE INDEX idx_disc_corp_date ON disclosures(corp_code, rcept_date);
CREATE INDEX idx_disc_class ON disclosures(event_class);

-- 공시 원문 텍스트 (DART document.xml 의 zip 안 파일 1개 = 1행)
CREATE TABLE disclosure_documents (
    rcept_no  TEXT NOT NULL REFERENCES disclosures(rcept_no),
    seq       INTEGER NOT NULL,       -- 1 = 본문, 2 이상 = 첨부(감사보고서 등)
    file_name TEXT NOT NULL,
    text      TEXT NOT NULL,          -- 태그 제거 텍스트. 표는 행마다 줄바꿈, 칸은 ' | ' 로 구분
    n_chars   INTEGER NOT NULL,
    PRIMARY KEY (rcept_no, seq)
);

-- 통합 뷰: 뉴스와 공시를 같은 컬럼으로 조회한다 (기업 단위로 1행)
-- 기업이 매핑되지 않은 뉴스는 corp_code 가 NULL 인 1행으로 나온다.
CREATE VIEW v_documents AS
SELECT 'news' AS doc_type,
       'N' || n.news_id AS doc_id,
       nc.corp_code AS corp_code,
       n.published_date AS doc_date,
       n.title AS title,
       n.body AS body,
       n.press AS source,
       n.url AS url,
       (SELECT category FROM news_cdmo_keywords k
         WHERE k.news_id = n.news_id AND k.is_primary = 1) AS category,
       (SELECT keyword FROM news_cdmo_keywords k
         WHERE k.news_id = n.news_id AND k.is_primary = 1) AS keyword,
       n.origin AS subtype,
       n.dup_of IS NOT NULL AS is_duplicate,
       n.lang AS lang,
       n.title_ko AS title_ko
FROM news n
LEFT JOIN news_companies nc ON nc.news_id = n.news_id
UNION ALL
SELECT 'disclosure',
       'D' || d.rcept_no,
       d.corp_code,
       d.rcept_date,
       d.report_nm,
       (SELECT text FROM disclosure_documents x WHERE x.rcept_no = d.rcept_no AND x.seq = 1),
       d.flr_nm,
       d.url,
       d.event_class,
       NULL,
       d.pblntf_ty_nm,
       d.is_amended,
       'ko',
       NULL
FROM disclosures d;

-- 기업 × 일자별 뉴스·공시 건수 (EDA·시점 비교용). 뉴스는 중복 제거 후 기준
CREATE VIEW v_company_daily AS
SELECT c.corp_code, c.corp_name, t.doc_date,
       SUM(t.doc_type = 'news') AS news_cnt,
       SUM(t.doc_type = 'disclosure') AS disclosure_cnt
FROM (
    SELECT nc.corp_code AS corp_code, n.published_date AS doc_date, 'news' AS doc_type
    FROM news n JOIN news_companies nc ON nc.news_id = n.news_id
    WHERE n.dup_of IS NULL
    UNION ALL
    SELECT corp_code, rcept_date, 'disclosure' FROM disclosures
) t JOIN companies c ON c.corp_code = t.corp_code
GROUP BY c.corp_code, t.doc_date;
