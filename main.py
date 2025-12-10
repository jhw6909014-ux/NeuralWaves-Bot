import os
import random
import asyncio
import requests
import google.generativeai as genai
import edge_tts
from gtts import gTTS # 新增備用與音庫
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, ColorClip
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# --- 設定區 ---
GEMINI_KEY = os.environ["GEMINI_API_KEY"]
YT_CLIENT_ID = os.environ["YT_CLIENT_ID"]
YT_CLIENT_SECRET = os.environ["YT_CLIENT_SECRET"]
YT_REFRESH_TOKEN = os.environ["YT_REFRESH_TOKEN"]

# --- 1. 下載背景影片 (加入 GitHub Raw 源，保證下載成功) ---
def get_background_video():
    print("📥 正在準備背景影片...")
    
    # 這裡有三道防線
    urls = [
        # 1. 嘗試 Pexels (高品質)
        "https://videos.pexels.com/video-files/855018/855018-hd_1920_1080_30fps.mp4",
        # 2. 嘗試 Wikimedia (開源)
        "https://upload.wikimedia.org/wikipedia/commons/transcoded/c/c5/Time_lapse_of_clouds_over_mountains.webm/Time_lapse_of_clouds_over_mountains.webm.720p.vp9.webm",
        # 3. ★ 保底防線：GitHub Raw 源 (絕對不會擋)
        "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/classroom.mp4" 
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    for url in urls:
        try:
            print(f"嘗試下載: {url[:40]}...")
            r = requests.get(url, stream=True, headers=headers, timeout=20)
            if r.status_code == 200:
                filename = "bg.mp4"
                with open(filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1024*1024):
                        if chunk:
                            f.write(chunk)
                
                if os.path.getsize(filename) > 10000:
                    print("✅ 下載成功！")
                    return filename, False
        except Exception as e:
            print(f"⚠️ 下載失敗: {e}")
            continue
    
    print("❌ 所有下載皆失敗，生成純色背景。")
    return "color_bg", True

# --- 2. AI 生成文案 ---
def get_ai_script():
    print("🧠 正在生成 AI 文案...")
    genai.configure(api_key=GEMINI_KEY)
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        topics = ["冷知識", "生活", "科技", "心理學", "歷史"]
        topic = random.choice(topics)
        
        prompt = (f"請給我一個關於 '{topic}' 的繁體中文短影音腳本。"
                  "格式要求：第一行是標題，第二行開始是內文(約 60 字)。"
                  "只要回傳純文字，不要有 markdown。")
        
        response = model.generate_content(prompt)
        text = response.text.strip().split('\n')
        text = [line for line in text if line.strip()]
        
        if text:
            return text[0].strip(), "".join(text[1:]).strip()
            
    except Exception as e:
        print(f"⚠️ AI 錯誤: {e}")
    
    return "每日小知識", "堅持到底的人運氣都不會太差，今天也要加油喔！"

# --- 3. 轉語音 (雙重引擎：Edge + Google) ---
async def make_voice(text):
    print("🗣️ 轉語音中...")
    output = "voice.mp3"
    
    # 優先嘗試 Edge-TTS (好聽)
    try:
        voice = "zh-CN-XiaoxiaoNeural"
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output)
        if os.path.exists(output) and os.path.getsize(output) > 0:
            print("✅ Edge-TTS 生成成功")
            return output
    except Exception as e:
        print(f"⚠️ Edge-TTS 失敗 ({e})，切換至 Google TTS...")

    # 備用方案：Google TTS (穩定)
    try:
        tts = gTTS(text=text, lang='zh-tw')
        tts.save(output)
        print("✅ Google-TTS 生成成功")
        return output
    except Exception as e:
        print(f"❌ 所有語音生成皆失敗: {e}")
        return None

# --- 4. 合成影片 ---
def make_video(bg_source, is_color_bg, voice_path):
    print("🎬 正在合成...")
    
    # 音訊處理
    audio = None
    duration = 10.0
    if voice_path and os.path.exists(voice_path):
        audio = AudioFileClip(voice_path)
        duration = audio.duration + 1.0

    # 畫面處理
    if is_color_bg:
        clip = ColorClip(size=(1080, 1920), color=(20, 30, 80), duration=duration)
    else:
        try:
            clip = VideoFileClip(bg_source)
            # 裁切 9:16
            w, h = clip.size
            if w/h > 9/16:
                new_w = h * (9/16)
                clip = clip.crop(x1=w/2 - new_w/2, width=new_w, height=h)
            clip = clip.loop(duration=duration)
        except Exception as e:
            print(f"⚠️ 影片讀取錯誤 ({e})，回退純色")
            clip = ColorClip(size=(1080, 1920), color=(50, 50, 50), duration=duration)

    if audio:
        clip = clip.set_audio(audio)
    
    output = "final_output.mp4"
    clip.write_videofile(output, fps=24, codec="libx264", audio_codec="aac", threads=4, logger=None)
    return output

# --- 5. 上傳 ---
def upload_youtube(video_path, title, description):
    print(f"🚀 上傳: {title}")
    creds = Credentials(None, refresh_token=YT_REFRESH_TOKEN, token_uri="https://oauth2.googleapis.com/token", client_id=YT_CLIENT_ID, client_secret=YT_CLIENT_SECRET)
    youtube = build("youtube", "v3", credentials=creds)
    
    body = {
        "snippet": {"title": title[:90], "description": description + "\n\n#Shorts #AI", "categoryId": "22"},
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
    }
    
    media = MediaFileUpload(video_path, chunksize=1024*1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"進度: {int(status.progress() * 100)}%")
    print("🎉 上傳成功！")

if __name__ == "__main__":
    try:
        bg_file, is_color = get_background_video()
        title, text = get_ai_script()
        voice_file = asyncio.run(make_voice(text))
        final_video = make_video(bg_file, is_color, voice_file)
        upload_youtube(final_video, title, text)
    except Exception as e:
        print(f"❌ 錯誤: {e}")
        # 這裡不報錯，讓流程跑完
