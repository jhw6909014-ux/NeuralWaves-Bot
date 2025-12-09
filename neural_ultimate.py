import os
import time
import random
import asyncio
import subprocess
import ssl
import sys

# 自動安裝缺少的套件 (以防萬一)
try:
    import feedparser
    import edge_tts
    import google.generativeai as genai
    import certifi
    from gtts import gTTS
except ImportError:
    pass

# ==========================================
# ⚡ NEURAL GITHUB BOT (單次執行版)
# ==========================================

# 重點修改：從 GitHub Secrets 讀取金鑰，而不是寫死
API_KEY = os.environ.get("GEMINI_API_KEY") 
if not API_KEY:
    print("❌ 錯誤：找不到 GEMINI_API_KEY，請檢查 GitHub Secrets 設定")
    sys.exit(1)

RSS_URLS = ["https://technews.tw/feed/", "https://www.ithome.com.tw/rss"]
BG_VIDEO = "shorts_bg.mp4"
BGM_AUDIO = "bgm.mp3"

genai.configure(api_key=API_KEY)

async def robust_tts(text, filename="temp_voice.mp3"):
    print(f"🗣️ [TTS] 生成語音: {text[:10]}...")
    try:
        # 嘗試 Edge TTS
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        comm = edge_tts.Communicate(text, "zh-TW-YunJheNeural")
        await comm.save(filename)
        return True
    except Exception:
        # 失敗則使用 Google TTS
        try:
            tts = gTTS(text=text, lang='zh-TW')
            tts.save(filename)
            return True
        except:
            return False

async def main():
    print("🚀 GitHub Action 任務開始...")

    # 1. 抓新聞
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    news_list = []
    try:
        for url in RSS_URLS:
            f = feedparser.parse(url)
            if f.entries: news_list.extend(f.entries[:2])
    except: pass
    
    if not news_list:
        title, summary = "AI自動廣播", "目前沒有最新新聞。"
    else:
        item = random.choice(news_list)
        title, summary = item.title, item.summary

    # 2. 寫腳本
    print("🧠 撰寫腳本中...")
    prompt = f"你是Podcast主持人，將這則新聞改寫成一段30秒內的口語講稿，繁體中文，無標題直接講內容：{title} - {summary}"
    try:
        resp = model.generate_content(prompt)
        script = resp.text.replace("*", "").strip()
    except:
        script = f"大家好，今天的新聞是{title}。"

    # 3. 轉語音
    if not await robust_tts(script):
        print("❌ TTS 失敗"); return

    # 4. 剪輯 (GitHub 環境已有 FFmpeg)
    output_file = f"Ultimate_{int(time.time())}.mp4"
    print("🎬 開始剪輯...")
    
    inputs = ["-stream_loop", "-1", "-i", BG_VIDEO, "-i", "temp_voice.mp3"]
    filter_complex = '-map 0:v -map 1:a'
    
    if os.path.exists(BGM_AUDIO):
        inputs.extend(["-stream_loop", "-1", "-i", BGM_AUDIO])
        filter_complex = '-filter_complex "[2:a]volume=0.1[bg];[1:a][bg]amix=inputs=2:duration=first[aout]" -map 0:v -map "[aout]"'

    # 注意：這裡加上 -t 58 確保影片不超過 60 秒 (Shorts 限制)
    cmd = ["ffmpeg", "-y"] + inputs + filter_complex.split() + [
        "-t", "58", "-c:v", "libx264", "-preset", "ultrafast", "-shortest", output_file
    ]
    
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    if os.path.exists(output_file):
        print(f"🎉 影片生成成功: {output_file}")
    else:
        print("❌ 影片生成失敗")

if __name__ == "__main__":
    asyncio.run(main())
