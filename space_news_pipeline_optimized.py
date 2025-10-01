import os
import json
import subprocess
import requests
import feedparser
import re
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import openai
from gtts import gTTS
from tqdm import tqdm
import warnings
from dotenv import load_dotenv

from database_client import DatabaseClient
from api_manager import APIManager
from gpu_detector import GPUDetector
from resource_manager import ResourceManager
from config_presets import ConfigPresets

warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")

load_dotenv()

with open("pipeline_config.json") as f:
    BASE_CONFIG = json.load(f)

PRESET_NAME = BASE_CONFIG.get("preset", "balanced")
CONFIG = ConfigPresets.merge_with_preset(PRESET_NAME, BASE_CONFIG)

db = DatabaseClient()
api_manager = APIManager(db)
gpu = GPUDetector()
resource_mgr = ResourceManager()

openai.api_key = CONFIG["openai_key"]
api_manager.set_api_keys(
    CONFIG["pexels_key"],
    CONFIG["pixabay_key"],
    CONFIG["unsplash_key"],
    CONFIG["giphy_key"]
)

OUTPUT_DIR = CONFIG["output_dir"]
NARRATION_FILE = os.path.join(OUTPUT_DIR, "narration.mp3")
TRANSCRIPT_FILE = os.path.join(OUTPUT_DIR, "transcript.json")
MUSIC_FILE = os.path.join(OUTPUT_DIR, CONFIG.get("music_file", "background.mp3"))
FINAL_VIDEO = os.path.join(OUTPUT_DIR, CONFIG.get("final_video", "final_output.mp4"))

ARTICLES_PER_FEED = CONFIG.get("articles_per_feed", 3)
TRANSITION_TYPE = CONFIG.get("transition_type", "fade")
TRANSITION_DURATION = CONFIG.get("transition_duration", 0.8)
DUCKING = CONFIG.get("ducking", {"threshold": 0.03, "ratio": 4, "attack": 20, "release": 1000})

NEWS_FEEDS = [
    "https://www.nasa.gov/rss/dyn/breaking_news.rss",
    "https://www.esa.int/rssfeed/Our_Activities",
    "https://www.space.com/feeds/all"
]

RESOLUTION = CONFIG["resolution"]
PRESET = CONFIG["preset"]
CRF = str(CONFIG["crf"])
USE_KEN_BURNS = CONFIG["use_ken_burns"]
MAX_WORKERS = resource_mgr.get_optimal_workers(
    min_workers=2,
    max_workers=CONFIG.get("max_workers", 4)
)

os.makedirs(OUTPUT_DIR, exist_ok=True)

current_job_id = None

print(f"🚀 Optimized Pipeline Starting...")
print(f"📊 Preset: {PRESET_NAME}")
print(f"🎬 Resolution: {RESOLUTION}")
print(f"⚙️ Workers: {MAX_WORKERS}")
print(f"💾 GPU: {gpu.gpu_info.get('type', 'cpu').upper()}")
print(f"🖥️ System: {resource_mgr.cpu_count} CPUs, {resource_mgr.get_system_info()['memory_total_gb']:.1f}GB RAM\n")

def run_ffmpeg_with_progress(cmd, label="FFmpeg", total_time=None, show_bar=True):
    cmd.extend(["-progress", "pipe:1", "-nostats", "-loglevel", "0"])
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    pbar = tqdm(total=total_time, unit="s", desc=label,
                dynamic_ncols=True, smoothing=0.3,
                leave=show_bar, disable=not show_bar)

    time_pattern = re.compile(r"out_time=(\d+):(\d+):(\d+)\.(\d+)")

    for line in process.stdout:
        line = line.strip()
        if line.startswith("out_time="):
            match = time_pattern.match(line)
            if match:
                hh, mm, ss, ms = match.groups()
                seconds = int(hh) * 3600 + int(mm) * 60 + int(ss) + int(ms) / 100.0
                if total_time:
                    pbar.n = min(seconds, total_time)
                    pbar.refresh()
        elif line.startswith("progress=end"):
            break

    process.wait()
    pbar.close()

    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, cmd)

def fetch_articles():
    print("📰 Fetching space news...")
    articles = []
    for url in NEWS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:ARTICLES_PER_FEED]:
                articles.append(entry.title + " - " + entry.summary)
        except Exception as e:
            print(f"⚠️ Failed to fetch from {url}: {e}")
    return articles

