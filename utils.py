import re
import requests

def get_video_url(tiktok_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 12_1_2 like Mac OS X)"
    }
    try:
        resp = requests.get(tiktok_url, headers=headers, timeout=10)
        html = resp.text

        # 匹配无水印视频链接
        video_url = re.search(r'"playAddr":"(.*?)"', html)
        if not video_url:
            raise Exception("视频链接未找到")
        real_url = video_url.group(1).replace('\\u0026', '&').replace('\\', '')

        return real_url
    except Exception as e:
        raise Exception(f"解析失败: {str(e)}"
