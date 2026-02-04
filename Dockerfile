# Dockerfile
FROM python:3.10-slim

# 1. 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    ffmpeg \
    fontconfig \
    unzip \
    curl \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# 2. 폰트 설치
RUN mkdir -p /usr/share/fonts/paperlogy && \
    curl -L -o /tmp/Paperlogy.zip https://github.com/Freesentation/paperlogy/raw/refs/heads/main/Paperlogy-1.000.zip && \
    unzip /tmp/Paperlogy.zip -d /tmp/paperlogy && \
    find /tmp/paperlogy -name "*.ttf" -exec cp {} /usr/share/fonts/paperlogy/ \; && \
    fc-cache -fv && \
    rm -rf /tmp/Paperlogy.zip /tmp/paperlogy

# 3. 작업 디렉토리
WORKDIR /opt/ai

# 4. 라이브러리 설치
RUN pip install --no-cache-dir redis minio requests

# 5. 소스 코드 복사
COPY src/worker.py /opt/ai/worker.py
COPY src/generate_caption.py /opt/ai/worker/generate_caption.py
COPY src/scripts/run_ffmpeg_shorts.sh /opt/ai/scripts/run_ffmpeg_shorts.sh
COPY src/scripts/cleanup_ai.sh /opt/ai/scripts/cleanup_ai.sh

# 6. 실행 권한 및 환경 변수
RUN chmod +x /opt/ai/scripts/*.sh

ENV PYTHONUNBUFFERED=1
ENV FFMPEG_SCRIPT=/opt/ai/scripts/run_ffmpeg_shorts.sh
ENV CAPTION_SCRIPT=/opt/ai/worker/generate_caption.py

CMD ["python3", "/opt/ai/worker.py"]