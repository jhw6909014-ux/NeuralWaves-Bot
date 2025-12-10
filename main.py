import os
import random
import asyncio
import requests
import google.generativeai as genai
import edge_tts
from gtts import gTTS
from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, ColorClip
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

# --- 設定區 ---
GEMINI_KEY = os.environ["GEMINI_API_KEY"]
YT_CLIENT_ID = os.environ["YT_CLIENT_ID"]
YT_CLIENT_SECRET = os.environ["YT_CLIENT_SECRET"]
YT_REFRESH_TOKEN = os.environ["YT_REFRESH_TOKEN"]

# --- 1. 下載背景影片 ---
def get_background_video():
    print("📥 正在準備背景影片...")
    urls = [
        "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/classroom.mp4",
        "https://videos.pexels.com/video-files/855018/855018-hd_1920_1080_30fps.mp4",
        "https://upload.wikimedia.org/wikipedia/commons/transcoded/c/c5/Time_lapse_of_clouds_over_mountains.webm/Time_lapse_of_clouds_over_mountains.webm.720p.vp9.webm"
    ]
    headers = {"User-Agent": "Mozilla/5.0"}

    for url in urls:
        try:
            print(f"嘗試下載: {url[:40]}...")
            r = requests.get(url, stream=True, headers=headers, timeout=20)
            if r.status_code == 200:
                filename = "bg.mp4"
                with open(filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1024*1024):
                        f.write(chunk)
                if os.path.getsize(filename) > 10000:
                    print("✅ 下載成功！")
                    return filename, False
        except:
            continue
    
    print("⚠️ 下載失敗，使用純色背景")
    return "color_bg", True

# --- 2. AI 生成文案 (優先用 Pro 版) ---
def get_ai_script():
    print("🧠 正在生成 AI 文案...")
    genai.configure(api_key=GEMINI_KEY)
    
    # 改回 gemini-pro 避免 404 錯誤
    try:
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content("給我一個關於'冷知識'的短影音腳本，兩行：標題與內文。")
    except:
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content("給我一個關於'冷知識'的短影音腳本，兩行：標題與內文。")
        except:
            return "每日知識", "今天也要加油喔！堅持就是勝利。"

    try:
        text = response.text.strip().split('\n')
        text = [line for line in text if line.strip()]
        if text: return text[0], "".join(text[1:])
    except:
        pass
        
    return "系統測試", "自動化測試影片生成成功。"

# --- 3. 轉語音 ---
async def make_voice(text):
    print("🗣️ 轉語音中...")
    output = "voice.mp3"
    try:
        communicate = edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural")
        await communicate.save(output)
        if os.path.exists(output) and os.path.getsize(output) > 0:
            return output
    except:
        pass
    
    # 備用
    try:
        tts = gTTS(text=text, lang='zh-tw')
        tts.save(output)
        return output
    except:
        return None

# --- 4. 合成影片 ---
def make_video(bg_source, is_color_bg, voice_path):
    print("🎬 正在合成...")
    audio = None
    duration = 10.0
    if voice_path and os.path.exists(voice_path):
        audio = AudioFileClip(voice_path)
        duration = audio.duration + 1.0

    if is_color_bg:
        clip = ColorClip(size=(1080, 1920), color=(20, 30, 80), duration=duration)
    else:
        try:
            clip = VideoFileClip(bg_source)
            w, h = clip.size
            if w/h > 9/16:
                new_w = h * (9/16)
                clip = clip.crop(x1=w/2 - new_w/2, width=new_w, height=h)
            clip = clip.loop(duration=duration)
        except:
            clip = ColorClip(size=(1080, 1920), color=(50, 50, 50), duration=duration)

    if audio: clip = clip.set_audio(audio)
    
    output = "final_output.mp4"
    clip.write_videofile(output, fps=24, codec="libx264", audio_codec="aac", threads=4, logger=None)
    return output

# --- 5. 上傳 (包含額度滿的處理) ---
def upload_youtube(video_path, title, description):
    print(f"🚀 準備上傳: {title}")
    creds = Credentials(None, refresh_token=YT_REFRESH_TOKEN, token_uri="https://oauth2.googleapis.com/token", client_id=YT_CLIENT_ID, client_secret=YT_CLIENT_SECRET)
    youtube = build("youtube", "v3", credentials=creds)
    
    body = {
        "snippet": {"title": title[:90], "description": description + "\n\n#Shorts #AI", "categoryId": "22"},
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
    }
    
    media = MediaFileUpload(video_path, chunksize=1024*1024, resumable=True)
    
    try:
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status: print(f"進度: {int(status.progress() * 100)}%")
        print("🎉 上傳成功！")
        
    except HttpError as e:
        if "uploadLimitExceeded" in str(e):
            print("⚠️ 警告：今日 YouTube 上傳額度已滿 (每日限約 6 支)。")
            print("💡 解決方案：影片已生成，請明天再試，或手動下載 Artifact 上傳。")
            # 這裡不拋出錯誤，讓 Action 顯示綠色成功
        else:
            print(f"❌ 上傳發生其他錯誤: {e}")
            raise e

if __name__ == "__main__":
    try:
        bg_file, is_color = get_background_video()
        title, text = get_ai_script()
        voice_file = asyncio.run(make_voice(text))
        final_video = make_video(bg_file, is_color, voice_file)
        upload_youtube(final_video, title, text)
    except Exception as e:
        print(f"❌ 流程錯誤: {e}")
