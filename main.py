import sys
import os
import threading
import resources_rc
import requests
from io import BytesIO
from PIL import Image, ImageQt, ImageOps
from PySide6 import QtGui
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QTextEdit, QProgressBar, QFileDialog, QDialog,
                               QComboBox, QMessageBox, QScrollArea, QFrame)
from PySide6.QtGui import QPixmap, QIcon, QAction
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QSize, QRectF, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from functools import partial
import downloader
from PySide6.QtWebEngineWidgets import QWebEngineView
from downloader import (download_video, download_playlist,
                          download_video_file, download_playlist_video,
                          get_available_qualities, get_default_audio_folder, get_default_video_folder,
                          returnUrlInfo, returnAudPlayUrlInfo, set_audio_download_folder, set_video_download_folder,
                          acancel_download, vcancel_download, search_videos)

# Thread-Safe Error Dialog (converted multiline comment removed)
import tkinter.messagebox as tkmb
global Finished
Finished = False
def dummy_show_error(title, message):
    QTimer.singleShot(0, lambda: QMessageBox.critical(None, title, message))
tkmb.showerror = dummy_show_error

def rounded_pixmap(pixmap, radius=20, border_color="#010101", border_width=0):
    size = pixmap.size()
    rounded = QPixmap(size)
    rounded.fill(Qt.transparent)
    painter = QtGui.QPainter(rounded)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    path = QtGui.QPainterPath()
    rect = QRectF(0, 0, size.width(), size.height())
    path.addRoundedRect(rect, radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, pixmap)
    if border_width > 0:
        pen = QtGui.QPen(QtGui.QColor(border_color))
        pen.setWidth(border_width)
        painter.setPen(pen)
        painter.drawRoundedRect(rect.adjusted(border_width/2, border_width/2, -border_width/2, -border_width/2),
                                 radius, radius)
    painter.end()
    return rounded

class QualityDialog(QDialog):
    def __init__(self, qualities, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Video Quality")
        self.setStyleSheet("background-color: rgba(0, 0, 0, 200); " +
                           "color: #ffffff; " +
                           "border: 2px solid #0ef; " +
                           "border-radius: 10px;")
        self.selected_quality = None
        layout = QVBoxLayout()
        label = QLabel("Select Quality:")
        layout.addWidget(label)
        self.combo = QComboBox()
        self.combo.addItems(qualities)
        layout.addWidget(self.combo)
        button_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def accept(self):
        self.selected_quality = self.combo.currentText()
        super().accept()

    def get_selected_quality(self):
        return self.selected_quality

class SearchResultWidget(QWidget):
    def __init__(self, result, parent=None):
        super().__init__(parent)
        self.result = result
        self.video_url = result.get("webpage_url") or result.get("url")

        # Main layout for the widget
        layout = QHBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(5, 5, 5, 5)

        # Thumbnail
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setStyleSheet("background-color: transparent;")
        self.thumbnail_label.setFixedSize(120, 90)
        self.thumbnail_label.setScaledContents(True)
        layout.addWidget(self.thumbnail_label)

        # Duration
        title = result.get('title', 'No Title')
        sec = result.get('duration', '0')
        try:
            sec = int(sec)
        except:
            sec = 0
        hour = None
        minute = None
        if sec > 60:
            minute = int(sec / 60)
            sec = sec % 60
            if minute > 60:
                hour = int(minute / 60)
                minute = int(minute % 60)
        if hour is not None:
            length = f"{hour:02d}:{minute:02d}:{sec:02d}"
        elif minute is not None:
            length = f"{minute:02d}:{sec:02d}"
        else:
            length = f"00:{sec:02d}"
        self.time_label = QLabel(length)
        self.time_label.setStyleSheet("font-weight: bold;")
        self.time_label.setMaximumWidth(50)
        layout.addWidget(self.time_label)

        # Title
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.title_label)

        # Buttons
        self.audio_btn = QPushButton("Download Audio")
        self.video_btn = QPushButton("Download Video")
        self.watch_btn = QPushButton("Watch Video")
        
        # Style buttons
        button_style = "background-color:#0ef; color:#000000; padding: 5px;"
        self.audio_btn.setStyleSheet(button_style)
        self.video_btn.setStyleSheet(button_style)
        self.watch_btn.setStyleSheet(button_style)
        
        # Set button sizes
        self.audio_btn.setMaximumWidth(110)
        self.video_btn.setMaximumWidth(110)
        self.watch_btn.setMaximumWidth(110)

        # Add buttons to layout
        layout.addWidget(self.audio_btn)
        layout.addWidget(self.video_btn)
        layout.addWidget(self.watch_btn)

        # Load thumbnail
        thumbnail_url = result.get('thumbnail')
        if thumbnail_url:
            try:
                response = requests.get(thumbnail_url, timeout=10)
                response.raise_for_status()
                image_data = response.content
                image = Image.open(BytesIO(image_data))
                image = image.resize((120, 90), Image.LANCZOS)
                qt_image = ImageQt.ImageQt(image)
                pixmap = QPixmap.fromImage(qt_image)
                spixmap = rounded_pixmap(pixmap, radius=10, border_color="#303030", border_width=2)
                self.thumbnail_label.setPixmap(spixmap)
            except Exception as e:
                print("Thumbnail load error:", e)

        # Set a fixed height for the widget to ensure consistency
        self.setFixedHeight(110)

