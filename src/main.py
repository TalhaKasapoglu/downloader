import os
import sys
import time
import threading
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor, Future
from downloader.manager import DownloadManager
from downloader.history import DownloadHistory
from downloader.utils import find_cookies_file
from downloader.config import (
    DEFAULT_MAX_CONCURRENT_DOWNLOADS,
    DELAY_BETWEEN_DOWNLOADS,
    VIDEO_QUALITY_LABELS_CLI,
    AUDIO_QUALITY_LABELS_CLI,
    AUDIO_CODEC_LABELS_CLI,
)

def download_single(manager: DownloadManager, history: DownloadHistory, url: str, format_type: str, index: int, quality: str = 'best', codec: str = 'aac'):
    """Download a single URL and handle cleanup/finalization."""
    try:
        print(f"\n[{index}] Starting: {url}")
        downloader, file_uuid = manager.download(url, format_type, quality=quality, codec=codec)

        # Cleanup thumbnails
        downloader.cleanup_thumbnails(file_uuid)

        # Rename final file (remove UUID)
        downloader.finalize_filename(file_uuid)

        history.add(url=url, format_type=format_type, success=True, codec=codec, quality=quality, output_path=manager.output_path)
        print(f"[{index}] Completed: {url}")
        return (index, url, True, None)
    except Exception as e:
        history.add(url=url, format_type=format_type, success=False, codec=codec, quality=quality, error=str(e), output_path=manager.output_path)
        print(f"[{index}] Failed: {url} - {e}")
        return (index, url, False, str(e))

def main():
    print("=== Media Downloader ===")

    # 1. Get Download Path
    print("\nPlease enter the download path (leave empty for './downloads'):")
    download_path = input("> ").strip()
    if not download_path:
        download_path = "./downloads"

    # Create directory if it doesn't exist
    if not os.path.exists(download_path):
        try:
            os.makedirs(download_path)
            print(f"Created directory: {download_path}")
        except OSError as e:
            print(f"Error creating directory: {e}")
            return

    # 2. Get Concurrent Downloads
    print(f"\nMax concurrent downloads (default: {DEFAULT_MAX_CONCURRENT_DOWNLOADS}):")
    conc_input = input("> ").strip()
    try:
        max_concurrent = int(conc_input) if conc_input else DEFAULT_MAX_CONCURRENT_DOWNLOADS
        if max_concurrent < 1:
            max_concurrent = DEFAULT_MAX_CONCURRENT_DOWNLOADS
    except ValueError:
        max_concurrent = DEFAULT_MAX_CONCURRENT_DOWNLOADS
    print(f"Using {max_concurrent} concurrent download(s)")

    # 3. Get Media Type
    print("\nSelect format:")
    print("1. Video (MP4)")
    print("2. Audio")
    choice = input("Enter choice (1 or 2): ").strip()

    format_type = 'video' if choice == '1' else 'audio'
    if choice not in ['1', '2']:
        print("Invalid choice, defaulting to Video.")
        format_type = 'video'

    # 3b. Get Video Quality
    quality = 'best'
    if format_type == 'video':
        print("\nSelect video quality:")
        print("1. Best (highest available)")
        print("2. 1080p")
        print("3. 720p")
        print("4. 480p")
        q_choice = input("Enter choice (1-4): ").strip()

        quality = VIDEO_QUALITY_LABELS_CLI.get(q_choice, 'best')
        if q_choice not in VIDEO_QUALITY_LABELS_CLI:
            print("Invalid choice, defaulting to Best quality.")

    # 3c. Get Audio Codec + Quality
    codec = 'aac'
    if format_type == 'audio':
        print("\nSelect audio codec:")
        print("1. AAC (m4a)")
        print("2. MP3")
        print("3. OPUS")
        print("4. FLAC (lossless)")
        print("5. Vorbis (ogg)")
        c_choice = input("Enter choice (1-5): ").strip()

        codec = AUDIO_CODEC_LABELS_CLI.get(c_choice, 'aac')
        if c_choice not in AUDIO_CODEC_LABELS_CLI:
            print("Invalid choice, defaulting to AAC.")

        print("\nSelect audio quality (bitrate):")
        print("1. Best (320kbps)")
        print("2. 256kbps")
        print("3. 192kbps")
        print("4. 128kbps")
        print("5. 96kbps")
        print("6. 64kbps")
        aq_choice = input("Enter choice (1-6): ").strip()

        quality = AUDIO_QUALITY_LABELS_CLI.get(aq_choice, 'best')
        if aq_choice not in AUDIO_QUALITY_LABELS_CLI:
            print("Invalid choice, defaulting to Best quality.")

    # 3d. Cookies status
    cookies_path = find_cookies_file()
    if cookies_path:
        print(f"\n✅ cookies.txt found — YouTube login cookies active")
    else:
        print(f"\n⚠️  No cookies.txt found in project root")
        print("    YouTube may require login. Place a cookies.txt file next to run.py")
        print("    Use browser extension like 'Get cookies.txt LOCALLY' to export.")

    # 4. Get URLs (space-separated)
    print("\nEnter URL(s) to download (separate multiple URLs with spaces):")
    url_input = input("> ").strip()
    if not url_input:
        print("Error: URL cannot be empty.")
        return

    urls = url_input.split()
    url_count = len(urls)
    print(f"\nFound {url_count} URL(s) to download.")

    # 5. Queue-based download system
    manager = DownloadManager(os.path.abspath(download_path))
    history = DownloadHistory()

    # Show stats
    stats = history.get_stats()
    if stats["total"] > 0:
        print(f"\n📊 History: {stats['total']} total  ·  ✅ {stats['successful']} successful  ·  ❌ {stats['failed']} failed")

    # Create a queue with all URLs
    url_queue = Queue()
    for i, url in enumerate(urls):
        url_queue.put((i + 1, url))

    results = []
    results_lock = threading.Lock()

    def worker():
        """Worker that pulls URLs from queue and downloads them."""
        while True:
            try:
                # Get next URL from queue (non-blocking)
                index, url = url_queue.get_nowait()
            except Empty:
                # Queue is empty, worker exits
                break

            try:
                result = download_single(manager, history, url, format_type, index, quality=quality, codec=codec)
                with results_lock:
                    results.append(result)

                # Add delay between downloads to avoid rate limiting
                if not url_queue.empty():
                    print(f"Waiting {DELAY_BETWEEN_DOWNLOADS}s before next download...")
                    time.sleep(DELAY_BETWEEN_DOWNLOADS)
            finally:
                url_queue.task_done()

    # Start workers
    threads = []
    num_workers = min(max_concurrent, url_count)

    print(f"\nStarting {num_workers} download worker(s)...")
    
    for _ in range(num_workers):
        t = threading.Thread(target=worker)
        t.start()
        threads.append(t)
    
    # Wait for all workers to complete
    for t in threads:
        t.join()
    
    # 5. Summary
    print("\n" + "="*50)
    print("DOWNLOAD SUMMARY")
    print("="*50)
    
    successful = [r for r in results if r[2]]
    failed = [r for r in results if not r[2]]
    
    print(f"Total: {len(results)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failed)}")
    
    if failed:
        print("\nFailed downloads:")
        for idx, url, _, error in failed:
            print(f"  [{idx}] {url}: {error}")
    
    print("\nAll operations completed!")

if __name__ == "__main__":
    main()
