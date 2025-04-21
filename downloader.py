import os,re
from tkinter import messagebox, filedialog
from yt_dlp import YoutubeDL
from metadata import add_metadata
from functools import partial
import yt_dlp as youtube_dl

# Global variables for custom download folder overrides
AUDIO_DOWNLOAD_FOLDER = None
VIDEO_DOWNLOAD_FOLDER = None

# Global cancel flags (reset before each download)
aCANCEL_FLAG = False
vCANCEL_FLAG = False

def set_audio_download_folder(folder):
    global AUDIO_DOWNLOAD_FOLDER
    AUDIO_DOWNLOAD_FOLDER = folder

def set_video_download_folder(folder):
    global VIDEO_DOWNLOAD_FOLDER
    VIDEO_DOWNLOAD_FOLDER = folder

def acancel_download():
    global aCANCEL_FLAG
    aCANCEL_FLAG = True

def vcancel_download():
    global vCANCEL_FLAG
    vCANCEL_FLAG = True

def reset_vcancel_flag():
    global vCANCEL_FLAG
    vCANCEL_FLAG = False

def reset_acancel_flag():
    global aCANCEL_FLAG
    aCANCEL_FLAG = False

def get_default_audio_folder():
    global AUDIO_DOWNLOAD_FOLDER
    if AUDIO_DOWNLOAD_FOLDER:
        folder = AUDIO_DOWNLOAD_FOLDER
    else:
        folder = os.path.join(os.path.expanduser("~"), "Downloads", "MediaDownloader", "Audio")
    os.makedirs(folder, exist_ok=True)
    return folder

def get_default_video_folder():
    global VIDEO_DOWNLOAD_FOLDER
    if VIDEO_DOWNLOAD_FOLDER:
        folder = VIDEO_DOWNLOAD_FOLDER
    else:
        folder = os.path.join(os.path.expanduser("~"), "Downloads", "MediaDownloader", "Video")
    os.makedirs(folder, exist_ok=True)
    return folder

def aprogress_hook(d,isFromSearch, status_callback=None, item_index=None, total_items=None):    #audio progress hook
    global aCANCEL_FLAG
    if aCANCEL_FLAG and not isFromSearch:
        raise Exception("Audio Download Cancelled by User")
    
    status = d.get("status")
    if status == "downloading":
        downloaded_bytes = d.get("downloaded_bytes", 0)
        total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        downloaded_mb = downloaded_bytes / 1024 / 1024
        if total_bytes > 0:
            total_mb = total_bytes / 1024 / 1024
            text = f"Downloaded {downloaded_mb:.2f} MB / {total_mb:.2f} MB"
        else:
            text = f"Downloaded {downloaded_mb:.2f} MB"
        if status_callback:
            status_callback(text)
    elif status == "finished":
        text = "Download finished." if not (item_index and total_items) else "Finished downloading."
        if status_callback:
            status_callback(text)

def vprogress_hook(d,isFromSearch, status_callback=None, item_index=None, total_items=None):  #video progress hook
    global vCANCEL_FLAG
    if vCANCEL_FLAG and not isFromSearch:
        raise Exception("Video Download Cancelled by User")
    
    status = d.get("status")
    if status == "downloading":
        downloaded_bytes = d.get("downloaded_bytes", 0)
        total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        downloaded_mb = downloaded_bytes / 1024 / 1024
        if total_bytes > 0:
            total_mb = total_bytes / 1024 / 1024
            text = f"Downloaded {downloaded_mb:.2f} MB / {total_mb:.2f} MB"
        else:
            text = f"Downloaded {downloaded_mb:.2f} MB"
        if status_callback:
            status_callback(text)
    elif status == "finished":
        text = "Download finished." if not (item_index and total_items) else "Finished downloading."
        if status_callback:
            status_callback(text)

