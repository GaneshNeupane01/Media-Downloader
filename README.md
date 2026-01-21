# Media Downloader (PySide6 + yt-dlp)

![Demo](UI_Glance_MediaDownloader.jpg)

Simple desktop app to download audio/video from YouTube and many other sites using yt-dlp, with a PySide6 UI and optional metadata (cover art + lyrics).

## Features
- Download audio or video
- Bulk playlist downloads (audio or video)
- Metadata: cover art and synced/plain lyrics (LRCLib + Genius fallback)
- Parallel downloads where applicable
- Choose video quality before downloading
- Supports hundreds of sites via yt-dlp

## Requirements
- Python 3.8+
- ffmpeg (for audio extraction and video merging)
- On Linux: `python3-tk` (tkinter) for message dialogs
- Internet connection for fetching metadata/thumbnails

## Setup
1. Create a virtual environment (recommended) and install dependencies:
	```bash
	python3 -m venv .venv
	source .venv/bin/activate
	pip install -r requirements.txt
	```
2. Install system packages (Ubuntu/Debian example):
	```bash
	sudo apt update
	sudo apt install ffmpeg python3-tk
	```

## Run
```bash
python3 main.py
```

## Notes
- Web view for the “Watch Video” dialog uses `PySide6-QtWebEngine`.
- Lyrics are fetched via LRCLib first, then Genius as a fallback.
- If ffmpeg is missing, audio extraction (MP3) and video merges will fail.

## Optional: Build
Pack into a single executable with PyInstaller (spec file provided):
```bash
pyinstaller MediaDownloader.spec
```


## More Details
For screenshots and extra info: https://ganesh-neupane.com.np/MediaDownloaderDetails


## 👤 Author
**Ganesh Neupane**
Computer Engineering 
- GitHub: [@GaneshNeupane01](https://github.com/GaneshNeupane01)
- Detail: [@portfolio](https://ganesh-neupane.com.np)
- Email: ganeshneupane1357@gmail.com
