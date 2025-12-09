import os
import time
import random
import asyncio
import subprocess
import ssl
import sys
import glob

# 自動安裝缺少的套件
try:
    import feedparser
    import edge_tts
    import google.generativeai as genai
    import certifi
    from gtts import gTTS
except ImportError:
    pass

# ==========================================
# ⚡ NEURAL GITHUB BOT (無敵偵錯版)
# ==========================================

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("❌ [致命錯誤] 找不到 GEMINI_API_KEY，請檢查 GitHub Secrets！")
    sys.exit(1)

genai.configure(api_key=API_KEY)

# --- 核心功能：自動尋找素材 (解決檔名大小寫問題) ---
def find_file(extension):
    # 搜尋當前目錄下所有的檔案
    files = glob.glob(f"*{extension}") + glob.glob(f"*{extension.upper()}")
    if files:
        print(f"✅ 找到素材 ({extension}): {files[0]}")
        return files[0]
    return None

async def robust_tts(text, filename="temp_voice.mp3"):
    print(f"🗣️ [TTS] 生成語音: {text[:10]}...")
    try:
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        comm = edge_tts.Communicate(text, "zh-TW-YunJheNeural")
        await comm.save(filename)
        return True
    except Exception as e:
        print(f"⚠️ Edge TTS 失敗 ({e})，切換 Google TTS...")
        try:
            tts = gTTS(text=text, lang='zh-TW')
            tts.save(filename)
            return True
        except Exception as e2:
            print(f"❌ TTS 全面失敗: {e2}")
            return False

async def main():
    print("🚀 任務開始：環境檢查中...")
    
    # 1. 自動尋找背景影片與音樂
    bg_video = find_file(".mp4")
    bg_music = find_file(".mp3")
    
    if not bg_video:
        print("❌ [錯誤] 找不到任何 .mp4 影片檔！請確認你有上傳背景影片(例如 shorts_bg.mp4)")
        # 列出當前所有檔案幫忙除錯
        print("📂 當前目錄檔案列表:", os.listdir("."))
        sys.exit(1)

    # 2. 抓新聞
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    news_list = []
    try:
        # 增加更多來源確保有東西抓
        urls = ["https://technews.tw/feed/", "https://www.ithome.com.tw/rss", "https://feeds.feedburner.com/engadget/cstc"]
        for url in urls:
            f = feedparser.parse(url)
            if f.entries: news_list.extend(f.entries[:2])
    except: pass
    
    if not news_list:
        title, summary = "AI自動廣播", "目前沒有最新新聞。"
    else:
        item = random.choice(news_list)
        title, summary = item.title, item.summary

    # 3. 寫腳本
    print("🧠 撰寫腳本中...")
    prompt = f"你是Podcast主持人，將這則新聞改寫成一段30秒內的口語講稿，繁體中文，無標題直接講內容：{title} - {summary}"
    try:
        resp = model.generate_content(prompt)
        script = resp.text.replace("*", "").strip()
    except Exception as e:
        print(f"⚠️ AI 生成失敗: {e}")
        script = f"大家好，今天的新聞標題是{title}。"

    # 4. 轉語音
    if not await robust_tts(script):
        sys.exit(1)

    # 5. 剪輯 (關鍵修改：顯示錯誤訊息)
    output_file = f"Ultimate_{int(time.time())}.mp4"
    print(f"🎬 開始剪輯 (使用影片: {bg_video})...")
    
    inputs = ["-stream_loop", "-1", "-i", bg_video, "-i", "temp_voice.mp3"]
    filter_complex = '-map 0:v -map 1:a'
    
    if bg_music:
        print(f"🎵 加入背景音樂: {bg_music}")
        inputs.extend(["-stream_loop", "-1", "-i", bg_music])
        filter_complex = '-filter_complex "[2:a]volume=0.1[bg];[1:a][bg]amix=inputs=2:duration=first[aout]" -map 0:v -map "[aout]"'

    cmd = ["ffmpeg", "-y"] + inputs + filter_complex.split() + [
        "-t", "58", "-c:v", "libx264", "-preset", "ultrafast", "-shortest", output_file
    ]
    
    # 這裡不再隱藏錯誤 (stderr=subprocess.PIPE)
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    if result.returncode == 0 and os.path.exists(output_file):
        print(f"🎉 影片生成成功: {output_file}")
        print(f"📊 檔案大小: {os.path.getsize(output_file)} bytes")
    else:
        print("❌ [FFmpeg 失敗] 請查看下方錯誤訊息：")
        print("------------------------------------------------")
        print(result.stderr) # 這裡會把真正的錯誤原因印出來
        print("------------------------------------------------")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
