import os
import uuid
import glob
import base64
import struct
import subprocess
import yt_dlp
from .base import BaseDownloader
from .utils import find_cookies_file

class AudioDownloader(BaseDownloader):
    # Supported codecs with their file extensions and yt-dlp audio format names.
    # 'format' is passed to yt-dlp's FFmpegExtractAudio as preferredcodec.
    # yt-dlp expects a format name (e.g. 'opus'), not the raw FFmpeg encoder
    # name (e.g. 'libopus') — using the latter raises KeyError: 'libopus'.
    CODECS = {
        'aac':    {'ext': 'm4a',  'format': 'aac'},
        'mp3':    {'ext': 'mp3',  'format': 'mp3'},
        'opus':   {'ext': 'opus', 'format': 'opus'},
        'flac':   {'ext': 'flac', 'format': 'flac'},
        'vorbis': {'ext': 'ogg',  'format': 'vorbis'},
        'wav':    {'ext': 'wav',  'format': 'wav'},
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
        ydl_format = codec_info['format']
        bitrate = self.QUALITY_BITRATES.get(quality, self.QUALITY_BITRATES['best'])
        print(f"Downloading Audio ({codec.upper()}, {bitrate}kbps) from: {url} (ID: {file_uuid})")

        postprocessors = [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': ydl_format,
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

        # Ogg containers (.opus/.ogg) cannot store an attached JPEG stream, but
        # they support the METADATA_BLOCK_PICTURE Vorbis comment instead.
        if ext in ('opus', 'ogg'):
            self._embed_ogg_cover(audio_path, thumb_path, ext)
            return

        # FLAC/WAV have limited/unsupported thumbnail embedding
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

    @staticmethod
    def _picture_block_base64(thumb_path: str) -> str:
        """Build a base64 FLAC picture block for METADATA_BLOCK_PICTURE.

        Ogg/Opus cover art is stored as a Vorbis comment, not as an attached
        picture stream. The comment value is a base64-encoded FLAC picture
        metadata block (type 3 = front cover, image/jpeg).
        """
        dims = subprocess.check_output(
            [
                'ffprobe', '-v', 'error', '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height',
                '-of', 'csv=p=0:s=x', thumb_path,
            ],
            text=True,
        ).strip()
        width, height = (int(v) for v in dims.split('x')[:2])

        # WebP/PNG covers are converted to JPEG for maximum player support.
        jpeg = subprocess.check_output(
            [
                'ffmpeg', '-v', 'error', '-i', thumb_path,
                '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'mjpeg', '-',
            ],
            stderr=subprocess.PIPE,
        )

        be32 = lambda value: struct.pack('>I', value)
        mime = b'image/jpeg'
        block = (
            be32(3)                  # picture type: front cover
            + be32(len(mime)) + mime
            + be32(0)                # empty description
            + be32(width) + be32(height)
            + be32(24)               # bits per pixel
            + be32(0)                # number of colors (0 = unspecified)
            + be32(len(jpeg)) + jpeg
        )
        return base64.b64encode(block).decode('ascii')

    def _embed_ogg_cover(self, audio_path: str, thumb_path: str, ext: str):
        """Embed cover art into .opus/.ogg via METADATA_BLOCK_PICTURE tag."""
        temp_output = audio_path + f".temp.{ext}"
        try:
            picture = self._picture_block_base64(thumb_path)
            cmd = [
                'ffmpeg', '-y', '-loglevel', 'error',
                '-i', audio_path,
                '-c:a', 'copy',
                '-metadata:s:a:0', f'METADATA_BLOCK_PICTURE={picture}',
                temp_output,
            ]
            subprocess.run(cmd, check=True)
            os.replace(temp_output, audio_path)
            print("Thumbnail embedded successfully (METADATA_BLOCK_PICTURE).")
        except (subprocess.CalledProcessError, OSError, ValueError) as e:
            print(f"Failed to embed thumbnail: {e}")
            if os.path.exists(temp_output):
                os.remove(temp_output)

    def cleanup_thumbnails(self, file_uuid: str):
        """Remove every temporary file for this download except the audio."""
        for file_path in glob.glob(os.path.join(self.output_path, f"*{file_uuid}*")):
            # Keep only the final audio file (title-[uuid].ext); remove
            # .webp/.jpg/.mp4/.part/.temp.* files and any other leftovers.
            if file_path.endswith(f"-[{file_uuid}].{self._ext}"):
                continue
            try:
                os.remove(file_path)
                print(f"Cleaned up temporary file: {file_path}")
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
