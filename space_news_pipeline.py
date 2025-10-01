import os, json, subprocess, requests, feedparser, re, random
from concurrent.futures import ThreadPoolExecutor, as_completed
import openai
from gtts import gTTS
from tqdm import tqdm
import warnings

# Silence Whisper FP16 warning on CPU
warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")

# -----------------------------
# LOAD CONFIG
# -----------------------------
with open("pipeline_config.json") as f:
    CONFIG = json.load(f)

openai.api_key = CONFIG["openai_key"]
PEXELS_KEY = CONFIG["pexels_key"]
PIXABAY_KEY = CONFIG["pixabay_key"]
UNSPLASH_KEY = CONFIG["unsplash_key"]
GIPHY_KEY = CONFIG["giphy_key"]

OUTPUT_DIR = CONFIG["output_dir"]
NARRATION_FILE = os.path.join(OUTPUT_DIR, "narration.mp3")
TRANSCRIPT_FILE = os.path.join(OUTPUT_DIR, "transcript.json")
MUSIC_FILE = os.path.join(OUTPUT_DIR, CONFIG["music_file"])
FINAL_VIDEO = os.path.join(OUTPUT_DIR, CONFIG["final_video"])

ARTICLES_PER_FEED = CONFIG["articles_per_feed"]

TRANSITION_TYPE = CONFIG["transition_type"]
TRANSITION_DURATION = CONFIG["transition_duration"]

DUCKING = CONFIG["ducking"]

NEWS_FEEDS = [
    "https://www.nasa.gov/rss/dyn/breaking_news.rss",
    "https://www.esa.int/rssfeed/Our_Activities",
    "https://www.space.com/feeds/all"
]

# -----------------------------
# MODE SWITCH
# -----------------------------
MODE = CONFIG.get("mode", "hq")  # default HQ if not set

if MODE == "fast":
    RESOLUTION = "854x480"
    PRESET = "ultrafast"
    CRF = "28"
    USE_KEN_BURNS = False  # static images only
    MAX_WORKERS = 6
else:
    RESOLUTION = CONFIG["resolution"]
    PRESET = "fast"
    CRF = "23"
    USE_KEN_BURNS = True
    MAX_WORKERS = CONFIG["max_workers"]

os.makedirs(OUTPUT_DIR, exist_ok=True)

# -----------------------------
# FFmpeg Helper with Progress
# -----------------------------
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

# -----------------------------
# STEP 1: FETCH NEWS
# -----------------------------
def fetch_articles():
    articles = []
    for url in NEWS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:ARTICLES_PER_FEED]:
            articles.append(entry.title + " - " + entry.summary)
    return articles

def summarize_to_script(articles):
    try:
        # First: OpenAI GPT
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role":"system","content":"You are a science journalist."},
                {"role":"user","content":f"Turn this space news into an engaging YouTube script for an 8-9 min video (~1300 words):\n{articles}"}
            ]
        )
        return resp["choices"][0]["message"]["content"]

    except Exception as e:
        print(f"⚠️ OpenAI failed: {e}")
        print("➡️ Trying Hugging Face fallback...")

        try:
            from transformers import pipeline
            summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

            text = " ".join(articles)[:4000]
            input_len = len(text.split())
            max_len = min(600, max(150, int(input_len * 0.6)))  # auto-adjust

            summary = summarizer(
                text,
                max_length=max_len,
                min_length=150,
                do_sample=False
            )[0]["summary_text"]

            script = "Welcome to Space News!\n\n"
            script += summary
            script += "\n\nThat's all for now in space news!"
            return script

        except Exception as e2:
            print(f"⚠️ Hugging Face fallback also failed: {e2}")
            print("➡️ Using basic text fallback...")

            fallback_script = "Welcome to Space News!\n\n"
            for i, article in enumerate(articles, start=1):
                fallback_script += f"Story {i}: {article}\n\n"
            fallback_script += "That's all for now in space news!"
            return fallback_script

# -----------------------------
# STEP 2: NARRATION
# -----------------------------
def text_to_speech(text, out_file=NARRATION_FILE):
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

# -----------------------------
# STEP 3: TRANSCRIPT
# -----------------------------
def transcribe_segments(audio_file, out_file=TRANSCRIPT_FILE):
    import whisper
    model = whisper.load_model("small")
    result = model.transcribe(audio_file)
    segments = [{"start": seg["start"], "end": seg["end"], "text": seg["text"]} for seg in result["segments"]]
    with open(out_file, "w") as f:
        json.dump(segments, f, indent=2)
    return segments

