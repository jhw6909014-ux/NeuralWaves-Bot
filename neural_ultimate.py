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
# ⚡ NEURAL GITHUB BOT (語法修復版)
# ==========================================

# 讀取金鑰
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
YT_CLIENT_ID = os.environ.get("YT_CLIENT_ID")
YT_CLIENT_SECRET = os.environ.get("YT_CLIENT_SECRET")
YT_REFRESH_TOKEN = os.environ.get("YT_REFRESH_TOKEN")

if not GEMINI_KEY:
    print("❌ [錯誤] 缺少 GEMINI_API_KEY"); sys.exit(1)

genai.configure(api_key=GEMINI_KEY)

# --- 核心功能：上傳到 YouTube ---
def upload_to_youtube(video_path, title, description):
    # 檢查有沒有金鑰，沒有就跳過
    if not (YT_CLIENT_ID and YT_CLIENT_SECRET and YT_REFRESH_TOKEN):
        print("⚠️ 缺少 YouTube 金鑰，跳過上傳步驟 (僅生成影片)")
        return

    print(f"🚀 正在上傳到 YouTube: {title}...")
    try:
        # 重建憑證
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
                'tags': ['Shorts', 'AI', 'News', 'Tech'],
                'categoryId': '28' # 科技類
            },
            'status': {
                'privacyStatus': 'public', # 若想先測試可改 'private'
                'selfDeclaredMadeForKids': False
            }
        }
        
        # 建立上傳請求
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        request = youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media
        )
        
        # 執行上傳
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"   上傳進度: {int(status.progress() * 100)}%")
                
        print(f"✅ 上傳成功！影片 ID: {response['id']}")
        
    except Exception as e:
        print(f"❌ 上傳失敗: {e}")

# --- 核心功能：自動尋找素材 ---
def find_file(extension):
    files = glob.glob(f"*{extension}") + glob.glob(f"*{extension.upper()}")
    if files: return files[0]
    return None

async def robust_tts(text, filename="temp_voice.mp3"):
    print(f"🗣️ [TTS] 生成語音...")
    try:
        comm = edge_tts.Communicate(text, "zh-TW-YunJheNeural")
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
    print("🚀 任務開始...")
    
    bg_video = find_file(".mp4")
    bg_music = find_file(".mp3")
    
    if not bg_video:
        print("❌ 找不到背景影片！"); sys.exit(1)

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
        title_raw, summary = "AI科技快訊", "目前無最新新聞。"
    else:
        item = random.choice(news_list)
        title_raw, summary = item.title, item.summary

    # 2. 寫腳本 & 標題
    print("🧠 AI 正在思考內容與標題...")
    prompt = f"""
    你是專業YouTuber。請根據這則新聞：{title_raw} - {summary}
    1. 寫一個吸引人的YouTube Shorts標題(20字內)，包含 #Shorts
    2. 寫一段30秒內的口語講稿(繁體中文)。
    請用 "|||" 分隔標題和講稿。
    """
    try:
        resp = model.generate_content(prompt)
        parts = resp.text.split("|||")
        yt_title = parts[0].strip().replace("*", "")
        script = parts[1].strip().replace("*", "")
    except:
        yt_title = f"{title_raw} #Shorts"
        script = f"大家好，今日新聞是{title_raw}。"

    # 3. 轉語音 (這裡是你剛剛斷掉的地方，現在修好了)
    if not await robust_tts(script): sys.exit(1)

    # 4. 剪輯
    output_file = "final_output.mp4"
    print(f"🎬 剪輯中... (標題: {yt_title})")
    
    cmd = ["ffmpeg", "-y", "-stream_loop", "-1", "-i", bg_video, "-i", "temp_voice.mp3"]
    if bg_music:
        cmd.extend(["-stream_loop", "-1", "-i", bg_music])
        cmd.extend(["-filter_complex", "[2:a]volume=0.1[bg];[1:a][bg]amix=inputs=2:duration=first[aout]", "-map", "0:v", "-map", "[aout]"])
    else:
        cmd.extend(["-map", "0:v", "-map", "1:a"])

    cmd.extend(["-t", "58", "-c:v", "libx264", "-preset", "ultrafast", "-shortest", output_file])
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    if os.path.exists(output_file):
        print(f"🎉 影片生成成功！準備上傳...")
        # 5. 上傳到 YouTube
        description = f"AI 自動生成報導。\n新聞來源：{title_raw}\n#AI #Tech #Shorts"
        upload_to_youtube(output_file, yt_title, description)
    else:
        print("❌ 影片生成失敗")

if __name__ == "__main__":
    asyncio.run(main())