class VideoPlayerDialog(QDialog):
    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Watch Video")
        self.setMinimumSize(800, 500)

        layout = QVBoxLayout(self)

        # Create YouTube embed HTML
        video_id = self.get_youtube_id(url)
        if video_id:
            embed_html = f"""
            <html>
                <body style='margin:0'>
                    <iframe width="100%" height="100%"
                            src="https://www.youtube.com/embed/{video_id}"
                            frameborder="0" allowfullscreen>
                    </iframe>
                </body>
            </html>
            """
            # Create and add web view
            web_view = QWebEngineView()
            web_view.setHtml(embed_html)
            layout.addWidget(web_view)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("background-color:#0ef; color:#000000; padding: 5px;")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

    def get_youtube_id(self, url):
        import re
        patterns = [
            r'youtube\.com/watch\?v=([^&]+)',
            r'youtu\.be/([^?]+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

class SearchTab(QWidget):
    results_ready = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.results_ready.connect(self.display_results)

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Search bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search for videos on YouTube...")
        search_layout.addWidget(self.search_input)
        self.search_btn = QPushButton("Search")
        self.search_btn.setStyleSheet("background-color:#0ef; color:#000000; padding: 5px;")
        self.search_btn.clicked.connect(self.perform_search)
        search_layout.addWidget(self.search_btn)
        layout.addLayout(search_layout)

        # Scroll area for search results
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; }")
        self.results_widget = QWidget()
        self.results_layout = QVBoxLayout(self.results_widget)
        self.results_layout.setAlignment(Qt.AlignTop)
        self.results_layout.setSpacing(10)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_area.setWidget(self.results_widget)
        layout.addWidget(self.scroll_area)

        # Log text
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("background-color: transparent; border: 0px; padding: 5px;")
        self.log_text.setFixedHeight(400)  # Limit log height
        layout.addWidget(self.log_text)

    def perform_search(self):
        query = self.search_input.text().strip()
        if not query:
            QMessageBox.critical(self, "Error", "Please enter a search query")
            return
        self.log("Searching for: " + query)
        for i in reversed(range(self.results_layout.count())):
            widget = self.results_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)
        threading.Thread(target=self.search_thread, args=(query,), daemon=True).start()

    def search_thread(self, query):
        results = search_videos(query)
        self.results_ready.emit(results)

    @Slot(list)
    def display_results(self, results):
        if not results:
            self.log("No results found.")
            return
        for result in results:
            widget = SearchResultWidget(result)
            widget.audio_btn.clicked.connect(lambda checked, url=result.get("webpage_url"): self.download_audio(url))
            widget.video_btn.clicked.connect(lambda checked, url=result.get("webpage_url"): self.download_video(url))
            widget.watch_btn.clicked.connect(lambda checked, url=result.get("webpage_url"): self.show_video(url))
            self.results_layout.addWidget(widget)
        self.log(f"Found {len(results)} results.")

    def show_video(self, url):
        # Open video in a dialog instead of embedding it in the main layout
        dialog = VideoPlayerDialog(url, self)
        dialog.exec()

    def download_audio(self, url):
        self.log("Starting audio download for: " + url)
        threading.Thread(target=self.audio_download_thread, args=(url,), daemon=True).start()

    def audio_download_thread(self, url):
        isFromSearch=True
        success = downloader.download_video(url,isFromSearch, status_callback=lambda text: self.log(text))
        if success:
            self.log("Audio download completed!")
        else:
            self.log("Audio download failed!")

    def download_video(self, url):
        self.log("Fetching available qualities for: " + url)
        result = get_available_qualities(url)
        if result:
            qualities, info = result
        else:
            qualities, info = ([], {})
        quality = None
        if qualities:
            dialog = QualityDialog(qualities, self)
            if dialog.exec() == QDialog.Accepted:
                quality = dialog.get_selected_quality()
        if not quality:
            quality = "best"
        self.log("Selected quality: " + quality)
        threading.Thread(target=self.video_download_thread, args=(url, quality), daemon=True).start()

    def video_download_thread(self, url, quality):
        isFromSearch=True
        success = downloader.download_video_file(url,isFromSearch, quality=quality, status_callback=lambda text: self.log(text))
        if success:
            self.log("Video download completed!")
        else:
            self.log("Video download failed!")

    def log(self, message):
        self.log_text.append(message)