# -----------------------------
# STEP 4: VISUAL SOURCING
# -----------------------------
def search_nasa(query):
    url = f"https://images-api.nasa.gov/search?q={query}&media_type=image,video"
    r = requests.get(url)
    if r.status_code == 200:
        items = r.json()["collection"]["items"]
        if items:
            links = items[0].get("links", [])
            if links:
                return links[0]["href"]
    return None

def search_pexels(query):
    url = f"https://api.pexels.com/v1/search?query={query}&per_page=1"
    headers = {"Authorization": PEXELS_KEY}
    r = requests.get(url, headers=headers)
    if r.status_code == 200 and r.json()["photos"]:
        return r.json()["photos"][0]["src"]["large"]
    return None

def search_pixabay(query):
    url = f"https://pixabay.com/api/?key={PIXABAY_KEY}&q={query}&image_type=photo&video_type=all"
    r = requests.get(url)
    if r.status_code == 200 and r.json()["hits"]:
        hit = r.json()["hits"][0]
        return hit.get("largeImageURL") or hit.get("videos", {}).get("medium", {}).get("url")
    return None

def search_unsplash(query):
    url = f"https://api.unsplash.com/search/photos?query={query}&client_id={UNSPLASH_KEY}"
    r = requests.get(url)
    if r.status_code == 200 and r.json()["results"]:
        return r.json()["results"][0]["urls"]["regular"]
    return None

def search_giphy(query):
    url = f"https://api.giphy.com/v1/gifs/search?q={query}&api_key={GIPHY_KEY}&limit=1"
    r = requests.get(url)
    if r.status_code == 200 and r.json()["data"]:
        return r.json()["data"][0]["images"]["original"]["url"]
    return None

def ai_fallback(prompt, output_file):
    try:
        fallback_images = [
            "https://www.nasa.gov/sites/default/files/thumbnails/image/nasa-logo-web-rgb.png",
            "https://www.nasa.gov/sites/default/files/styles/full_width_feature/public/thumbnails/image/potw2023a.jpg",
            "https://www.nasa.gov/sites/default/files/thumbnails/image/iss056e201857.jpg",
            "https://www.nasa.gov/sites/default/files/thumbnails/image/mars2020-PIA23964-rovernameplate.jpg",
            "https://www.nasa.gov/sites/default/files/thumbnails/image/jwst_deep_field.png"
        ]
        chosen_url = random.choice(fallback_images)
        img_data = requests.get(chosen_url, timeout=30).content
        with open(output_file, "wb") as f:
            f.write(img_data)
        print(f"🖼️ AI fallback used {chosen_url} for: {prompt}")
    except Exception as e:
        print(f"⚠️ AI fallback failed for {prompt}: {e}")

# -----------------------------
# STEP 5: KEN BURNS / STATIC
# -----------------------------
def apply_ken_burns(image_file, output_file, duration=10):
    if USE_KEN_BURNS:
        zoom_expr = "zoom+0.0015"
        filter_str = f"zoompan=z='{zoom_expr}':d=25*{duration}:s={RESOLUTION},format=yuv420p"
        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-t", str(duration), "-i", image_file,
            "-filter_complex", filter_str,
            "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
            "-colorspace", "bt709", "-pix_fmt", "yuv420p",
            output_file
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-t", str(duration), "-i", image_file,
            "-vf", f"scale={RESOLUTION},format=yuv420p",
            "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
            "-colorspace", "bt709", "-pix_fmt", "yuv420p",
            output_file
        ]
    run_ffmpeg_with_progress(cmd, label=f"KenBurns-{os.path.basename(output_file)}",
                             total_time=duration, show_bar=False)