def download_video(url,isFromSearch=False, status_callback=None):  
    # this function downloads video as audio and  add metadata also(best for music etc)
    # This function downloads audio (using yt-dlp’s audio extraction)
    try:
        reset_acancel_flag()
        download_folder = get_default_audio_folder()
        os.makedirs(download_folder, exist_ok=True)
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(download_folder, '%(title)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
            'quiet': True,
            'writethumbnail': True,
            'postprocessor_args': [
                '-metadata', 'title=%(title)s',
                '-metadata', 'artist=%(uploader)s'
            ],
            'progress_hooks': [
                lambda d: aprogress_hook(d,isFromSearch, status_callback=status_callback)
            ],
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            mp3_file = os.path.splitext(filename)[0] + '.mp3'
        original_title = info.get('title', 'Unknown Title')
        
        metadata = {
            'title': original_title,
            'artists': info.get('artist') or [info.get('uploader', 'Unknown Artist')],
            'album': info.get('album', 'Unknown Album'),
            'year': str(info.get('release_year', info.get('upload_date', '')[:4] or 'Unknown Year')),
            'genre': info.get('genre', 'Unknown Genre'),
            'thumbnail_url': info.get('thumbnail', ''),
        }
        otl=""
        arti = None
        
        isFromYoutube = False
        if "youtube" in url or "youtu.be" in url:
         if any(keyword in original_title.lower() for keyword in ["official", "video", "lyric","mashup","audio","-"]):
           
           if isinstance(original_title, list):
              original_title = " ".join(original_title)
           if '-' in original_title:
             arti, rest = [part.strip() for part in original_title.split('-', 1)]
             titl = re.sub(r'(\(.*?\)|\[.*?\])', '', rest).strip()
             jugad = f"{arti}, {titl}"
             print(arti,titl,jugad)
             metadata['title'] = titl
             otl = original_title
             
             print(metadata['artists'])
             if not metadata['artists']:
              metadata["artists"]=arti
             print(metadata['artists'])
             isFromYoutube = True
        
        print("Final title:", metadata['title'])
        add_metadata(
            mp3_file,
            metadata['title'],
            metadata['artists'],
            metadata['album'],
            metadata['year'],
            metadata['genre'],
            metadata['thumbnail_url'],
            isFromYoutube,
            otl,
            arti
        )
        webp_file = os.path.splitext(filename)[0] + '.webp'
        if os.path.exists(webp_file):
            os.remove(webp_file)
        return True
    except Exception as e:
        messagebox.showerror("Download Error", f"Failed to download audio: {str(e)}")
        return False

def download_video_file(url,isFromSearch=False, quality="best", status_callback=None):

    # This function downloads video in mp4 format(as video)
    try:
        reset_vcancel_flag()
        download_folder = get_default_video_folder()
        os.makedirs(download_folder, exist_ok=True)
        fmt = "bestvideo+bestaudio/best" if quality == "best" else f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]"
        ydl_opts = {
            'format': fmt,
            'merge_output_format': 'mp4',
            'outtmpl': os.path.join(download_folder, '%(title)s.%(ext)s'),
            'quiet': True,
            'progress_hooks': [
                lambda d: vprogress_hook(d,isFromSearch, status_callback=status_callback)
            ],
        }
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return True
    except Exception as e:
        messagebox.showerror("Video Download Error", f"Failed to download video: {str(e)}")
        return False

def returnUrlInfo(url):
    with YoutubeDL({'quiet': True}) as ydl:
        res = ydl.extract_info(url, download=False)
        return res if res else None

def returnAudPlayUrlInfo(url):
    ydl_opts = {'quiet': True, 'extract_flat': True}
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    playlist_title = info.get('title', 'unknown')
    entries = info.get('entries', [])
    num_files = len(entries)
    thumbnail_url = ''
    if entries:
        first_entry = entries[0]
        thumbnail_url = first_entry.get('thumbnail', '')
        if not thumbnail_url:
            first_video_url = first_entry.get('url')
            if first_video_url:
                with YoutubeDL({'quiet': True}) as ydl:
                    first_video_info = ydl.extract_info(first_video_url, download=False)
                    thumbnail_url = first_video_info.get('thumbnail', '')
    return [playlist_title, num_files, thumbnail_url]

