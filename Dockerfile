# syntax=docker/dockerfile:1
# 대시보드 실행 이미지 — ghcr.io/ai-campus-1st/mid_proj_bio (비공개)
#
# 코드는 이 저장소에서, 공개하지 않는 데이터(통합 DB · 공시 RAG 색인 · 기사 URL·제목이 든 산출물)는
# 비공개 데이터 이미지(Dockerfile.data)에서 가져와 합친다. 설명: docs/06_technical/DEPLOYMENT.md
# 복사 대상은 .dockerignore 의 허용 목록으로 제한한다 (.env 등 비밀 파일은 빌드 맥락에 들어오지 않는다).

ARG DATA_IMAGE=ghcr.io/ai-campus-1st/mid_proj_bio-data:latest
FROM ${DATA_IMAGE} AS data

FROM python:3.12-slim
LABEL org.opencontainers.image.source="https://github.com/AI-Campus-1st/mid_proj_bio" \
      org.opencontainers.image.description="Bio CDMO issue dashboard (Streamlit)"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
RUN useradd --create-home --uid 10001 app

COPY requirements-app.txt .
RUN pip install -r requirements-app.txt

# 코드 · 테마 · 공개 산출물 (저장소)
COPY .streamlit/config.toml .streamlit/config.toml
COPY collect/config.py collect/config.py
COPY rag/build_index.py rag/qa.py rag/
COPY dashboard/ dashboard/
COPY data/processed/ data/processed/

# 비공개 데이터 (데이터 이미지). 색인은 chromadb 가 열 때 쓰기 권한이 필요할 수 있어 app 사용자 소유로 둔다
COPY --from=data /data/ data/
COPY --from=data --chown=10001:10001 /chroma_db/ chroma_db/

USER app
EXPOSE 8501

# Render 는 PORT 환경변수로 포트를 넘긴다. 로컬에서는 8501
# 배포 이미지는 코드가 바뀌지 않으므로 파일 감시를 끈다 (켜 두면 컨테이너에서 폴링 방식으로 계속 검사한다)
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
  CMD python -c "import os,urllib.request;urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\",\"8501\")}/_stcore/health')"
CMD streamlit run dashboard/app.py --server.address=0.0.0.0 --server.port=${PORT:-8501} --server.headless=true --server.fileWatcherType=none --browser.gatherUsageStats=false
