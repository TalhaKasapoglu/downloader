import os
import uuid
import glob
import subprocess
import yt_dlp
from .base import BaseDownloader
from .utils import find_cookies_file

class VideoDownloader(BaseDownloader):
    # Quality presets: maps quality label to yt-dlp format string
    # We don't restrict video ext to mp4 here because merge_output_format handles the final container.
    # This allows yt-dlp to pick the best quality stream and merge into mp4.
    QUALITY_FORMATS = {
        'best':  'bestvideo+bestaudio/best',
        '1080':  'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
        '720':   'bestvideo[height<=720]+bestaudio/best[height<=720]',
        '480':   'bestvideo[height<=480]+bestaudio/best[height<=480]',
    }

    def download(self, url: str, quality: str = 'best', progress_hook=None):

        file_uuid = str(uuid.uuid4())[:8]
        fmt = self.QUALITY_FORMATS.get(quality, self.QUALITY_FORMATS['best'])
        quality_label = quality if quality == 'best' else f"{quality}p"
        print(f"Downloading Video (MP4, {quality_label}) from: {url} (ID: {file_uuid})")
        print(f"  Format string: {fmt}")

        ydl_opts = {
            'format': fmt,
            'outtmpl': os.path.join(self.output_path, f'%(title)s-[{file_uuid}].%(ext)s'),
            'merge_output_format': 'mp4',
            'writethumbnail': True,
            'add_metadata': True,
            'sleep_interval': 2,
            'max_sleep_interval': 5,
            'sleep_interval_requests': 1,
            'extractor_retries': 5,
            'retry_sleep': 5,
            'extractor_args': {
                'youtube': {
                    'player_client': ['web', 'web_safari', 'android'],
                },
            },
            'postprocessors': [
                {'key': 'FFmpegMetadata', 'add_chapters': True},
            ],
        }

        cookies_path = find_cookies_file()
        if cookies_path:
            ydl_opts['cookiefile'] = cookies_path

        if progress_hook:
            ydl_opts['progress_hooks'] = [progress_hook]
        
        # No try/finally here, cleanup is manual
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # Manually embed thumbnail using FFmpeg
        self._embed_thumbnail_ffmpeg(file_uuid)
            
        return file_uuid
    
    def _embed_thumbnail_ffmpeg(self, file_uuid: str):
        # Find video file
        video_files = glob.glob(os.path.join(self.output_path, f"*{file_uuid}*.mp4"))
        if not video_files:
            print("Video file not found for embedding (might be mkv or other if merge failed, but we enforced mp4).")
            return
        video_path = video_files[0]

        # Find thumbnail file
        thumb_files = glob.glob(os.path.join(self.output_path, f"*{file_uuid}*"))
        thumb_path = None
        for f in thumb_files:
            if f.endswith(('.jpg', '.jpeg', '.png', '.webp')) and f != video_path:
                thumb_path = f
                break

        if not thumb_path:
            print("Thumbnail file not found for embedding.")
            return

        print(f"Embedding thumbnail using FFmpeg: {thumb_path} -> {video_path}")

        temp_output = video_path + ".temp.mp4"

        # Embed thumbnail as attached picture (cover art) in MP4:
        # - Map all video streams from input 0 first
        # - Map all audio streams from input 0
        # - Map thumbnail from input 1 as last video stream
        # - Main video streams: copy codec, set as default
        # - Audio streams: copy codec
        # - Thumbnail: convert to mjpeg, mark as attached_pic
        # - Use faststart for web streaming compatibility
        cmd = [
            'ffmpeg', '-y', '-loglevel', 'error',
            '-i', video_path,
            '-i', thumb_path,
            '-map', '0:v',          # All video streams first
            '-map', '0:a?',          # All audio streams (optional)
            '-map', '1:v:0',         # Thumbnail as last video stream
            '-c:v:0', 'copy',        # Copy main video stream(s)
            '-c:a', 'copy',          # Copy audio streams
            '-c:v:-1', 'mjpeg',      # Convert thumbnail (last video stream) to mjpeg
            '-disposition:v:0', 'default',
            '-disposition:v:-1', 'attached_pic',
            '-movflags', 'faststart',
            temp_output
        ]

        try:
            subprocess.run(cmd, check=True)
            # Replace original with temp
            os.replace(temp_output, video_path)
            print("Thumbnail embedded successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to embed thumbnail: {e}")
            if os.path.exists(temp_output):
                os.remove(temp_output)

    def cleanup_thumbnails(self, file_uuid: str):
        # Look for image files containing the UUID in the output directory
        extensions = ['*.jpg', '*.jpeg', '*.png', '*.webp']
        for ext in extensions:
            pattern = os.path.join(self.output_path, f"*{file_uuid}*{ext}")
            for file_path in glob.glob(pattern):
                try:
                    os.remove(file_path)
                    print(f"Cleaned up thumbnail: {file_path}")
                except OSError as e:
                    print(f"Failed to remove {file_path}: {e}")

    def finalize_filename(self, file_uuid: str):
        # Find video file
        pattern = os.path.join(self.output_path, f"*{file_uuid}*.mp4")
        files = glob.glob(pattern)
        if not files:
            # It implies something went wrong or file extension differs,
            # but we enforced 'mp4' in merge_output_format.
            return

        original_path = files[0]
        directory = os.path.dirname(original_path)
        filename = os.path.basename(original_path)
        
        # Remove the -[{file_uuid}] suffix
        # The pattern in outtmpl is: %(title)s-[{file_uuid}].%(ext)s
        uuid_tag = f"-[{file_uuid}]"
        new_filename = filename.replace(uuid_tag, "")
        
        new_path = os.path.join(directory, new_filename)
        
        if original_path == new_path:
            return

        try:
            if os.path.exists(new_path):
                print(f"File '{new_filename}' already exists. Overwriting...")
                os.remove(new_path)
            
            os.rename(original_path, new_path)
            print(f"Renamed: {filename} -> {new_filename}")
        except OSError as e:
            print(f"Error renaming final file: {e}")
