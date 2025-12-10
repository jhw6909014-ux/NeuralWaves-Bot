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

# --- 1. 下載背景影片 (修復版：偽裝成瀏覽器) ---
def download_background():
    print("📥 正在下載背景影片...")
    
    # 換一個更穩定的影片來源
    video_url = "https://videos.pexels.com/video-files/855018/855018-hd_1920_1080_30fps.mp4"
    
    # ★ 關鍵修改：加入 Header 偽裝成 Chrome 瀏覽器，防止被網站擋
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        r = requests.get(video_url, stream=True, headers=headers)
        
        # 檢查是否下載成功 (200 OK)
        if r.status_code != 200:
            raise Exception(f"下載失敗，狀態碼: {r.status_code}")
            
        with open("bg.mp4", 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)
        
        # ★ 關鍵檢查：檔案是否太小 (如果小於 100KB 代表下載到假檔案)
        file_size = os.path.getsize("bg.mp4")
        if file_size < 100000: 
            raise Exception(f"下載的影片檔案太小 ({file_size} bytes)，可能是假檔案。")
            
        print(f"✅ 背景下載完成 (大小: {file_size/1024/1024:.2f} MB)")
        return "bg.mp4"
    except Exception as e:
        print(f"❌ 下載影片嚴重失敗: {e}")
        # 如果下載失敗，程式必須停止，否則後面會報錯
        raise e

# --- 2. AI 生成文案 (增強版) ---
def get_ai_script():
    print("🧠 正在生成 AI 文案...")
    genai.configure(api_key=GEMINI_KEY)
    
    # 嘗試多種模型名稱，總有一個能用
    model = None
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
    except:
        try:
            model = genai.GenerativeModel('gemini-pro')
        except:
            pass

    topics = ["冷知識", "生活小撇步", "驚人事實", "每日激勵", "心理學效應", "科技新知"]
    topic = random.choice(topics)
    
    prompt = (f"請給我一個關於 '{topic}' 的繁體中文短影音腳本。"
              "格式要求：第一行是吸引人的標題(不要有#)，第二行開始是內文(約 80 字，口語化，適合朗讀)。"
              "只要回傳純文字，不要有 markdown 符號。")
    
    try:
        if model is None:
            raise Exception("無法初始化任何 AI 模型")
            
        response = model.generate_content(prompt)
        text = response.text.strip()
        lines = text.split('\n')
        lines = [line for line in lines if line.strip()]
        
        if not lines:
            return "AI 思考失敗", "堅持到底的人運氣都不會太差，今天也要加油喔！"

        title = lines[0].strip()
        content = "".join(lines[1:]).strip()
        
        print(f"✅ 文案生成成功: {title}")
        return title, content
    except Exception as e:
        print(f"⚠️ AI 錯誤 (使用備用文案): {e}")
        return "每日小知識", "你知道嗎？每天保持微笑可以增加免疫力，今天也要開心過一天喔！"

# --- 3. 轉語音 (Edge-TTS) ---
async def make_voice(text):
    print("🗣️ 正在轉語音...")
    voice = "zh-CN-XiaoxiaoNeural" 
    output = "voice.mp3"
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output)
    
    # 檢查語音檔是否真的存在
    if not os.path.exists(output) or os.path.getsize(output) == 0:
        raise Exception("語音生成失敗 (檔案為空)")
        
    print("✅ 語音完成")
    return output

# --- 4. 合成影片 (MoviePy) ---
def make_video(video_path, voice_path):
    print("🎬 正在合成影片...")
    
    # 檢查檔案是否存在
    if not os.path.exists(video_path):
        raise Exception(f"找不到影片檔: {video_path}")
    
    clip = VideoFileClip(video_path)
    audio = AudioFileClip(voice_path)
    
    # 1. 裁切影片為直式 9:16
    w, h = clip.size
    target_ratio = 9/16
    if w/h > target_ratio:
        new_w = h * target_ratio
        clip = clip.crop(x1=w/2 - new_w/2, width=new_w, height=h)
    
    # 2. 調整長度
    final_duration = audio.duration + 1.0 
    final_clip = clip.loop(duration=final_duration)
    
    # 3. 合成音軌
    final_clip = final_clip.set_audio(audio)
    
    output_path = "final_output.mp4"
    final_clip.write_videofile(
        output_path, 
        fps=24, 
        codec="libx264", 
        audio_codec="aac", 
        threads=4,
        logger=None
    )
    print("✅ 影片合成完成！")
    return output_path

# --- 5. 上傳 YouTube ---
def upload_youtube(video_path, title, description):
    print(f"🚀 準備上傳到 YouTube: {title}...")
    
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
            "description": description + "\n\n#Shorts #AI", 
            "categoryId": "22"
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }
    
    media = MediaFileUpload(video_path, chunksize=1024*1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    
    print("Uploading...")
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"上傳進度: {int(status.progress() * 100)}%")
            
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
        print(f"❌ 程式執行發生錯誤: {e}")
        exit(1)