def summarize_to_script(articles):
    articles_text = "\n".join(articles)
    articles_hash = db.hash_content(articles_text)

    if CONFIG.get("enable_script_cache", True):
        cached_script = db.get_cached_script(articles_hash)
        if cached_script:
            print("✅ Using cached script")
            return cached_script

    try:
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a science journalist."},
                {"role": "user", "content": f"Turn this space news into an engaging YouTube script for an 8-9 min video (~1300 words):\n{articles_text}"}
            ]
        )
        script = resp["choices"][0]["message"]["content"]

        if CONFIG.get("enable_script_cache", True):
            word_count = len(script.split())
            db.save_script_cache(articles_hash, script, "gpt-3.5-turbo", word_count)

        return script

    except Exception as e:
        print(f"⚠️ OpenAI failed: {e}")
        print("➡️ Trying Hugging Face fallback...")

        try:
            from transformers import pipeline
            summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

            text = " ".join(articles)[:4000]
            input_len = len(text.split())
            max_len = min(600, max(150, int(input_len * 0.6)))

            summary = summarizer(
                text,
                max_length=max_len,
                min_length=150,
                do_sample=False
            )[0]["summary_text"]

            script = "Welcome to Space News!\n\n"
            script += summary
            script += "\n\nThat's all for now in space news!"

            if CONFIG.get("enable_script_cache", True):
                word_count = len(script.split())
                db.save_script_cache(articles_hash, script, "bart-large-cnn", word_count)

            return script

        except Exception as e2:
            print(f"⚠️ Hugging Face fallback also failed: {e2}")
            print("➡️ Using basic text fallback...")

            fallback_script = "Welcome to Space News!\n\n"
            for i, article in enumerate(articles, start=1):
                fallback_script += f"Story {i}: {article}\n\n"
            fallback_script += "That's all for now in space news!"
            return fallback_script

def text_to_speech(text, out_file=NARRATION_FILE):
    print("🎙️ Generating narration...")
    voice = CONFIG.get("voice", "default")

    if voice == "uk":
        tts = gTTS(text=text, lang="en", tld="co.uk")
    elif voice == "au":
        tts = gTTS(text=text, lang="en", tld="com.au")
    elif voice == "in":
        tts = gTTS(text=text, lang="en", tld="co.in")
    else:
        tts = gTTS(text=text, lang="en")

    tts.save(out_file)

def transcribe_segments(audio_file, out_file=TRANSCRIPT_FILE):
    audio_hash = db.hash_file(audio_file)
    model_name = "small"

    if CONFIG.get("enable_transcription_cache", True):
        cached_segments = db.get_cached_transcription(audio_hash, model_name)
        if cached_segments:
            print("✅ Using cached transcription")
            with open(out_file, "w") as f:
                json.dump(cached_segments, f, indent=2)
            return cached_segments

    print("🎧 Transcribing audio...")
    import whisper
    model = whisper.load_model(model_name)
    result = model.transcribe(audio_file)
    segments = [{"start": seg["start"], "end": seg["end"], "text": seg["text"]} for seg in result["segments"]]

    with open(out_file, "w") as f:
        json.dump(segments, f, indent=2)

    if CONFIG.get("enable_transcription_cache", True):
        duration = int(segments[-1]["end"]) if segments else 0
        db.save_transcription_cache(audio_hash, model_name, segments, duration)

    return segments

def download_media(url: str, output_path: str):
    data = requests.get(url, timeout=30).content
    with open(output_path, "wb") as f:
        f.write(data)
    return db.hash_file(output_path)

def apply_ken_burns(image_file, output_file, duration=10):
    encoding_args = gpu.get_ffmpeg_encoding_args(RESOLUTION, CRF, PRESET)

    if USE_KEN_BURNS:
        zoom_expr = "zoom+0.0015"
        scale_filter = gpu.get_scale_filter(RESOLUTION)

        filter_complex = f"zoompan=z='{zoom_expr}':d=25*{duration}:s={RESOLUTION}"

        if gpu.requires_hw_upload():
            hw_upload = gpu.get_hw_upload_filter()
            filter_complex = f"{filter_complex},{hw_upload},{scale_filter}"
        else:
            filter_complex = f"{filter_complex},{scale_filter},format=yuv420p"

        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-t", str(duration), "-i", image_file,
            "-filter_complex", filter_complex,
            *encoding_args,
            "-colorspace", "bt709", "-pix_fmt", "yuv420p",
            output_file
        ]
    else:
        scale_filter = gpu.get_scale_filter(RESOLUTION)
        filter_str = f"{scale_filter},format=yuv420p"

        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-t", str(duration), "-i", image_file,
            "-vf", filter_str,
            *encoding_args,
            "-colorspace", "bt709", "-pix_fmt", "yuv420p",
            output_file
        ]

    run_ffmpeg_with_progress(cmd, label=f"KB-{os.path.basename(output_file)[:10]}",
                             total_time=duration, show_bar=False)

