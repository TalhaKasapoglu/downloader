from abc import ABC, abstractmethod

class BaseDownloader(ABC):
    def __init__(self, output_path: str):
        self.output_path = output_path

    @abstractmethod
    def download(self, url: str) -> str:
        pass

    @abstractmethod
    def cleanup_thumbnails(self, file_uuid: str):
        pass

    @abstractmethod
    def finalize_filename(self, file_uuid: str):
        pass
