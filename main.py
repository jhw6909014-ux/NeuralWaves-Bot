import os
import random
import asyncio
import requests
import google.generativeai as genai
import edge_tts
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# --- 設定區 ---
GEMINI_KEY = os.environ["GEMINI_API_KEY"]
YT_CLIENT_ID = os.environ["YT_CLIENT_ID"]
YT_CLIENT_SECRET = os.environ["YT_CLIENT_SECRET"]
YT_REFRESH_TOKEN = os.environ["YT_REFRESH_TOKEN"]

# --- 1. 下載背景影片 (使用 Pexels 免費素材) ---
def download_background():
    print("📥 正在下載背景影片...")
    # 這裡用一個高品質的風景影片當範例，避免版權問題
    video_url = "https://videos.pexels.com/video-files/5527788/5527788-hd_1080_1920_25fps.mp4"
    
    r = requests.get(video_url, stream=True)
    with open("bg.mp4", 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024*1024):
            if chunk:
                f.write(chunk)
    print("✅ 背景下載完成")
    return "bg.mp4"

# --- 2. AI 生成文案 (Gemini) ---
def get_ai_script():
    print("🧠 正在生成 AI 文案...")
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel('gemini-pro')
    
    topics = ["冷知識", "生活小撇步", "驚人事實", "每日激勵", "心理學效應"]
    topic = random.choice(topics)
    
    prompt = (f"請給我一個關於 '{topic}' 的繁體中文短影音腳本。"
              "格式要求：第一行是吸引人的標題(不要有#)，第二行開始是內文(約 80 字，口語化，適合朗讀)。"
              "只要回傳純文字，不要有 markdown 符號。")
    
    response = model.generate_content(prompt)
    text = response.text.strip()
    lines = text.split('\n')
    title = lines[0].strip()
    content = "".join(lines[1:]).strip()
    
    print(f"✅ 文案生成: {title}")
    return title, content

# --- 3. 轉語音 (Edge-TTS) ---
async def make_voice(text):
    print("🗣️ 正在轉語音...")
    voice = "zh-CN-XiaoxiaoNeural" # 若要台灣口音可改 zh-TW-HsiaoChenNeural
    output = "voice.mp3"
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output)
    print("✅ 語音完成")
    return output

# --- 4. 合成影片 (MoviePy) ---
def make_video(video_path, voice_path):
    print("🎬 正在合成影片...")
    clip = VideoFileClip(video_path)
    audio = AudioFileClip(voice_path)
    
    # 裁切影片：確保是直式 9:16
    w, h = clip.size
    target_ratio = 9/16
    if w/h > target_ratio:
        new_w = h * target_ratio
        clip = clip.crop(x1=w/2 - new_w/2, width=new_w, height=h)
    
    # 讓影片長度 = 語音長度 + 1秒緩衝
    final_duration = audio.duration + 0.5
    
    # 如果背景太短就循環，太長就切掉
    final_clip = clip.loop(duration=final_duration)
    final_clip = final_clip.set_audio(audio)
    
    output_path = "final_output.mp4"
    # 使用相容性最高的編碼參數
    final_clip.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", threads=4)
    print("✅ 影片合成完成！")
    return output_path

# --- 5. 上傳 YouTube ---
def upload_youtube(video_path, title, description):
    print(f"🚀 準備上傳: {title}...")
    creds = Credentials(
        None, 
        refresh_token=YT_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=YT_CLIENT_ID, 
        client_secret=YT_CLIENT_SECRET
    )
    youtube = build("youtube", "v3", credentials=creds)
    
    body = {
        "snippet": {
            "title": title[:90], 
            "description": description + "\n\n#Shorts #AI #冷知識 #自動化", 
            "categoryId": "22"
        },
        "status": {
            "privacyStatus": "public", # 設定為公開
            "selfDeclaredMadeForKids": False
        }
    }
    
    media = MediaFileUpload(video_path, chunksize=1024*1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploading... {int(status.progress() * 100)}%")
            
    print("🎉 上傳成功！影片已發布。")

# --- 主執行區 ---
if __name__ == "__main__":
    try:
        bg_video = download_background()
        title, text = get_ai_script()
        asyncio.run(make_voice(text))
        final_video = make_video(bg_video, "voice.mp3")
        upload_youtube(final_video, title, text)
    except Exception as e:
        print(f"❌ 發生錯誤: {e}")
        raise e
