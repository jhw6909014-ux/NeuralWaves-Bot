import os
import time
import random
import asyncio
import subprocess
import glob
import sys

# 自動安裝缺少的套件
try:
    import edge_tts
    import google.generativeai as genai
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.oauth2.credentials import Credentials
except ImportError:
    pass

# ==========================================
# 🕵️ NEURAL DEBUG BOT (抓鬼偵錯版)
# ==========================================

# 讀取金鑰
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
YT_CLIENT_ID = os.environ.get("YT_CLIENT_ID")
YT_CLIENT_SECRET = os.environ.get("YT_CLIENT_SECRET")
YT_REFRESH_TOKEN = os.environ.get("YT_REFRESH_TOKEN")

if not GEMINI_KEY:
    print("❌ [錯誤] 缺少 GEMINI_API_KEY"); sys.exit(1)

genai.configure(api_key=GEMINI_KEY)

# --- 核心：隨機挑選背景影片 ---
def pick_random_background():
    print("🔍 正在掃描目錄下的影片...")
    # 列出所有檔案幫忙除錯
    print(f"📂 目錄檔案列表: {os.listdir('.')}")
    
    # 搜尋所有 mp4 (忽略大小寫)
    all_videos = glob.glob("*.mp4") + glob.glob("*.MP4")
    
    # 過濾掉「生成的成品」
    candidates = []
    for v in all_videos:
        if "final" in v or "Ultimate" in v or "output" in v: 
            continue
        candidates.append(v)
    
    if not candidates:
        print("❌ [嚴重錯誤] 找不到任何素材影片！GitHub 上面真的有 .mp4 檔案嗎？")
        return None
    
    selected = random.choice(candidates)
    print(f"✅ 選中背景影片: {selected}")
    return selected

# --- 核心：尋找音樂 ---
def find_music():
    musics = glob.glob("*.mp3")
    if musics: return random.choice(musics)
    return None

# --- 核心：轉語音 (加強偵錯) ---
async def robust_tts(text, filename="temp_voice.mp3"):
    print(f"🗣️ [TTS] 準備生成語音...")
    if not text or len(text) < 2:
        print("❌ [TTS 錯誤] AI 生成的文字是空的！無法轉語音。")
        return False

    try:
        # 使用更穩定的參數
        comm = edge_tts.Communicate(text, "zh-TW-YunJheNeural", rate="+10%") 
        await comm.save(filename)
        
        # 檢查檔案是否真的存在且有大小
        if os.path.exists(filename) and os.path.getsize(filename) > 0:
            print("✅ 語音生成成功！")
            return True
        else:
            print("❌ [TTS 錯誤] 檔案生成了但大小為 0。")
            return False
    except Exception as e:
        print(f"❌ [TTS 崩潰] 錯誤原因: {e}")
        return False

# --- 核心：上傳到 YouTube ---
def upload_to_youtube(video_path, title, description):
    if not (YT_CLIENT_ID and YT_CLIENT_SECRET and YT_REFRESH_TOKEN):
        print("⚠️ 缺少 YouTube 金鑰，跳過上傳")
        return

    print(f"🚀 正在上傳: {title}...")
    try:
        creds = Credentials(None, refresh_token=YT_REFRESH_TOKEN, token_uri="https://oauth2.googleapis.com/token", client_id=YT_CLIENT_ID, client_secret=YT_CLIENT_SECRET)
        youtube = build('youtube', 'v3', credentials=creds)
        body = {
            'snippet': {'title': title, 'description': description, 'tags': ['Shorts'], 'categoryId': '24'},
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

async def main():
    print("👻 啟動偵錯模式...")
    
    # 1. 檢查影片素材
    bg_video = pick_random_background()
    if not bg_video: sys.exit(1)
    
    bg_music = find_music()

    # 2. 生成內容
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    topic = random.choice(["恐怖故事", "冷知識", "都市傳說"])
    print(f"🧠 AI 正在寫稿: {topic}...")
    
    prompt = f"寫一個 50 字以內的{topic}，第一句要有爆點。最後給一個 Shorts 標題用 ||| 分隔。"
    
    try:
        resp = model.generate_content(prompt)
        text_raw = resp.text.replace("*", "").strip()
        print(f"📝 AI 回傳內容: {text_raw}") # 印出來檢查
        
        if "|||" in text_raw:
            parts = text_raw.split("|||")
            script = parts[0].strip()
            yt_title = parts[1].strip()
        else:
            script = text_raw
            yt_title = f"{topic} #Shorts"
            
    except Exception as e:
        print(f"❌ AI 生成失敗: {e}")
        script = "你知道嗎？這是一個測試語音。系統正在偵錯中。"
        yt_title = "系統測試 #Shorts"

    # 3. 轉語音
    if not await robust_tts(script): 
        print("❌ 程式因 TTS 失敗而終止")
        sys.exit(1)

    # 4. 剪輯
    output_file = "final_output.mp4"
    print(f"🎬 開始剪輯 (素材: {bg_video})...")
    
    # 簡單剪輯指令 (不切片，直接用素材的前 58 秒，排除切片邏輯錯誤)
    cmd = [
        "ffmpeg", "-y", 
        "-i", bg_video, 
        "-i", "temp_voice.mp3"
    ]
    
    if bg_music:
        cmd.extend(["-stream_loop", "-1", "-i", bg_music])
        filter_complex = "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[v];[2:a]volume=0.05[bg];[1:a][bg]amix=inputs=2:duration=first[aout]"
        cmd.extend(["-filter_complex", filter_complex, "-map", "[v]", "-map", "[aout]"])
    else:
        cmd.extend(["-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920", "-map", "0:v", "-map", "1:a"])

    cmd.extend(["-t", "58", "-c:v", "libx264", "-preset", "ultrafast", "-shortest", output_file])
    
    # 捕捉 FFmpeg 錯誤
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    if result.returncode != 0:
        print("❌ FFmpeg 剪輯失敗！錯誤訊息如下：")
        print(result.stderr)
        sys.exit(1)
    
    if os.path.exists(output_file):
        print(f"🎉 成功生成: {output_file}")
        upload_to_youtube(output_file, yt_title, "#Shorts")
    else:
        print("❌ 影片檔案未生成 (未知原因)")

if __name__ == "__main__":
    asyncio.run(main())
