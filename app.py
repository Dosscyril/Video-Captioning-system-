import os
import whisper
import subprocess
from flask import Flask, request, render_template, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
PROCESSED_FOLDER = "processed"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

def extract_audio(video_path, audio_path):
    try:
        subprocess.run(
            ["ffmpeg", "-i", video_path, "-q:a", "0", "-map", "a", audio_path, "-y"],
            check=True
        )
    except subprocess.CalledProcessError as e:
        print("FFmpeg Audio Extraction Error:", e)

def generate_srt(audio_path, srt_path):
    try:
        whisper_model = whisper.load_model("base")  # Load model on demand
        result = whisper_model.transcribe(audio_path)

        with open(srt_path, "w", encoding="utf-8") as f:
            for segment in result["segments"]:
                f.write(f"{segment['id']}\n")
                f.write(f"{format_timestamp(segment['start'])} --> {format_timestamp(segment['end'])}\n")
                f.write(f"{segment['text']}\n\n")

        return True
    except Exception as e:
        print("Whisper Error:", str(e))
        return False

def format_timestamp(seconds):
    """Formats seconds to HH:MM:SS,MS for SRT subtitles."""
    millisec = int((seconds % 1) * 1000)
    return f"{int(seconds // 3600):02}:{int((seconds % 3600) // 60):02}:{int(seconds % 60):02},{millisec:03}"

def add_subtitles(video_path, srt_path, output_path):
    """Overlays subtitles onto the video using FFmpeg."""
    try:
        video_path = video_path.replace("\\", "/")  # Ensure proper path formatting
        srt_path = srt_path.replace("\\", "/")
        output_path = output_path.replace("\\", "/")

        subprocess.run(
            ["ffmpeg", "-i", video_path, "-vf", f"subtitles={srt_path}", "-c:a", "copy", output_path, "-y"],
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print("FFmpeg Subtitle Error:", e)
        return False

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        video = request.files.get("video")
        subtitle = request.files.get("subtitle")

        if not video:
            return "Error: Video file is required!", 400

        filename = secure_filename(video.filename)
        video_path = os.path.join(UPLOAD_FOLDER, filename)
        video.save(video_path)

        audio_path = os.path.join(UPLOAD_FOLDER, "audio.wav")
        srt_path = os.path.join(UPLOAD_FOLDER, "subtitles.srt")
        output_path = os.path.join(PROCESSED_FOLDER, "output.mp4")

        if subtitle:
            subtitle_path = os.path.join(UPLOAD_FOLDER, secure_filename(subtitle.filename))
            subtitle.save(subtitle_path)
            srt_path = subtitle_path  # Use uploaded subtitle file

        else:
            extract_audio(video_path, audio_path)
            if not generate_srt(audio_path, srt_path):
                return "Error: Subtitle generation failed!", 500

        if add_subtitles(video_path, srt_path, output_path):
            return render_template("index.html", video_processed=True)

        return "Error: Subtitle overlay failed!", 500

    return render_template("index.html", video_processed=False)
    
@app.route("/download")
def download():
    output_path = os.path.join(PROCESSED_FOLDER, "output.mp4")
    if os.path.exists(output_path):
        return send_file(output_path, as_attachment=True)
    return "No processed video found!", 404
if __name__ == "__main__":
    app.run(debug=True)