class DownloaderApp(QMainWindow):
    audio_status_signal = Signal(str)
    audiop_status_signal = Signal(str)
    video_status_signal = Signal(str)
    videop_status_signal = Signal(str)
    audio_image_signal = Signal(QPixmap)
    video_image_signal = Signal(QPixmap)
    audio_progress_finished_signal = Signal()
    video_progress_finished_signal = Signal()

    def __init__(self):
        super().__init__()
        self.bg_pixmap = QPixmap("1.jpg")
        self.setWindowTitle("Media Downloader")
        self.setMinimumSize(800, 600)
        self.showMaximized()
        self.setStyleSheet("QWidget { background-color: transparent; color: #ffffff; } " +
                           "QLineEdit { background-color: transparent; border: 1px solid #0ef; border-radius: 5px; padding: 2px; } " +
                           "QTextEdit, QComboBox, QScrollArea { background-color: transparent; border: 0px; border-radius: 5px; padding: 5px; } " +
                           "QTabWidget::pane { border: 0px; background: transparent; margin-top: 10px; } " +
                           "QTabBar::tab { background: transparent; color: #ffffff; padding: 8px; border-top-left-radius: 5px; border-top-right-radius: 5px; } " +
                           "QTabBar::tab:selected { background: #0ef; color: #000000; }")
        tkmb.showerror = lambda title, message: QTimer.singleShot(0, lambda: QMessageBox.critical(self, title, message))
        self.audio_download_thread = None
        self.video_download_thread = None
        self.setup_ui()
        self.audio_status_signal.connect(self.update_audio_status)
        self.audiop_status_signal.connect(self.update_audiop_status)
        self.video_status_signal.connect(self.update_video_status)
        self.videop_status_signal.connect(self.update_videop_status)
        self.audio_image_signal.connect(self.set_audio_image)
        self.video_image_signal.connect(self.set_video_image)
        self.audio_progress_finished_signal.connect(self.audio_progress_finished)
        self.video_progress_finished_signal.connect(self.video_progress_finished)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        if not self.bg_pixmap.isNull():
            scaled = self.bg_pixmap.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        super().paintEvent(event)

    def show_about(self):
        QMessageBox.information(
            self, "About",
            "Media Downloader"
            "with Preview, Cancel & History Features\n"
            "Paste the link, one click download from internet\n\n"
            "Basic Features:\n"
            " *It can download Youtube video ,Youtube audio \n"
            " *Search and download video/audio from youtube\n"
            " *Thousands of supported platforms, social media apps like   facebook,instagram,tiktok etc and many more platforms like soundcloud,Deezer\n\n"
            "Advanced Fearures:\n"
            " *Downloading playlist support\n"
            " *Downloading metadata with synced lyrics supported for single audio and   audio  playlist(useful for downloading yt music,soundcloud playlist etc..)\n"

            " *User can select quality before downloading videos\n"
            
        )

    def select_audio_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Audio Download Folder", get_default_audio_folder())
        if folder:
            set_audio_download_folder(folder)
            self.audio_folder_label.setText("Download Folder: " + folder)

    def select_video_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Video Download Folder", get_default_video_folder())
        if folder:
            set_video_download_folder(folder)
            self.video_folder_label.setText("Download Folder: " + folder)

    def choose_quality_dialog(self, qualities):
        dialog = QualityDialog(qualities, self)
        if dialog.exec() == QDialog.Accepted:
            return dialog.get_selected_quality()
        return None

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        self.audio_tab = QWidget()
        self.tabs.addTab(self.audio_tab, "Audio")
        self.setup_audio_tab(self.audio_tab)
        self.video_tab = QWidget()
        self.tabs.addTab(self.video_tab, "Video")
        self.setup_video_tab(self.video_tab)
        self.search_tab = SearchTab()
        self.tabs.addTab(self.search_tab, "Search")
        # Add About button as a corner widget on the top right
        about_button = QPushButton("?")
        about_button.setStyleSheet("background-color: transparent; color: #00FFFF; border: none;font-size:13pt;")
        about_button.clicked.connect(self.show_about)
        self.tabs.setCornerWidget(about_button, Qt.TopRightCorner)

    def setup_audio_tab(self, tab):
        audio_layout = QVBoxLayout(tab)
        audio_input_widget = QWidget()
        audio_input_layout = QVBoxLayout(audio_input_widget)
        title_label = QLabel("Audio Download")
        title_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        audio_input_layout.addWidget(title_label)
        url_widget = QWidget()
        url_layout = QHBoxLayout(url_widget)
        self.audio_url_entry = QLineEdit()
        self.audio_url_entry.setPlaceholderText("Enter Media URL")
        url_layout.addWidget(self.audio_url_entry)
        clear_audio_btn = QPushButton("Clear")
        clear_audio_btn.clicked.connect(lambda: self.audio_url_entry.clear())
        clear_audio_btn.setStyleSheet("background-color:#0ef;color:#8B0000")
        url_layout.addWidget(clear_audio_btn)
        audio_input_layout.addWidget(url_widget)
        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        preview_audio_btn = QPushButton("Preview")
        preview_audio_btn.clicked.connect(self.preview_audio)
        preview_audio_btn.setStyleSheet("background-color:#0ef;color:#000000")
        btn_layout.addWidget(preview_audio_btn)
        self.audio_download_btn = QPushButton("Download Audio")
        self.audio_download_btn.clicked.connect(self.start_audio_download)
        self.audio_download_btn.setStyleSheet("background-color:#0ef;color:#000000")
        btn_layout.addWidget(self.audio_download_btn)
        cancel_audio_btn = QPushButton("Cancel")
        cancel_audio_btn.clicked.connect(lambda: self.cancel_audio_download())
        cancel_audio_btn.setStyleSheet("background-color:#0ef;color:#8B0000")
        btn_layout.addWidget(cancel_audio_btn)
        select_audio_btn = QPushButton("Select Folder")
        select_audio_btn.clicked.connect(self.select_audio_folder)
        select_audio_btn.setStyleSheet("background-color:#0ef;color:#000000")
        btn_layout.addWidget(select_audio_btn)
        audio_input_layout.addWidget(btn_widget)
        audio_layout.addWidget(audio_input_widget)
        audio_progress_widget = QWidget()
        audio_progress_layout = QVBoxLayout(audio_progress_widget)
        self.audio_progress = QProgressBar()
        self.audio_progress.setMinimum(0)
        self.audio_progress.setMaximum(0)
        audio_progress_layout.addWidget(self.audio_progress)
        self.audio_folder_label = QLabel("Download Folder: " + get_default_audio_folder())
        audio_progress_layout.addWidget(self.audio_folder_label)
        self.audiop_status_label = QLabel("")
        self.audiop_status_label.setStyleSheet("font-size: 15pt; color: #ffffff;")
        audio_progress_layout.addWidget(self.audiop_status_label)
        self.audio_status_label = QLabel("")
        self.audio_status_label.setStyleSheet("font-size: 15pt; color: #ffffff;")
        audio_progress_layout.addWidget(self.audio_status_label)
        audio_layout.addWidget(audio_progress_widget)
        self.audio_history_text = QTextEdit()
        self.audio_history_text.setReadOnly(True)
        self.audio_history_text.setFixedSize(680, 270)
        self.audio_history_text.setStyleSheet("background-color: rgba(0, 0, 0, 100); border: 1px solid #303030; border-radius:10px;")
        self.aimage_label = QLabel()
        self.aimage_label.setAlignment(Qt.AlignCenter)
        self.aimage_label.setFixedSize(480, 270)
        self.aimage_label.setScaledContents(True)
        self.aimage_label.hide()
        self.audio_bottom_widget = QWidget()
        self.audio_bottom_layout = QHBoxLayout(self.audio_bottom_widget)
        self.audio_bottom_layout.addWidget(self.audio_history_text)
        self.audio_bottom_layout.addSpacing(10)
        self.audio_bottom_layout.addWidget(self.aimage_label)
        self.audio_bottom_layout.setAlignment(Qt.AlignCenter | Qt.AlignTop)
        audio_layout.addWidget(self.audio_bottom_widget)

    def setup_video_tab(self, tab):
        video_layout = QVBoxLayout(tab)
        video_input_widget = QWidget()
        video_input_layout = QVBoxLayout(video_input_widget)
        video_title_label = QLabel("Video Download")
        video_title_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        video_input_layout.addWidget(video_title_label)
        video_url_widget = QWidget()
        video_url_layout = QHBoxLayout(video_url_widget)
        self.video_url_entry = QLineEdit()
        self.video_url_entry.setPlaceholderText("Enter Media URL")
        video_url_layout.addWidget(self.video_url_entry)
        clear_video_btn = QPushButton("Clear")
        clear_video_btn.clicked.connect(lambda: self.video_url_entry.clear())
        clear_video_btn.setStyleSheet("background-color:#0ef;color:#8B0000")
        video_url_layout.addWidget(clear_video_btn)
        video_input_layout.addWidget(video_url_widget)
        quality_widget = QWidget()
        quality_layout = QHBoxLayout(quality_widget)
        quality_label = QLabel("Playlist Quality:")
        quality_layout.addWidget(quality_label)
        self.playlist_quality_combo = QComboBox()
        self.playlist_quality_combo.addItems(["best", "2160", "1440", "1080", "720", "480", "360", "240"])
        quality_layout.addWidget(self.playlist_quality_combo)
        preview_video_btn = QPushButton("Preview")
        preview_video_btn.setStyleSheet("background-color:#0ef;color:#000000")
        preview_video_btn.clicked.connect(self.preview_video)
        quality_layout.addWidget(preview_video_btn)
        self.video_download_btn = QPushButton("Download Video")
        self.video_download_btn.clicked.connect(self.start_video_download)
        self.video_download_btn.setStyleSheet("background-color:#0ef;color:#000000")
        quality_layout.addWidget(self.video_download_btn)
        cancel_video_btn = QPushButton("Cancel")
        cancel_video_btn.clicked.connect(lambda: self.cancel_video_download())
        cancel_video_btn.setStyleSheet("background-color:#0ef;color:#8B0000")
        quality_layout.addWidget(cancel_video_btn)
        select_video_btn = QPushButton("Select Folder")
        select_video_btn.clicked.connect(self.select_video_folder)
        select_video_btn.setStyleSheet("background-color:#0ef;color:#000000")
        quality_layout.addWidget(select_video_btn)
        video_input_layout.addWidget(quality_widget)
        video_layout.addWidget(video_input_widget)
        video_progress_widget = QWidget()
        video_progress_layout = QVBoxLayout(video_progress_widget)
        self.video_progress = QProgressBar()
        self.video_progress.setMinimum(0)
        self.video_progress.setMaximum(0)
        video_progress_layout.addWidget(self.video_progress)
        self.video_folder_label = QLabel("Download Folder: " + get_default_video_folder())
        video_progress_layout.addWidget(self.video_folder_label)
        self.videop_status_label = QLabel("")
        self.videop_status_label.setStyleSheet("font-size: 15pt; color: #ffffff;")
        video_progress_layout.addWidget(self.videop_status_label)
        self.video_status_label = QLabel("")
        self.video_status_label.setStyleSheet("font-size: 15pt; color: #ffffff;")
        video_progress_layout.addWidget(self.video_status_label)
        video_layout.addWidget(video_progress_widget)
        self.video_history_text = QTextEdit()
        self.video_history_text.setReadOnly(True)
        self.video_history_text.setFixedSize(680, 270)
        self.video_history_text.setStyleSheet("background-color: rgba(0, 0, 0, 100); border: 2px solid #303030; border-radius:10px;")
        self.vimage_label = QLabel()
        self.vimage_label.setAlignment(Qt.AlignCenter)
        self.vimage_label.setFixedSize(480, 270)
        self.vimage_label.setScaledContents(True)
        self.vimage_label.hide()
        self.video_bottom_widget = QWidget()
        self.video_bottom_layout = QHBoxLayout(self.video_bottom_widget)
        self.video_bottom_layout.addWidget(self.video_history_text)
        self.video_bottom_layout.addSpacing(10)
        self.video_bottom_layout.addWidget(self.vimage_label)
        self.video_bottom_layout.setAlignment(Qt.AlignCenter | Qt.AlignTop)
        video_layout.addWidget(self.video_bottom_widget)

    def log_audio(self, message):
        self.audio_history_text.append(message)

    def log_video(self, message):
        self.video_history_text.append(message)

    def preview_audio(self):
        url = self.audio_url_entry.text().strip()
        if not url:
            QMessageBox.critical(self, "Error", "Please enter a URL to preview audio info")
            return
        try:
            if "playlist" in url:
                info = returnAudPlayUrlInfo(url)
                title = info[0]
                thumbnail_url = info[2]
                self.audiop_status_signal.emit("Playlist: " + title)
                self.audio_status_signal.emit("Total Files: " + str(info[1]))
            else:
                info = returnUrlInfo(url)
                title = info.get('title', 'Unknown Title')
                thumbnail_url = info.get('thumbnail', '')
            self.log_audio("Preview: " + title)
            if thumbnail_url:
                response = requests.get(thumbnail_url, timeout=10)
                response.raise_for_status()
                image_data = response.content
                image = Image.open(BytesIO(image_data))
                resized_image = image.resize((480, 270), Image.LANCZOS)
                qt_image = ImageQt.ImageQt(resized_image)
                pixmap = QPixmap.fromImage(qt_image)
                spixmap = rounded_pixmap(pixmap, radius=10, border_color="#303030", border_width=2)
                self.aimage_label.setPixmap(spixmap)
                self.aimage_label.show()
            else:
                self.aimage_label.hide()
        except Exception as e:
            QMessageBox.critical(self, "Preview Error", str(e))

    def preview_video(self):
        url = self.video_url_entry.text().strip()
        if not url:
            QMessageBox.critical(self, "Error", "Please enter a URL to preview video info")
            return
        if not (url.startswith("http://") or url.startswith("https://")):
            QMessageBox.critical(self, "Error", "Please enter a valid URL to preview video info")
            return
        try:
            if "playlist" in url.lower():
                info = returnAudPlayUrlInfo(url)
                title = info[0]
                thumbnail_url = info[2]
                self.videop_status_signal.emit("Playlist: " + title)
                self.video_status_signal.emit("Total Files: " + str(info[1]))
                
            else:
                info = returnUrlInfo(url)
                title = info.get('title', 'Unknown Title')
                thumbnail_url = info.get('thumbnail', '')
                self.video_status_signal.emit(title)
                dialog = VideoPlayerDialog(url, self)
                dialog.exec()
            self.log_video("Preview: " + title)
            if thumbnail_url:
                response = requests.get(thumbnail_url, timeout=10)
                response.raise_for_status()
                image_data = response.content
                image = Image.open(BytesIO(image_data))
                resized_image = image.resize((480, 270), Image.LANCZOS)
                qt_image = ImageQt.ImageQt(resized_image)
                pixmap = QPixmap.fromImage(qt_image)
                spixmap = rounded_pixmap(pixmap, radius=10, border_color="#303030", border_width=2)
                self.vimage_label.setPixmap(spixmap)
                self.vimage_label.show()
            else:
                self.vimage_label.hide()
           
            
        except Exception as e:
            QMessageBox.critical(self, "Preview Error", str(e))

    def cancel_audio_download(self):
        try:
            acancel_download()
            self.log_audio("Cancelling Audio Download.")
        except Exception as e:
            QMessageBox.critical(self, "Cancel Error", str(e))

    def cancel_video_download(self):
        try:
            vcancel_download()
            self.log_video("Cancelling Video Download.")
        except Exception as e:
            QMessageBox.critical(self, "Cancel Error", str(e))

    def start_audio_download(self):
        url = self.audio_url_entry.text().strip()
        if not url:
            QMessageBox.critical(self, "Error", "Please enter a URL for audio")
            return
        self.audio_progress.setMaximum(0)
        self.audio_status_label.setText("Starting download...")
        self.log_audio("Download started.")
        self.aimage_label.clear()
        def audio_task():
            try:
                if "playlist" in url:
                    success = downloader.download_playlist(url, status_callback=lambda text: self.audio_status_signal.emit(text),
                                                            progress_callback_audio=self.playlist_audio_track)
                else:
                    info = returnUrlInfo(url)
                    if info:
                        status_text = "Downloading " + info.get('title','unknown title')
                        self.audio_status_signal.emit(status_text)
                        thumbnail_url = info.get('thumbnail', '')
                        if thumbnail_url:
                            response = requests.get(thumbnail_url, timeout=10)
                            response.raise_for_status()
                            image_data = response.content
                            image = Image.open(BytesIO(image_data))
                            resized_image = image.resize((480, 270), Image.LANCZOS)
                            qt_image = ImageQt.ImageQt(resized_image)
                            pixmap = QPixmap.fromImage(qt_image)
                            spixmap = rounded_pixmap(pixmap, radius=10, border_color="#303030", border_width=2)
                            self.audio_image_signal.emit(spixmap)
                    success = downloader.download_video(url, status_callback=lambda text: self.audio_status_signal.emit(text))
                if success:
                    
                    self.log_audio("Audio download completed!")
                else:
                    self.audio_status_label.setText("Download Cancelled")
                    self.audiop_status_label.setText("")
                    
                    if not Finished:
                        self.aimage_label.hide()
                        self.log_audio("Audio download failed!")
                    if Finished:
                        self.audio_status_label.setText("Download Completed")
                        self.audiop_status_label.setText("")

            except Exception as e:
                self.audio_status_signal.emit("Error: " + str(e))
                self.log_audio("Error: " + str(e))
            finally:
                self.audio_progress_finished_signal.emit()
        self.audio_download_thread = threading.Thread(target=audio_task, daemon=True)
        self.audio_download_thread.start()

    @Slot(str)
    def update_audio_status(self, text):
        self.audio_status_label.setText(text)

    @Slot(str)
    def update_audiop_status(self, text):
        self.audiop_status_label.setText(text)

    @Slot(QPixmap)
    def set_audio_image(self, pixmap):
        self.aimage_label.setPixmap(pixmap)
        self.aimage_label.show()

    @Slot()
    def audio_progress_finished(self):
        self.audio_progress.setMaximum(1)
        self.audio_progress.setValue(1)

    def playlist_audio_track(self, title, thumbnail, index, total, playlist_title):
        pstatus_text = "Playlist " + playlist_title + ": Total Files " + str(total)
        self.audiop_status_signal.emit(pstatus_text)
        status_text = "Downloading " + str(index) + "/" + str(total) + ": " + title
        self.audio_status_signal.emit(status_text)
        self.log_audio("Downloading: " + title + " (" + str(index) + "/" + str(total) + ")")
        global Finished 
        print(index/total)
        if index>=total:
          Finished = True
          print("yes u did it")
        else:
          Finished = False
        if thumbnail:
            try:
                response = requests.get(thumbnail, timeout=10)
                response.raise_for_status()
                image_data = response.content
                image = Image.open(BytesIO(image_data))
                resized_image = image.resize((480, 270), Image.LANCZOS)
                qt_image = ImageQt.ImageQt(resized_image)
                pixmap = QPixmap.fromImage(qt_image)
                spixmap = rounded_pixmap(pixmap, radius=10, border_color="#303030", border_width=2)
                self.audio_image_signal.emit(spixmap)
            except Exception as e:
                print("Failed to load thumbnail:", e)

    def start_video_download(self):
        url = self.video_url_entry.text().strip()
        if not url:
            QMessageBox.critical(self, "Error", "Please enter a URL for video")
            return
        if not (url.startswith("http://") or url.startswith("https://")):
            self.video_status_label.setText("Please Enter a valid URL or search from search bar.")
            self.videop_status_label.setText("")
            return
        self.vimage_label.clear()
        self.video_progress.setMaximum(0)
        self.video_status_label.setText("Starting download...")
        self.log_video("Download started.")
        if "playlist" in url.lower():
            def video_task_playlist():
                try:
                    quality = self.playlist_quality_combo.currentText()
                    success = downloader.download_playlist_video(url, quality=quality,
                                                                 status_callback=lambda text: self.video_status_signal.emit(text),
                                                                 progress_callback=self.update_download_progress)
                    if success:
                        self.log_video("Video download completed!")
                    else:
                        self.video_status_label.setText("Download Cancelled")
                        self.videop_status_label.setText("")
                        self.log_video("Video download failed!")
                except Exception as e:
                    self.video_status_signal.emit("Error: " + str(e))
                    self.log_video("Error: " + str(e))
                finally:
                    self.video_progress_finished_signal.emit()
            self.video_download_thread = threading.Thread(target=video_task_playlist, daemon=True)
            self.video_download_thread.start()
        else:
            result = downloader.get_available_qualities(url)
            if result:
                qualities, info = result
            else:
                qualities, info = ([], {})
            quality = None
            if qualities:
                quality = self.choose_quality_dialog(qualities)
            if not quality:
                quality = "best"
            self.log_video("Selected quality: " + quality)
            def video_task_single(quality):
                try:
                    status_text = "Downloading " + info.get('title','unknown title')
                    self.video_status_signal.emit(status_text)
                    thumbnail_url = info.get('thumbnail', '')
                    if thumbnail_url:
                        response = requests.get(thumbnail_url, timeout=10)
                        response.raise_for_status()
                        image_data = response.content
                        image = Image.open(BytesIO(image_data))
                        resized_image = image.resize((480, 270), Image.LANCZOS)
                        qt_image = ImageQt.ImageQt(resized_image)
                        pixmap = QPixmap.fromImage(qt_image)
                        spixmap = rounded_pixmap(pixmap, radius=10, border_color="#303030", border_width=2)
                        self.video_image_signal.emit(spixmap)
                    success = downloader.download_video_file(url, quality=quality,
                                                             status_callback=lambda text: self.video_status_signal.emit(text))
                    if success:
                        self.log_video("Video download completed!")
                    else:
                        self.video_status_label.setText("Cannot Download")
                        self.vimage_label.hide()
                        self.log_video("Video download failed!")
                except Exception as e:
                    self.video_status_signal.emit("Error: " + str(e))
                    self.log_video("Error: " + str(e))
                finally:
                    self.video_progress_finished_signal.emit()
            self.video_download_thread = threading.Thread(target=video_task_single, args=(quality,), daemon=True)
            self.video_download_thread.start()

    @Slot(str)
    def update_video_status(self, text):
        self.video_status_label.setText(text)

    @Slot(str)
    def update_videop_status(self, text):
        self.videop_status_label.setText(text)

    @Slot(QPixmap)
    def set_video_image(self, pixmap):
        self.vimage_label.setPixmap(pixmap)
        self.vimage_label.show()

    @Slot()
    def video_progress_finished(self):
        self.video_progress.setMaximum(1)
        self.video_progress.setValue(1)

    def update_download_progress(self, title, thumbnail, index, total, playlist_title):
        pstatus_text = "Playlist " + playlist_title + ": Total Files " + str(total)
        self.videop_status_signal.emit(pstatus_text)
        status_text = "Downloading " + str(index) + "/" + str(total) + ": " + title
        self.video_status_signal.emit(status_text)
        self.log_video("Downloading: " + title + " (" + str(index) + "/" + str(total) + ")")
        if thumbnail:
            try:
                response = requests.get(thumbnail, timeout=10)
                response.raise_for_status()
                image_data = response.content
                image = Image.open(BytesIO(image_data))
                resized_image = image.resize((480, 270), Image.LANCZOS)
                qt_image = ImageQt.ImageQt(resized_image)
                pixmap = QPixmap.fromImage(qt_image)
                spixmap = rounded_pixmap(pixmap, radius=10, border_color="#303030", border_width=2)
                self.video_image_signal.emit(spixmap)
            except Exception as e:
                print("Failed to load thumbnail:", e)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QtGui.QIcon(":/icons/faviconc5.ico"))
    window = DownloaderApp()
    window.show()
    sys.exit(app.exec())
