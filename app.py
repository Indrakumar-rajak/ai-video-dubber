import streamlit as st
import subprocess
import os
import asyncio
import tempfile
from pathlib import Path

st.set_page_config(page_title="AI Video Studio", page_icon="🎬", layout="wide")

# -----------------------------
# Helpers
# -----------------------------
def run_cmd(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-4000:] or result.stdout[-4000:])
    return result.stdout

async def make_tts(text, voice, output):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output)

def get_duration(path):
    out = run_cmd(
        f'ffprobe -v error -show_entries format=duration '
        f'-of default=noprint_wrappers=1:nokey=1 "{path}"'
    )
    return float(out.strip())

def process_video(input_path, output_path, voiceover_path=None,
                  zoom=0, speed=1.0, flip=False, brightness=0.0,
                  contrast=1.0, saturation=1.0):
    filters = []

    if zoom > 0:
        factor = max(0.80, 1.0 - zoom / 100.0)
        filters.append(
            f"crop=iw*{factor}:ih*{factor},scale=iw:ih"
        )

    if flip:
        filters.append("hflip")

    if contrast != 1.0 or saturation != 1.0 or brightness != 0:
        filters.append(
            f"eq=contrast={contrast}:brightness={brightness}:saturation={saturation}"
        )

    if speed != 1.0:
        filters.append(f"setpts={1.0/speed:.6f}*PTS")

    vf = ",".join(filters) if filters else "null"

    if voiceover_path:
        cmd = (
            f'ffmpeg -y -i "{input_path}" -i "{voiceover_path}" '
            f'-filter_complex "[0:v]{vf}[v]" '
            f'-map "[v]" -map 1:a -c:v libx264 -preset medium -crf 23 '
            f'-c:a aac -b:a 192k -shortest "{output_path}"'
        )
    else:
        cmd = (
            f'ffmpeg -y -i "{input_path}" '
            f'-vf "{vf}" -c:v libx264 -preset medium -crf 23 '
            f'-c:a aac -b:a 192k "{output_path}"'
        )

    run_cmd(cmd)

# -----------------------------
# UI
# -----------------------------
st.title("🎬 AI Video Studio")
st.caption("Video Upload / Link → Hindi Voice-over → Edit → Preview → Download")

tab1, tab2 = st.tabs(["📁 Upload Video", "🔗 Video Link"])

video_path = None

with tab1:
    uploaded = st.file_uploader(
        "Video upload karein",
        type=["mp4", "mov", "mkv", "webm"]
    )
    if uploaded:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded.name).suffix)
        tmp.write(uploaded.getbuffer())
        tmp.close()
        video_path = tmp.name
        st.success(f"Video ready: {uploaded.name}")

with tab2:
    video_url = st.text_input("YouTube/video URL paste karein")
    if video_url:
        st.info("Link processing ke liye yt-dlp install hona zaroori hai.")

st.divider()

st.subheader("🎙️ Hindi Voice-over")

voice = st.selectbox(
    "Voice",
    [
        ("Madhur — Hindi Male", "hi-IN-MadhurNeural"),
        ("Swara — Hindi Female", "hi-IN-SwaraNeural")
    ],
    format_func=lambda x: x[0]
)

voiceover_text = st.text_area(
    "Hindi narration / voice-over script",
    height=180,
    placeholder="Yahan apni Hindi narration likhein..."
)

st.subheader("🎨 Video Editing")

c1, c2, c3, c4 = st.columns(4)
with c1:
    zoom = st.slider("Zoom %", 0, 10, 0)
with c2:
    speed = st.slider("Speed", 0.90, 1.10, 1.00, 0.01)
with c3:
    flip = st.checkbox("Mirror / Flip", False)
with c4:
    contrast = st.slider("Contrast", 0.90, 1.20, 1.00, 0.01)

c5, c6 = st.columns(2)
with c5:
    saturation = st.slider("Saturation", 0.80, 1.30, 1.00, 0.01)
with c6:
    brightness = st.slider("Brightness", -0.10, 0.10, 0.00, 0.01)

st.divider()

if "final_path" not in st.session_state:
    st.session_state.final_path = None

if st.button("🚀 Generate Final Video", type="primary", use_container_width=True):
    if video_path is None and not video_url:
        st.error("Pehle video upload karein ya video link dein.")
        st.stop()

    progress = st.progress(0)
    status = st.empty()

    try:
        # Download URL if needed
        if video_path is None and video_url:
            status.info("📥 Video download ho rahi hai...")
            progress.progress(10)
            raw = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
            run_cmd(f'yt-dlp -f "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b" '
                    f'--merge-output-format mp4 -o "{raw}" "{video_url}"')
            video_path = raw

        progress.progress(25)
        status.info("🎙️ Voice-over prepare ho raha hai...")

        voice_file = None
        if voiceover_text.strip():
            voice_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
            asyncio.run(make_tts(voiceover_text.strip(), voice[1], voice_file))

        progress.progress(55)
        status.info("🎨 Video render ho rahi hai...")

        final_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name

        process_video(
            video_path,
            final_file,
            voiceover_path=voice_file,
            zoom=zoom,
            speed=speed,
            flip=flip,
            brightness=brightness,
            contrast=contrast,
            saturation=saturation
        )

        progress.progress(100)
        status.success("✅ Final video ready!")
        st.session_state.final_path = final_file

    except Exception as e:
        progress.empty()
        st.error("Processing error:")
        st.code(str(e))

# -----------------------------
# Preview / Download
# -----------------------------
if st.session_state.final_path and os.path.exists(st.session_state.final_path):
    st.divider()
    st.subheader("🎥 Preview")

    st.video(st.session_state.final_path)

    with open(st.session_state.final_path, "rb") as f:
        st.download_button(
            "📥 Download Final Video",
            data=f,
            file_name="final_video.mp4",
            mime="video/mp4",
            use_container_width=True
        )

    st.info(
        "YouTube upload ko next step mein OAuth/API ke through connect kiya ja sakta hai. "
        "Upload se pehle video ko private/unlisted rakhkar test karna safer hai."
    )

st.divider()
st.caption("⚠️ Copyright note: editing effects copyright ownership ya Content ID claims ko automatically remove nahi karte. Sirf wahi content use karein jiske use ki permission/rights aapke paas hain.")
