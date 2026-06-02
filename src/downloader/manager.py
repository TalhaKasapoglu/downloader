from .video_downloader import VideoDownloader
from .audio_downloader import AudioDownloader

class DownloadManager:
    def __init__(self, output_path: str):
        self.output_path = output_path

    def download(self, url: str, format_type: str, quality: str = 'best', codec: str = 'aac', progress_hook=None):
        if format_type == 'video':
            downloader = VideoDownloader(self.output_path)
            uuid = downloader.download(url, quality=quality, progress_hook=progress_hook)
        elif format_type == 'audio':
            downloader = AudioDownloader(self.output_path)
            uuid = downloader.download(url, quality=quality, codec=codec, progress_hook=progress_hook)
        else:
            raise ValueError("Invalid format type. Choose 'video' or 'audio'.")

        return downloader, uuid
