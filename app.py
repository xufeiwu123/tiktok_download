from flask import Flask, request, jsonify, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from celery import Celery
import logging
import os
import hashlib

from utils import get_video_url

app = Flask(__name__)
app.config.from_object('config.Config')

logging.basicConfig(level=logging.INFO)

# 请求频率限制
limiter = Limiter(get_remote_address, app=app)

# 缓存配置
cache = Cache(app)

# Celery 配置
celery = Celery(__name__, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

# 视频保存路径
SAVE_DIR = "/tmp/tiktok_videos"
os.makedirs(SAVE_DIR, exist_ok=True)


@app.route('/download', methods=['POST'])
@limiter.limit(app.config['LIMTER_DEFAULT_LIMIT'])
def download_video():
    data = request.json
    tiktok_url = data.get("url")

    if not tiktok_url:
        return jsonify({"status": "error", "message": "URL 是必填的"}), 400

    task = download_video_task.apply_async(args=[tiktok_url])
    return jsonify({"status": "success", "task_id": task.id})


@app.route('/status', methods=['GET'])
def check_status():
    task_id = request.args.get("task_id")
    task = download_video_task.AsyncResult(task_id)

    if task.state == "PENDING":
        return jsonify({"status": "pending"})
    elif task.state == "SUCCESS":
        return jsonify({"status": "success", "file_url": task.result})
    elif task.state == "FAILURE":
        return jsonify({"status": "failed", "error": str(task.info)})
    else:
        return jsonify({"status": task.state})


@app.route("/file/<filename>")
def serve_file(filename):
    return send_from_directory(SAVE_DIR, filename, as_attachment=True)


@celery.task(bind=True, max_retries=3)
def download_video_task(self, tiktok_url):
    try:
        # 如果已缓存，直接返回
        key = hashlib.md5(tiktok_url.encode()).hexdigest()
        cached_path = os.path.join(SAVE_DIR, key + ".mp4")
        if os.path.exists(cached_path):
            return f"/file/{key}.mp4"

        # 获取视频直链
        video_url = get_video_url(tiktok_url)
        logging.info(f"解析成功: {video_url}")

        resp = requests.get(video_url, timeout=15)
        with open(cached_path, "wb") as f:
            f.write(resp.content)

        return f"/file/{key}.mp4"
    except Exception as e:
        logging.error(f"任务失败: {str(e)}")
        raise self.retry(exc=e, countdown=10)


@app.after_request
def after_request(response):
    # 自动清理临时视频文件（可改为定时任务）
    try:
        for fname in os.listdir(SAVE_DIR):
            fpath = os.path.join(SAVE_DIR, fname)
            if os.path.isfile(fpath):
                if os.path.getmtime(fpath) + 3600 < os.path.getmtime(fpath):  # 超过一小时
                    os.remove(fpath)
    except:
        pass
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
