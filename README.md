# Space News Video Pipeline

Automated video generation pipeline that creates engaging space news videos from RSS feeds.

## Project Type

This is a **Python project** that uses FFmpeg for video processing.

## Quick Start

### 1. Install Dependencies

```bash
# Install Python packages
pip install -r requirements.txt

# Install FFmpeg
# Ubuntu/Debian:
sudo apt-get install ffmpeg

# macOS:
brew install ffmpeg

# Windows: Download from https://ffmpeg.org/download.html
```

### 2. Configure API Keys

Edit `pipeline_config.json` and add your API keys:
- OpenAI API key (for script generation)
- Pexels, Pixabay, Unsplash, Giphy API keys (for media)

### 3. Set Up Environment

The `.env` file with Supabase credentials is already configured.

### 4. Verify Setup

```bash
python3 setup_check.py
```

### 5. Run Pipeline

```bash
# Run optimized pipeline (recommended)
python3 space_news_pipeline_optimized.py

# Or run original pipeline
python3 space_news_pipeline.py
```

## Features

- Fetches latest space news from NASA, ESA, and Space.com
- Generates scripts using OpenAI GPT
- Creates narration with text-to-speech
- Sources visuals from multiple free APIs
- Applies Ken Burns effects and transitions
- GPU-accelerated rendering when available
- Intelligent caching with Supabase database
- Multiple quality presets (ultra_fast to production)

## Optimization Features

The optimized pipeline includes:
- 50-70% reduction in API calls through caching
- 2-4x faster rendering with GPU acceleration
- Circuit breaker pattern for API reliability
- Resource management to prevent system overload
- Progress tracking and error recovery

See `OPTIMIZATION_GUIDE.md` for detailed information.

## Requirements

- Python 3.8+
- FFmpeg
- 5GB+ free disk space
- (Optional) NVIDIA GPU with NVENC support for faster rendering

## Troubleshooting

**Error: npm/package.json not found**
This is a Python project. Ensure you're using Python commands, not npm.

**Error: pip not found**
Install pip for your Python version or use `python3 -m pip install -r requirements.txt`

**Slow rendering**
Try a faster preset in `pipeline_config.json`: `"preset": "fast"` or `"preset": "balanced"`