def process_segment(i, seg, master_bar=None):
    duration = int(seg["end"] - seg["start"])
    query = seg["text"]
    clip_path = os.path.join(OUTPUT_DIR, f"clip{i}.mp4")

    if CONFIG.get("enable_media_cache", True):
        cached_media = db.get_cached_media(query)
        if cached_media and os.path.exists(cached_media.get("local_path", "")):
            print(f"✅ Cache hit for segment {i}")
            try:
                apply_ken_burns(cached_media["local_path"], clip_path, duration=duration)
                if master_bar:
                    master_bar.update(1)
                return True
            except:
                pass

    url = api_manager.search_with_fallback(query, prefer_video=(duration > 15))

    if url:
        try:
            temp_file = os.path.join(OUTPUT_DIR, f"temp{i}.dat")
            file_hash = download_media(url, temp_file)

            if url.endswith(".gif") or url.endswith(".mp4"):
                encoding_args = gpu.get_ffmpeg_encoding_args(RESOLUTION, CRF, PRESET)
                scale_filter = gpu.get_scale_filter(RESOLUTION)

                cmd = [
                    "ffmpeg", "-y", "-i", temp_file, "-t", str(duration),
                    "-vf", f"{scale_filter},format=yuv420p",
                    *encoding_args,
                    "-colorspace", "bt709", "-pix_fmt", "yuv420p",
                    clip_path
                ]
                run_ffmpeg_with_progress(cmd, label=f"Seg-{i}",
                                         total_time=duration, show_bar=False)
            else:
                apply_ken_burns(temp_file, clip_path, duration=duration)

            if CONFIG.get("enable_media_cache", True):
                file_size = os.path.getsize(temp_file)
                media_type = "video" if url.endswith((".mp4", ".gif")) else "image"
                source = "unknown"
                for src in ["nasa", "pexels", "pixabay", "unsplash", "giphy"]:
                    if src in url.lower():
                        source = src
                        break

                db.save_media_cache(
                    query=query,
                    source=source,
                    media_url=url,
                    local_path=temp_file,
                    file_hash=file_hash,
                    media_type=media_type,
                    resolution=RESOLUTION,
                    file_size=file_size
                )

        except Exception as e:
            print(f"⚠️ Failed to process URL for segment {i}: {e}")
            fallback_image = os.path.join(OUTPUT_DIR, f"fallback{i}.png")
            create_fallback_image(query, fallback_image)
            apply_ken_burns(fallback_image, clip_path, duration=duration)
    else:
        fallback_image = os.path.join(OUTPUT_DIR, f"fallback{i}.png")
        create_fallback_image(query, fallback_image)
        apply_ken_burns(fallback_image, clip_path, duration=duration)

    if master_bar:
        master_bar.update(1)
    return True

def create_fallback_image(prompt, output_file):
    fallback_images = [
        "https://www.nasa.gov/sites/default/files/thumbnails/image/nasa-logo-web-rgb.png",
        "https://www.nasa.gov/sites/default/files/styles/full_width_feature/public/thumbnails/image/potw2023a.jpg",
        "https://www.nasa.gov/sites/default/files/thumbnails/image/iss056e201857.jpg",
        "https://www.nasa.gov/sites/default/files/thumbnails/image/mars2020-PIA23964-rovernameplate.jpg",
        "https://www.nasa.gov/sites/default/files/thumbnails/image/jwst_deep_field.png"
    ]
    chosen_url = random.choice(fallback_images)
    try:
        img_data = requests.get(chosen_url, timeout=30).content
        with open(output_file, "wb") as f:
            f.write(img_data)
    except Exception as e:
        print(f"⚠️ Fallback failed: {e}")

def generate_media_for_segments(segments, master_bar=None):
    print(f"🎬 Processing {len(segments)} segments with {MAX_WORKERS} workers...")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_segment, i, seg, master_bar): i
                  for i, seg in enumerate(segments, start=1)}

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"❌ Segment failed: {e}")

