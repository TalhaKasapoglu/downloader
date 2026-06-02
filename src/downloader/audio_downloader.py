import os
import uuid
import glob
import subprocess
import yt_dlp
from .base import BaseDownloader
from .utils import find_cookies_file

class AudioDownloader(BaseDownloader):
    # Supported codecs with their extensions and ffmpeg codec names
    CODECS = {
        'aac':  {'ext': 'm4a', 'ffmpeg': 'aac'},
        'mp3':  {'ext': 'mp3', 'ffmpeg': 'libmp3lame'},
        'opus': {'ext': 'opus', 'ffmpeg': 'libopus'},
        'flac': {'ext': 'flac', 'ffmpeg': 'flac'},
        'vorbis': {'ext': 'ogg', 'ffmpeg': 'libvorbis'},
        'wav':  {'ext': 'wav', 'ffmpeg': 'pcm_s16le'},
    }

    # Quality presets: maps quality label to bitrate (kbps)
    QUALITY_BITRATES = {
        'best': '320',
        '320':  '320',
        '256':  '256',
        '192':  '192',
        '128':  '128',
        '96':   '96',
        '64':   '64',
    }

    def __init__(self, output_path: str):
        super().__init__(output_path)
        self._codec = 'aac'
        self._ext = 'm4a'

    def download(self, url: str, quality: str = 'best', codec: str = 'aac', progress_hook=None):

        file_uuid = str(uuid.uuid4())[:8]
        codec_info = self.CODECS.get(codec, self.CODECS['aac'])
        self._codec = codec
        self._ext = codec_info['ext']
        ext = self._ext
        ffmpeg_codec = codec_info['ffmpeg']
        bitrate = self.QUALITY_BITRATES.get(quality, self.QUALITY_BITRATES['best'])
        print(f"Downloading Audio ({codec.upper()}, {bitrate}kbps) from: {url} (ID: {file_uuid})")

        postprocessors = [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': ffmpeg_codec,
                'preferredquality': bitrate,
            },
            {'key': 'FFmpegMetadata', 'add_chapters': True},
        ]

        # FLAC and WAV are lossless, ignore bitrate
        if codec in ('flac', 'wav'):
            postprocessors[0]['preferredquality'] = '0'

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(self.output_path, f'%(title)s-[{file_uuid}].%(ext)s'),
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
            'postprocessors': postprocessors,
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
        self._embed_thumbnail_ffmpeg(file_uuid, ext=self._ext)
            
        return file_uuid
    
    def _embed_thumbnail_ffmpeg(self, file_uuid: str, ext: str = None):
        ext = ext or self._ext
        # Find audio file
        audio_files = glob.glob(os.path.join(self.output_path, f"*{file_uuid}*.{ext}"))
        if not audio_files:
            print(f"Audio file not found for embedding (*.{ext}).")
            return
        audio_path = audio_files[0]

        # Find thumbnail file
        thumb_files = glob.glob(os.path.join(self.output_path, f"*{file_uuid}*"))
        thumb_path = None
        for f in thumb_files:
            if f.endswith(('.jpg', '.jpeg', '.png', '.webp')) and f != audio_path:
                thumb_path = f
                break

        if not thumb_path:
            print("Thumbnail file not found for embedding.")
            return

        print(f"Embedding thumbnail using FFmpeg: {thumb_path} -> {audio_path}")

        temp_output = audio_path + f".temp.{ext}"

        # For FLAC/WAV, thumbnail embedding is not well supported, skip
        if ext in ('flac', 'wav'):
            print(f"Thumbnail embedding skipped for {ext.upper()} format.")
            return

        # ffmpeg -i audio -i thumb -map 0 -map 1 -c copy -c:v:1 mjpeg -disposition:v:1 attached_pic out
        cmd = [
            'ffmpeg', '-y', '-loglevel', 'error',
            '-i', audio_path,
            '-i', thumb_path,
            '-map', '0', '-map', '1',
            '-c:a', 'copy',
            '-c:v', 'mjpeg',
            '-disposition:v:0', 'attached_pic',
            temp_output
        ]

        try:
            subprocess.run(cmd, check=True)
            os.replace(temp_output, audio_path)
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
        # Find audio file (try known extensions)
        extensions = [self._ext, 'm4a', 'mp3', 'opus', 'flac', 'ogg', 'wav']
        original_path = None
        for ext in extensions:
            files = glob.glob(os.path.join(self.output_path, f"*{file_uuid}*.{ext}"))
            if files:
                original_path = files[0]
                break
        if not original_path:
            return
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
