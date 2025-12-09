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
# ⚡ NEURAL GITHUB BOT (FFmpeg 修復版)
# ==========================================

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("❌ [致命錯誤] 找不到 GEMINI_API_KEY，請檢查 GitHub Secrets！")
    sys.exit(1)

genai.configure(api_key=API_KEY)

# --- 核心功能：自動尋找素材 ---
def find_file(extension):
    files = glob.glob(f"*{extension}") + glob.glob(f"*{extension.upper()}")
    if files:
        print(f"✅ 找到素材 ({extension}): {files[0]}")
        return files[0]
    return None

async def robust_tts(text, filename="temp_voice.mp3"):
    print(f"🗣️ [TTS] 生成語音: {text[:10]}...")
    try:
        # 修正：移除 SSL context，讓 edge-tts 使用預設連線，在 Linux 上通常較穩
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
    
    bg_video = find_file(".mp4")
    bg_music = find_file(".mp3")
    
    if not bg_video:
        print("❌ [錯誤] 找不到任何 .mp4 影片檔！")
        sys.exit(1)

    # 1. 抓新聞
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    news_list = []
    try:
        urls = ["https://technews.tw/feed/", "https://www.ithome.com.tw/rss"]
        for url in urls:
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
        script = f"大家好，今天的新聞標題是{title}。"

    # 3. 轉語音
    if not await robust_tts(script):
        sys.exit(1)

    # 4. 剪輯 (關鍵修復點：手動組裝 List)
    output_file = f"Ultimate_{int(time.time())}.mp4"
    print(f"🎬 開始剪輯 (使用影片: {bg_video})...")
    
    # 基礎指令
    cmd = ["ffmpeg", "-y"]
    
    # 輸入 0: 背景影片
    cmd.extend(["-stream_loop", "-1", "-i", bg_video])
    # 輸入 1: 人聲
    cmd.extend(["-i", "temp_voice.mp3"])
    
    # 判斷是否有背景音樂
    if bg_music:
        print(f"🎵 加入背景音樂: {bg_music}")
        # 輸入 2: 背景音樂
        cmd.extend(["-stream_loop", "-1", "-i", bg_music])
        
        # 複雜濾鏡 (注意：不要自己加引號，subprocess 會處理)
        filter_str = "[2:a]volume=0.1[bg];[1:a][bg]amix=inputs=2:duration=first[aout]"
        cmd.extend(["-filter_complex", filter_str, "-map", "0:v", "-map", "[aout]"])
    else:
        # 沒有背景音樂，直接對應
        cmd.extend(["-map", "0:v", "-map", "1:a"])

    # 最後加上編碼參數
    cmd.extend(["-t", "58", "-c:v", "libx264", "-preset", "ultrafast", "-shortest", output_file])
    
    # 執行指令並捕獲錯誤
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    if result.returncode == 0 and os.path.exists(output_file):
        print(f"🎉 影片生成成功: {output_file}")
        print(f"📊 檔案大小: {os.path.getsize(output_file)} bytes")
    else:
        print("❌ [FFmpeg 失敗] 錯誤日誌如下：")
        print(result.stderr)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