def build_video(segments):
    print("🎞️ Building final video...")

    if not os.path.exists(MUSIC_FILE):
        print(f"⚠️ Music file not found: {MUSIC_FILE}, creating silent audio...")
        duration = int(segments[-1]["end"])
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
            "-t", str(duration), "-c:a", "aac", MUSIC_FILE
        ]
        subprocess.run(cmd, capture_output=True)

    cmd = ["ffmpeg", "-y"]

    for i in range(len(segments)):
        cmd.extend(["-i", os.path.join(OUTPUT_DIR, f"clip{i+1}.mp4")])

    cmd.extend(["-i", NARRATION_FILE, "-i", MUSIC_FILE])

    filter_parts = []
    for i in range(len(segments)):
        filter_parts.append(f"[{i}:v]")

    concat_filter = f"{''.join(filter_parts)}concat=n={len(segments)}:v=1:a=0[vout]"

    audio_filter = f"[{len(segments)}:a][{len(segments)+1}:a]amerge=inputs=2,pan=stereo|c0<c0+0.3*c2|c1<c1+0.3*c3[aout]"

    filter_complex = f"{concat_filter};{audio_filter}"

    encoding_args = gpu.get_ffmpeg_encoding_args(RESOLUTION, CRF, PRESET)

    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "[vout]", "-map", "[aout]",
        *encoding_args,
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        "-colorspace", "bt709", "-pix_fmt", "yuv420p",
        FINAL_VIDEO
    ])

    total_time = int(segments[-1]["end"])
    run_ffmpeg_with_progress(cmd, label="Final Video", total_time=total_time, show_bar=True)

def cleanup_media():
    print("🧹 Cleaning up temporary files...")
    keep_files = {NARRATION_FILE, TRANSCRIPT_FILE, FINAL_VIDEO, MUSIC_FILE}

    for f in os.listdir(OUTPUT_DIR):
        path = os.path.join(OUTPUT_DIR, f)
        if path not in keep_files and os.path.isfile(path):
            if not path.endswith(".mp4") or path.startswith(os.path.join(OUTPUT_DIR, "clip")):
                try:
                    os.remove(path)
                except:
                    pass

if __name__ == "__main__":
    start_time = time.time()

    print(f"🚀 Starting Optimized Space News Pipeline (preset: {PRESET_NAME})...\n")

    if not resource_mgr.check_disk_space(required_gb=5.0):
        print("❌ Insufficient disk space! Need at least 5GB free.")
        exit(1)

    current_job_id = db.create_render_job(
        job_name=f"SpaceNews_{int(time.time())}",
        mode=PRESET_NAME
    )["id"]

    try:
        db.update_render_job(current_job_id, {"status": "processing", "current_step": "fetching_news"})

        articles = fetch_articles()
        master_bar = tqdm(total=100, desc="Overall Progress", unit="%",
                         dynamic_ncols=True, smoothing=0.3, leave=True)

        db.update_render_job(current_job_id, {"current_step": "generating_script"})
        script = summarize_to_script(articles)
        master_bar.update(10)

        db.update_render_job(current_job_id, {"current_step": "generating_narration"})
        text_to_speech(script)
        master_bar.update(10)

        db.update_render_job(current_job_id, {"current_step": "transcribing"})
        segments = transcribe_segments(NARRATION_FILE)
        master_bar.update(10)

        db.update_render_job(current_job_id, {
            "total_segments": len(segments),
            "current_step": "processing_media"
        })

        segment_bar = tqdm(total=len(segments), desc="Segments", unit="seg", leave=False)
        generate_media_for_segments(segments, master_bar=segment_bar)
        segment_bar.close()
        master_bar.update(50)

        db.update_render_job(current_job_id, {"current_step": "building_video"})
        build_video(segments)
        master_bar.update(15)

        db.update_render_job(current_job_id, {"current_step": "cleanup"})
        cleanup_media()
        master_bar.update(5)

        master_bar.close()

        elapsed_time = int(time.time() - start_time)
        db.update_render_job(current_job_id, {
            "status": "completed",
            "progress_percent": 100,
            "actual_time_sec": elapsed_time,
            "completed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "output_path": FINAL_VIDEO
        })

        print(f"\n✅ Done! Final video: {FINAL_VIDEO}")
        print(f"⏱️ Total time: {elapsed_time // 60}m {elapsed_time % 60}s")
        print(f"💾 GPU used: {gpu.gpu_info.get('type', 'cpu').upper()}")

    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        db.update_render_job(current_job_id, {
            "status": "failed",
            "error_log": json.dumps([{"error": str(e), "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}])
        })
        raise
