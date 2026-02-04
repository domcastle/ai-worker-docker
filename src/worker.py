#!/usr/bin/env python3
import os
import json
import time
import tempfile
import subprocess
import redis
from minio import Minio

# 환경변수 로드
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_QUEUE = os.getenv("REDIS_QUEUE", "video_processing_jobs")

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "justicadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "justicadmin123")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "videos")

FFMPEG_SCRIPT = os.getenv("FFMPEG_SCRIPT", "/opt/ai/scripts/run_ffmpeg_shorts.sh")
CAPTION_SCRIPT = os.getenv("CAPTION_SCRIPT", "/opt/ai/worker/generate_caption.py")

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True,
)

minio = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False,
)

def download_object(bucket, key, dst):
    try:
        obj = minio.get_object(bucket, key)
        with open(dst, "wb") as f:
            for c in obj.stream(1024 * 1024):
                f.write(c)
        obj.close()
        obj.release_conn()
    except Exception as e:
        print(f"❌ Download failed: {e}")
        raise

def upload_object(bucket, key, src):
    minio.fput_object(bucket, key, src, content_type="video/mp4")

def process_job(job: dict):
    input_key = job["input_key"]
    output_key = job["output_key"]
    variant = job.get("variant", "v1")

    tmp_input = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    tmp_output = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name

    try:
        print(f"⬇️ Downloading {input_key}...")
        download_object(MINIO_BUCKET, input_key, tmp_input)

        env = os.environ.copy()
        env["CAPTION_VARIANT"] = variant
        
        print("🧠 Generating caption...")
        try:
            caption = subprocess.check_output(
                ["python3", CAPTION_SCRIPT, tmp_input],
                text=True,
                timeout=600,
                env=env,
            ).strip()
        except subprocess.CalledProcessError:
            caption = ""
        
        if not caption:
            caption = "편집된 영상입니다"

        print(f"📝 Caption ({variant}): {caption}")

        print("🎬 Processing video with FFmpeg...")
        subprocess.run(
            [
                FFMPEG_SCRIPT,
                tmp_input,
                tmp_output,
                "", 
                "", 
                caption,
            ],
            check=True,
        )

        print(f"⬆️ Uploading to {output_key}...")
        upload_object(MINIO_BUCKET, output_key, tmp_output)
        print("✅ Job completed successfully.")

    except Exception as e:
        print(f"❌ Error processing job: {e}")
    finally:
        for f in (tmp_input, tmp_output):
            if os.path.exists(f):
                os.remove(f)

def main():
    print("🚀 AI Worker started (Hybrid Mode)")
    print(f"🔌 Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
    print(f"💾 Connected to Minio at {MINIO_ENDPOINT}")

    while True:
        try:
            result = redis_client.brpop(REDIS_QUEUE, timeout=5)
            if result:
                _, raw = result
                job = json.loads(raw)
                print(f"📥 Received job: {job}")
                process_job(job)
        except redis.exceptions.ConnectionError:
            print("⚠️ Redis connection lost. Retrying in 5s...")
            time.sleep(5)
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()