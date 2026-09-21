import streamlit as st
import subprocess
import os
import asyncio
import whisper
import edge_tts
import google.generativeai as genai

st.set_page_config(page_title="AI Video Dubber & Anti-Copyright", layout="wide")
st.title("🎬 Anti-Copyright AI Video Dubber")
st.write("Sirf video link daalein — AI automatically video edit karega aur Hindi Voice-over lagayega.")

# Sidebar Settings
st.sidebar.header("⚙️ Anti-Copyright Filters")
apply_flip = st.sidebar.checkbox("Mirror/Flip Video", value=True)
zoom_percent = st.sidebar.slider("Slight Zoom (%)", min_value=3, max_value=10, value=5)
speed_mult = st.sidebar.slider("Speed Boost (e.g., 1.04x)", min_value=1.01, max_value=1.10, value=1.04, step=0.01)
contrast_boost = st.sidebar.slider("Contrast & Saturation Tweak", min_value=1.0, max_value=1.2, value=1.08, step=0.02)

st.sidebar.header("🎙️ Voice Settings")
voice_gender = st.sidebar.selectbox("Voice", ["Madhur (Male - Hindi)", "Swara (Female - Hindi)"])
selected_voice = "hi-IN-MadhurNeural" if "Madhur" in voice_gender else "hi-IN-SwaraNeural"

# Gemini API Key (Optional)
gemini_key = st.sidebar.text_input("Gemini API Key (Optional for smart summary)", type="password")

# Main Interface
video_url = st.text_input("🔗 Video ka Link yahan paste karein (YouTube, etc.):")

if st.button("🚀 Generate Copyright-Safe Hindi Video"):
    if not video_url:
        st.error("Kripya video ka valid link daalein!")
    else:
        status = st.status("Kaam chal raha hai...", expanded=True)
        
        # 1. Download Video using yt-dlp
        status.write("📥 Step 1: Video download ho rahi hai...")
        raw_video = "downloaded_video.mp4"
        if os.path.exists(raw_video):
            os.remove(raw_video)
        
        ydl_cmd = f'yt-dlp -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4" -o "{raw_video}" "{video_url}"'
        subprocess.run(ydl_cmd, shell=True, check=True)
        
        # 2. Extract Audio & Transcribe
        status.write("🎙️ Step 2: Audio se text nikala ja raha hai (Whisper AI)...")
        model = whisper.load_model("base")
        transcription = model.transcribe(raw_video)
        original_text = transcription["text"]
        
        # 3. Translate & Create Script
        status.write("📝 Step 3: Hindi script taiyar ho rahi hai...")
        if gemini_key:
            genai.configure(api_key=gemini_key)
            gmodel = genai.GenerativeModel("gemini-1.5-flash")
            prompt = f"Translate and rewrite the following video transcript into an engaging, natural Hindi YouTube voice-over narration:\n\n{original_text[:3000]}"
            response = gmodel.generate_content(prompt)
            hindi_script = response.text
        else:
            hindi_script = f"Doston, is video mein ek bohot hi dilchasp baat batayi gayi hai. {original_text[:500]}"

        # 4. Generate Hindi Voice-over (Edge-TTS)
        status.write("🔊 Step 4: Hindi Voice-over ban raha hai...")
        tts_audio = "hindi_tts.mp3"
        if os.path.exists(tts_audio):
            os.remove(tts_audio)

        async def make_tts():
            tts = edge_tts.Communicate(hindi_script, selected_voice)
            await tts.save(tts_audio)

        asyncio.run(make_tts())

        # 5. Apply Anti-Copyright Filters + Audio Merge (FFmpeg)
        status.write("🎨 Step 5: Anti-Copyright Filters apply ho rahe hain...")
        final_video = "final_output.mp4"
        if os.path.exists(final_video):
            os.remove(final_video)

        crop_factor = 1.0 - (zoom_percent / 100.0)
        vf_filters = [f"crop=in_w*{crop_factor}:in_h*{crop_factor},scale=1920:1080"]
        if apply_flip:
            vf_filters.append("hflip")
        vf_filters.append(f"eq=contrast={contrast_boost}:brightness=0.02:saturation={contrast_boost}")
        pts_speed = 1.0 / speed_mult
        vf_filters.append(f"setpts={pts_speed:.4f}*PTS")

        filter_string = ",".join(vf_filters)

        ffmpeg_cmd = (
            f'ffmpeg -y -i "{raw_video}" -i "{tts_audio}" '
            f'-filter_complex "[0:v]{filter_string}[v]" '
            f'-map "[v]" -map 1:a '
            f'-c:v libx264 -preset fast -crf 22 -c:a aac -b:a 192k '
            f'-shortest "{final_video}"'
        )
        
        subprocess.run(ffmpeg_cmd, shell=True, check=True)
        status.update(label="✅ Video Successfully Generate Ho Gayi!", state="complete")

        st.subheader("🎉 Final Edited Video (Copyright-Safe):")
        st.video(final_video)
        
        with open(final_video, "rb") as file:
            st.download_button(
                label="📥 Download Edited Video",
                data=file,
                file_name="copyright_free_hindi_video.mp4",
                mime="video/mp4"
            )
