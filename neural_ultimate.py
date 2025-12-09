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
# 🔥 NEURAL VIRAL BOT (爆紅短影音版)
# ==========================================

# 讀取金鑰
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
YT_CLIENT_ID = os.environ.get("YT_CLIENT_ID")
YT_CLIENT_SECRET = os.environ.get("YT_CLIENT_SECRET")
YT_REFRESH_TOKEN = os.environ.get("YT_REFRESH_TOKEN")

if not GEMINI_KEY:
    print("❌ [錯誤] 缺少 GEMINI_API_KEY"); sys.exit(1)

genai.configure(api_key=GEMINI_KEY)

# --- 核心：上傳到 YouTube ---
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
                'tags': ['Shorts', '都市傳說', '恐怖', '冷知識', '故事'],
                'categoryId': '24' # 娛樂類
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

# --- 核心：隨機選擇背景影片片段 ---
def get_random_start_time(video_path, duration_needed=60):
    try:
        # 取得影片總長度
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        total_seconds = float(result.stdout)
        
        # 確保影片夠長
        if total_seconds <= duration_needed:
            return 0
            
        # 隨機選一個開始時間 (預留尾巴)
        max_start = total_seconds - duration_needed - 10
        start_time = random.uniform(0, max_start)
        return start_time
    except:
        return 0

# --- 核心：尋找素材 ---
def find_file(extension):
    files = glob.glob(f"*{extension}") + glob.glob(f"*{extension.upper()}")
    if files: return files[0]
    return None

async def robust_tts(text, filename="temp_voice.mp3"):
    print(f"🗣️ [TTS] 生成語音 (講鬼故事模式)...")
    try:
        # 這裡建議用 'zh-TW-YunJheNeural' 男聲講鬼故事比較有磁性
        # rate="+10%" 稍微加速，增加緊湊感
        comm = edge_tts.Communicate(text, "zh-TW-YunJheNeural", rate="+10%") 
        await comm.save(filename)
        return True
    except:
        return False

async def main():
    print("👻 啟動爆紅內容引擎...")
    
    # 這裡會抓你上傳的長影片 (例如 gameplay.mp4)
    bg_video = find_file(".mp4") 
    bg_music = find_file(".mp3")
    
    if not bg_video: print("❌ 沒影片檔"); sys.exit(1)

    # 1. 💎 爆紅腳本生成 (不抓新聞了，直接創作)
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    
    # 隨機選一個主題類型
    topics = ["細思極恐的短篇故事", "鮮為人知的暗黑冷知識", "都市傳說", "心理學詭計"]
    selected_topic = random.choice(topics)
    
    print(f"🧠 AI 正在構思主題: {selected_topic}...")
    
    prompt = f"""
    任務：寫一個適合 TikTok/Shorts 的爆紅短文案。
    主題：{selected_topic}
    
    要求：
    1. **第一句必須是「勾子 (Hook)」**：例如「你絕對不敢相信...」、「聽過這個都市傳說嗎？」。
    2. 內容要讓人想接著聽下去，有懸疑感或驚訝感。
    3. 字數控制在 160 字以內 (約 40-50 秒)。
    4. 語氣：口語化、神秘、像在講秘密。
    5. 不要標題，不要前言，直接給我內容。
    6. 最後要生成一個 YouTube Shorts 標題，放在最後一行，用 "|||" 分隔。
    """
    
    try:
        resp = model.generate_content(prompt)
        content_raw = resp.text.replace("*", "").strip()
        
        if "|||" in content_raw:
            parts = content_raw.split("|||")
            script = parts[0].strip()
            yt_title = parts[1].strip()
        else:
            script = content_raw
            yt_title = f"你絕對不知道的秘密... #Shorts #都市傳說"
            
    except:
        script = "你知道嗎？如果你的影子突然消失了，代表你可能已經... 這是一個流傳已久的都市傳說。"
        yt_title = "影子的秘密 #Shorts"

    # 3. 轉語音
    if not await robust_tts(script): sys.exit(1)

    # 4. 剪輯 (關鍵：隨機切片)
    output_file = "final_output.mp4"
    
    # 計算隨機開始時間
    start_time = get_random_start_time(bg_video)
    print(f"🎬 剪輯中... (從 {int(start_time)} 秒開始切片)")
    
    # FFmpeg 指令：加入 -ss (開始時間)
    cmd = ["ffmpeg", "-y", "-ss", str(start_time), "-i", bg_video, "-i", "temp_voice.mp3"]
    
    if bg_music:
        cmd.extend(["-stream_loop", "-1", "-i", bg_music])
        # 音樂壓得非常低 (0.05)，營造氛圍但不可搶戲
        cmd.extend(["-filter_complex", "[2:a]volume=0.05[bg];[1:a][bg]amix=inputs=2:duration=first[aout]", "-map", "0:v", "-map", "[aout]"])
    else:
        cmd.extend(["-map", "0:v", "-map", "1:a"])

    # -t 60 限制最大 60 秒
    cmd.extend(["-t", "58", "-c:v", "libx264", "-preset", "ultrafast", "-shortest", output_file])
    
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    if os.path.exists(output_file):
        print(f"🎉 影片生成成功！標題：{yt_title}")
        description = f"🔥 每天更新都市傳說/冷知識。\n\n#Shorts #冷知識 #都市傳說 #故事"
        upload_to_youtube(output_file, yt_title, description)
    else:
        print("❌ 影片生成失敗")

if __name__ == "__main__":
    asyncio.run(main())
