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
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.oauth2.credentials import Credentials
except ImportError:
    pass

# ==========================================
# 💎 NEURAL GITHUB BOT (V9.0 High-End 淨化版)
# ==========================================

# 讀取金鑰
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
YT_CLIENT_ID = os.environ.get("YT_CLIENT_ID")
YT_CLIENT_SECRET = os.environ.get("YT_CLIENT_SECRET")
YT_REFRESH_TOKEN = os.environ.get("YT_REFRESH_TOKEN")

if not GEMINI_KEY:
    print("❌ [錯誤] 缺少 GEMINI_API_KEY"); sys.exit(1)

genai.configure(api_key=GEMINI_KEY)

# --- 上傳功能 ---
def upload_to_youtube(video_path, title, description):
    if not (YT_CLIENT_ID and YT_CLIENT_SECRET and YT_REFRESH_TOKEN):
        print("⚠️ 缺少 YouTube 金鑰，跳過上傳")
        return

    print(f"🚀 上傳中: {title}...")
    try:
        creds = Credentials(
            None,
            refresh_token=YT_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=YT_CLIENT_ID,
            client_secret=YT_CLIENT_SECRET
        )
        youtube = build('youtube', 'v3', credentials=creds)
        
        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': ['Shorts', '科技', '財經', '新聞'],
                'categoryId': '28'
            },
            'status': {'privacyStatus': 'public', 'selfDeclaredMadeForKids': False}
        }
        
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        request = youtube.videos().insert(part=','.join(body.keys()), body=body, media_body=media)
        
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status: print(f"   進度: {int(status.progress() * 100)}%")
        print(f"✅ 上傳成功！ID: {response['id']}")
    except Exception as e:
        print(f"❌ 上傳失敗: {e}")

# --- 尋找素材 ---
def find_file(extension):
    files = glob.glob(f"*{extension}") + glob.glob(f"*{extension.upper()}")
    if files: return files[0]
    return None

# --- 💎 語音優化核心 ---
async def robust_tts(text, filename="temp_voice.mp3"):
    print(f"🗣️ [TTS] 生成語音 (加速優化版)...")
    try:
        # 這裡改用 'zh-TW-HsiaoYuNeural' (女聲) 或維持 'YunJhe' (男聲)
        # 重點是加上 rate='+10%' 讓語速變快，消除機器感
        comm = edge_tts.Communicate(text, "zh-TW-YunJheNeural", rate="+15%") 
        await comm.save(filename)
        return True
    except:
        try:
            tts = gTTS(text=text, lang='zh-TW')
            tts.save(filename)
            return True
        except:
            return False

async def main():
    print("💎 啟動高級內容引擎...")
    
    bg_video = find_file(".mp4")
    bg_music = find_file(".mp3")
    
    if not bg_video: print("❌ 沒影片檔"); sys.exit(1)

    # 1. 抓新聞 (改抓 TechNews 比較有料)
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    news_list = []
    try:
        urls = ["https://technews.tw/feed/", "https://www.bnext.com.tw/rss"]
        for url in urls:
            f = feedparser.parse(url)
            if f.entries: news_list.extend(f.entries[:3])
    except: pass
    
    if not news_list:
        title_raw, summary = "科技趨勢觀察", "目前沒有資料。"
    else:
        item = random.choice(news_list)
        title_raw, summary = item.title, item.summary

    # 2. 💎 高級文案 Prompt (這裡是最重要的改變)
    print("🧠 AI 正在注入靈魂...")
    prompt = f"""
    你是一位講話很犀利、節奏很快的科技YouTuber。
    請看這則新聞：{title_raw} - {summary}

    任務：
    1. 寫一個超吸睛的 YouTube Shorts 標題 (繁體中文, 20字內, 加上 #Shorts)。
    2. 改寫成一段「口語化」的講稿，像是在跟朋友聊天分享八卦。
       - **絕對不要**說「大家好」、「今日新聞是」。
       - **直接破題**，例如：「天啊！你有看到這個嗎？」、「這家公司太狂了吧！」。
       - 語氣要興奮、專業。
       - 長度控制在 40 秒以內。

    格式：標題|||講稿
    """
    
    try:
        resp = model.generate_content(prompt)
        parts = resp.text.split("|||")
        yt_title = parts[0].strip().replace("*", "")
        script = parts[1].strip().replace("*", "")
    except:
        yt_title = f"{title_raw} #Shorts"
        script = f"這則新聞真的很重要，{title_raw}，大家一定要關注一下。"

    # 3. 轉語音
    if not await robust_tts(script): sys.exit(1)

    # 4. 剪輯 (BGM 音量調得更細緻)
    output_file = "final_output.mp4"
    print(f"🎬 剪輯中... (標題: {yt_title})")
    
    cmd = ["ffmpeg", "-y", "-stream_loop", "-1", "-i", bg_video, "-i", "temp_voice.mp3"]
    if bg_music:
        cmd.extend(["-stream_loop", "-1", "-i", bg_music])
        # volume=0.08 (把音樂壓得更低，讓人聲更清楚，這是高級感的關鍵)
        cmd.extend(["-filter_complex", "[2:a]volume=0.08[bg];[1:a][bg]amix=inputs=2:duration=first[aout]", "-map", "0:v", "-map", "[aout]"])
    else:
        cmd.extend(["-map", "0:v", "-map", "1:a"])

    cmd.extend(["-t", "58", "-c:v", "libx264", "-preset", "ultrafast", "-shortest", output_file])
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    if os.path.exists(output_file):
        print(f"🎉 影片進化成功！準備上傳...")
        description = f"🔥 科技快訊\n新聞來源：{title_raw}\n\n#AI #科技 #商業 #Shorts"
        upload_to_youtube(output_file, yt_title, description)
    else:
        print("❌ 影片生成失敗")

if __name__ == "__main__":
    asyncio.run(main())
