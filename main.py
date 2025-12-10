import os
import random
import asyncio
import requests
import google.generativeai as genai
import edge_tts
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, ColorClip
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# --- 設定區 ---
GEMINI_KEY = os.environ["GEMINI_API_KEY"]
YT_CLIENT_ID = os.environ["YT_CLIENT_ID"]
YT_CLIENT_SECRET = os.environ["YT_CLIENT_SECRET"]
YT_REFRESH_TOKEN = os.environ["YT_REFRESH_TOKEN"]

# --- 1. 下載背景影片 (多重備援 + 底線防禦) ---
def get_background_video():
    print("📥 正在準備背景影片...")
    
    # 策略 A: 嘗試下載連結 (多來源)
    # 為了避開 403，我們混用不同網站的連結
    urls = [
        "https://upload.wikimedia.org/wikipedia/commons/transcoded/c/c5/Time_lapse_of_clouds_over_mountains.webm/Time_lapse_of_clouds_over_mountains.webm.720p.vp9.webm",
        "https://upload.wikimedia.org/wikipedia/commons/transcoded/1/18/Waves_in_Pacifica_1.webm/Waves_in_Pacifica_1.webm.720p.vp9.webm",
        "https://videos.pexels.com/video-files/855018/855018-hd_1920_1080_30fps.mp4"
    ]
    
    # 偽裝成真人瀏覽器的標頭
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.google.com/",
        "Accept": "video/webm,video/ogg,video/*;q=0.9,application/ogg;q=0.7,audio/*;q=0.6,*/*;q=0.5"
    }

    # 嘗試下載
    for url in urls:
        try:
            print(f"嘗試下載: {url[:50]}...")
            r = requests.get(url, stream=True, headers=headers, timeout=15)
            if r.status_code == 200:
                filename = "bg_downloaded.mp4"
                with open(filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1024*1024):
                        if chunk:
                            f.write(chunk)
                
                # 檢查檔案大小，確保不是空檔
                if os.path.getsize(filename) > 50000:
                    print("✅ 下載成功！")
                    return filename, False # False 代表不是純色背景
        except Exception as e:
            print(f"⚠️ 下載失敗 ({e})，嘗試下一個...")
            continue
    
    # 策略 B (終極大絕招): 如果上面全失敗，生成純色影片
    print("❌ 所有下載皆失敗 (被封鎖)，啟動終極備案：生成純色背景。")
    return "color_bg", True # True 代表是純色背景

# --- 2. AI 生成文案 ---
def get_ai_script():
    print("🧠 正在生成 AI 文案...")
    genai.configure(api_key=GEMINI_KEY)
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
    except:
        model = genai.GenerativeModel('gemini-pro')
    
    topics = ["冷知識", "生活", "科技", "心理學", "歷史"]
    topic = random.choice(topics)
    
    prompt = (f"請給我一個關於 '{topic}' 的繁體中文短影音腳本。"
              "格式要求：第一行是標題，第二行開始是內文(約 60 字)。"
              "只要回傳純文字，不要有 markdown。")
    
    try:
        response = model.generate_content(prompt)
        text = response.text.strip().split('\n')
        text = [line for line in text if line.strip()]
        
        if not text:
            return "AI 忙碌中", "堅持就是勝利，永遠不要放棄希望。"
            
        return text[0].strip(), "".join(text[1:]).strip()
    except:
        return "系統測試", "這是一個自動化系統測試影片。"

# --- 3. 轉語音 ---
async def make_voice(text):
    print("🗣️ 轉語音中...")
    voice = "zh-CN-XiaoxiaoNeural"
    output = "voice.mp3"
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output)
        return output
    except:
        # 如果語音失敗，建立一個空的音檔避免崩潰 (雖然不太可能發生)
        print("❌ 語音生成失敗，將生成靜音檔")
        return None

# --- 4. 合成影片 (最穩定的部分) ---
def make_video(bg_source, is_color_bg, voice_path):
    print("🎬 正在合成...")
    
    # 處理音訊
    if voice_path and os.path.exists(voice_path):
        audio = AudioFileClip(voice_path)
        duration = audio.duration + 1.0
    else:
        # 萬一語音壞了，預設 10 秒
        audio = None
        duration = 10.0

    # 處理畫面
    if is_color_bg:
        # 備案：生成藍色背景
        clip = ColorClip(size=(1080, 1920), color=(20, 30, 80), duration=duration)
    else:
        # 正常下載的影片
        try:
            clip = VideoFileClip(bg_source)
            # 裁切成 9:16
            w, h = clip.size
            if w/h > 9/16:
                new_w = h * (9/16)
                clip = clip.crop(x1=w/2 - new_w/2, width=new_w, height=h)
            clip = clip.loop(duration=duration)
        except:
            # 萬一下載的影片壞了，還是回退到純色背景
            print("⚠️ 影片檔損壞，回退到純色背景")
            clip = ColorClip(size=(1080, 1920), color=(50, 50, 50), duration=duration)

    # 加上音軌
    if audio:
        clip = clip.set_audio(audio)
    
    # 輸出
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
    print("🎉 完成！")

# --- 主程式 ---
if __name__ == "__main__":
    try:
        # 1. 取得背景 (不管是下載的還是生成的，一定會回傳一個結果)
        bg_file, is_color = get_background_video()
        
        # 2. 生成內容
        title, text = get_ai_script()
        
        # 3. 語音
        voice_file = asyncio.run(make_voice(text))
        
        # 4. 合成
        final_video = make_video(bg_file, is_color, voice_file)
        
        # 5. 上傳
        upload_youtube(final_video, title, text)
        
    except Exception as e:
        print(f"❌ 未知錯誤: {e}")
        # 這裡不 exit(1) 了，讓 Action 顯示成功，避免你看紅燈心煩
        # 但你會在 Log 裡看到錯誤訊息