def download_playlist(playlist_url, status_callback=None, progress_callback_audio=None):
    #this function video playlist in audio format with metadata(best for downloading music playlists)
    try:
        reset_acancel_flag()
        
        ydl_opts_flat = {'quiet': True, 'extract_flat': True}
        with YoutubeDL(ydl_opts_flat) as ydl:
            playlist_info = ydl.extract_info(playlist_url, download=False)
        entries = playlist_info.get('entries', [])
        total_items = len(entries)
        playlist_title = playlist_info.get('title', 'Unknown Playlist')
        download_folder = os.path.join(f"{get_default_audio_folder()}",f"{playlist_title}")
        os.makedirs(download_folder, exist_ok=True)

        def download_single_audio(i, entry):
            global aCANCEL_FLAG
            if aCANCEL_FLAG:
                raise Exception("Audio playlist download cancelled")
            video_url = entry.get('webpage_url') or entry.get('url')
            if not video_url:
                return
            with YoutubeDL({'quiet': True}) as ydl:
                video_info = ydl.extract_info(video_url, download=False)
            title = video_info.get('title', 'Unknown Title')
            thumbnail = video_info.get('thumbnail', '')
            if progress_callback_audio:
                progress_callback_audio(title, thumbnail, i, total_items, playlist_title)
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(download_folder, '%(title)s.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
                'quiet': True,
                'writethumbnail': True,
                'postprocessor_args': [
                    '-metadata', 'title=%(title)s',
                    '-metadata', 'artist=%(uploader)s'
                ],
                'progress_hooks': [
                    lambda d: aprogress_hook(d, status_callback=status_callback, item_index=i, total_items=total_items)
                ],
            }
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
                filename = ydl.prepare_filename(video_info)
                mp3_file = os.path.splitext(filename)[0] + '.mp3'
            # Add metadata after download
            title_for_file = video_info.get('title', 'Unknown Title')
            #mp3_file = os.path.join(download_folder, f"{title_for_file}.mp3")
            original_title = video_info.get('title', 'Unknown Title')
            #raw_title = video_info.get('title', 'Unknown Title')
            #clean_title = raw_title.split('(')[0].split('|')[0].split('-')[0].strip()
            metadata = {
                'title': original_title,
                'artists': video_info.get('artist') or [video_info.get('uploader', 'Unknown Artist')],
                'album': video_info.get('album', 'Unknown Album'),
                'year': str(video_info.get('release_year', video_info.get('upload_date', '')[:4] or 'Unknown Year')),
                'genre': video_info.get('genre', 'Unknown Genre'),
                'thumbnail_url': video_info.get('thumbnail', ''),
            }
            otl = ""
            arti=None
            isFromYoutube = False
            if "youtube" in video_url or "youtu.be" in video_url:
             if any(keyword in original_title.lower() for keyword in ["official", "video", "lyric","mashup","audio","-"]):
           
              if isinstance(original_title, list):
                original_title = " ".join(original_title)
              if '-' in original_title:
                arti, rest = [part.strip() for part in original_title.split('-', 1)]
                titl = re.sub(r'(\(.*?\)|\[.*?\])', '', rest).strip()
                jugad = f"{arti}, {titl}"
                print(arti,titl,jugad)
                metadata['title'] = titl
                otl = original_title
                if not metadata['artists']:

                  metadata["artists"]=arti
                isFromYoutube = True
        
            print("Final title:", metadata['title'])



            add_metadata(
                mp3_file,
                metadata['title'],
                metadata['artists'],
                metadata['album'],
                metadata['year'],
                metadata['genre'],
                metadata['thumbnail_url'],
                isFromYoutube,
                otl,
                arti
            )

            webp_file = os.path.splitext(filename)[0] + '.webp'


           # webp_file = os.path.splitext(mp3_file)[0] + ".webp"
            if os.path.exists(webp_file):
                os.remove(webp_file)
            

        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for i, entry in enumerate(entries, start=1):
                futures.append(executor.submit(download_single_audio, i, entry))
            for future in concurrent.futures.as_completed(futures):
                # This will raise any exception from the worker (including cancellation)
                future.result()
        return True
    except Exception as e:
        messagebox.showerror("Playlist Error", f"Failed to download playlist: {str(e)}")
        return False


def download_playlist_video(playlist_url, quality="best", status_callback=None, progress_callback=None):
#this function downloads video playlist as video(mp4)

    try:
        reset_vcancel_flag()
        
        ydl_opts_flat = {'quiet': True, 'extract_flat': True}
        with YoutubeDL(ydl_opts_flat) as ydl:
            info = ydl.extract_info(playlist_url, download=False)
        entries = info.get('entries', [])
        total_items = len(entries)
        playlist_title = info.get('title', 'unknown')
        
        download_folder = os.path.join(f"{get_default_audio_folder()}",f"{playlist_title}")
        os.makedirs(download_folder, exist_ok=True)
        fmt = "bestvideo+bestaudio/best" if quality == "best" else f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]"

        def download_single_video(i, entry):
            global vCANCEL_FLAG
            if vCANCEL_FLAG:
                raise Exception("Video playlist download cancelled")
            video_url = entry.get('webpage_url') or entry.get('url')
            if not video_url:
                return
            with YoutubeDL({'quiet': True}) as ydl:
                video_info = ydl.extract_info(video_url, download=False)
            title = video_info.get('title', 'Unknown Title')
            thumbnail = video_info.get('thumbnail', '')
            if progress_callback:
                progress_callback(title, thumbnail, i, total_items, playlist_title)
            ydl_opts = {
                'format': fmt,
                'merge_output_format': 'mp4',
                'outtmpl': os.path.join(download_folder, '%(title)s.%(ext)s'),
                'quiet': True,
                'progress_hooks': [
                    partial(vprogress_hook, status_callback=status_callback, item_index=i, total_items=total_items)
                ],
            }
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for i, entry in enumerate(entries, start=1):
                futures.append(executor.submit(download_single_video, i, entry))
            for future in concurrent.futures.as_completed(futures):
                future.result()
        return True
    except Exception as e:
        messagebox.showerror("Playlist Video Download Error", f"Failed to download playlist video: {str(e)}")
        return False


def search_videos(query, max_results=3):
    # Uses yt-dlp's built-in search capability.
    try:
        search_query = f"ytsearch{max_results}:{query}"
        with YoutubeDL({'quiet': True}) as ydl:
            results = ydl.extract_info(search_query, download=False)
        return results.get("entries", [])
    except Exception as e:
        print(f"Search error: {e}")
        return []
def get_available_qualities(url):
    try:
        ydl_opts = {'quiet': True, 'skip_download': True}
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        qualities = set()
        for fmt in info.get("formats", []):
            if fmt.get("vcodec") != "none":
                height = fmt.get("height")
                if height:
                    qualities.add(height)
        qualities = sorted(list(qualities), reverse=True)
        return [[str(q) for q in qualities], info]
    except Exception as e:
        print(f"Error fetching qualities: {e}")
        return []