# -----------------------------
# STEP 6: SEGMENT MEDIA
# -----------------------------
def process_segment(i, seg, master_bar=None):
    duration = int(seg["end"] - seg["start"])
    query = seg["text"]
    clip_path = os.path.join(OUTPUT_DIR, f"clip{i}.mp4")

    url = (search_nasa(query) or search_pixabay(query) or
           search_pexels(query) or search_unsplash(query) or search_giphy(query))

    if url:
        try:
            data = requests.get(url, timeout=30).content
            temp_file = os.path.join(OUTPUT_DIR, f"temp{i}.dat")
            with open(temp_file, "wb") as f:
                f.write(data)

            if url.endswith(".gif") or url.endswith(".mp4"):
                cmd = [
                    "ffmpeg", "-y", "-i", temp_file, "-t", str(duration),
                    "-vf", "scale=" + RESOLUTION + ",format=yuv420p",
                    "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
                    "-colorspace", "bt709", "-pix_fmt", "yuv420p",
                    clip_path
                ]
                run_ffmpeg_with_progress(cmd, label=f"Segment-{i}",
                                         total_time=duration, show_bar=False)
            else:
                apply_ken_burns(temp_file, clip_path, duration=duration)
        except Exception:
            out_img = os.path.join(OUTPUT_DIR, f"ai{i}.png")
            ai_fallback(query, out_img)
            apply_ken_burns(out_img, clip_path, duration=duration)
    else:
        out_img = os.path.join(OUTPUT_DIR, f"ai{i}.png")
        ai_fallback(query, out_img)
        apply_ken_burns(out_img, clip_path, duration=duration)

    if master_bar:
        master_bar.update(1)
    return True

def generate_media_for_segments(segments, master_bar=None):
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_segment, i, seg, master_bar): i for i, seg in enumerate(segments, start=1)}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"❌ Segment failed: {e}")

# -----------------------------
# STEP 7: BUILD VIDEO
# -----------------------------
def build_video(segments):
    cmd = ["ffmpeg"]
    for i, seg in enumerate(segments, start=1):
        cmd.extend(["-i", os.path.join(OUTPUT_DIR, f"clip{i}.mp4")])
    cmd.extend(["-i", NARRATION_FILE, "-i", MUSIC_FILE])

    filters = []
    for i in range(len(segments)-1):
        dur = segments[i]["end"] - segments[i]["start"]
        if i==0:
            filters.append(f"[{i}:v][{i+1}:v]xfade=transition={TRANSITION_TYPE}:duration={TRANSITION_DURATION}:offset={dur},format=yuv420p[v{i+1}]")
        else:
            filters.append(f"[v{i}][{i+1}:v]xfade=transition={TRANSITION_TYPE}:duration={TRANSITION_DURATION}:offset={dur},format=yuv420p[v{i+1}]")

    filters.append(f"[{len(segments)}:a][{len(segments)+1}:a]sidechaincompress=threshold={DUCKING['threshold']}:ratio={DUCKING['ratio']}:attack={DUCKING['attack']}:release={DUCKING['release']}[aout]")

    cmd.extend(["-filter_complex", "; ".join(filters)])
    cmd.extend([
        "-map", f"[v{len(segments)-1}]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
        "-c:a", "aac", "-shortest",
        "-colorspace", "bt709", "-pix_fmt", "yuv420p",
        FINAL_VIDEO
    ])

    total_time = int(segments[-1]["end"])
    run_ffmpeg_with_progress(cmd, label="FinalVideo", total_time=total_time, show_bar=True)

# -----------------------------
# STEP 8: CLEANUP
# -----------------------------
def cleanup_media():
    keep_files = {NARRATION_FILE, TRANSCRIPT_FILE, FINAL_VIDEO}
    for f in os.listdir(OUTPUT_DIR):
        path = os.path.join(OUTPUT_DIR, f)
        if path not in keep_files and not path.endswith(".mp4"):
            try:
                os.remove(path)
            except:
                pass

# -----------------------------
# MAIN with MASTER PROGRESS BAR
# -----------------------------
if __name__ == "__main__":
    print("🚀 Starting Space News Pipeline... (mode:", MODE, ")")

    steps = 5
    articles = fetch_articles()

    master_bar = tqdm(total=steps+10, desc="Pipeline Progress",
                      unit="step", dynamic_ncols=True,
                      smoothing=0.3, leave=True)

    # Step 1: Script
    script = summarize_to_script(articles)
    master_bar.update(1)

    # Step 2: Narration
    text_to_speech(script)
    master_bar.update(1)

    # Step 3: Transcript
    segments = transcribe_segments(NARRATION_FILE)
    master_bar.update(1)

    # Reset master bar
    master_bar.total = steps + len(segments)
    master_bar.refresh()

    # Step 4: Media
    generate_media_for_segments(segments, master_bar=master_bar)

    # Step 5: Final Video
    build_video(segments)
    master_bar.update(1)

    # Step 6: Cleanup
    cleanup_media()
    master_bar.update(1)

    master_bar.close()
    print("✅ Done! Final video:", FINAL_VIDEO)
