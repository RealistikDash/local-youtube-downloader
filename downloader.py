from __future__ import annotations

import os
import threading

from rich.console import Console
from rich.traceback import install
from pytubefix import YouTube
from pytubefix import Channel

DOWNLOAD_PATH_TEMPLATE = "./{channel_name}/{video_title}.mp4"
CHANNEL_DIRECTORY_TEMPLATE = "./{channel_name}/"

console = Console()
install(console=console)

_thread_pool: list[threading.Thread] = []


def ensure_channel_directory(channel_name: str) -> None:
    if os.path.exists(CHANNEL_DIRECTORY_TEMPLATE.format(channel_name=channel_name)):
        return
    os.makedirs(CHANNEL_DIRECTORY_TEMPLATE.format(channel_name=channel_name), exist_ok=True)


def download_video(video_url: str) -> None:
    video = YouTube(video_url)

    try:
        video.check_availability()
    except Exception as e:
        console.log(f":no_entry: Video {video_url!r} is not available: {e!r}")
        return


    video_title = video.title

    def video_completed_cb(*_) -> None:
        console.log(f":white_check_mark: Downloaded {video_title!r} successfully!")

    video.register_on_complete_callback(video_completed_cb)
    stream = video.streams.filter(progressive=True, file_extension="mp4").first()
    if not stream:
        console.log(f":no_entry: No suitable stream found for {video_title!r}.")
        return
    
    channel = Channel(video.channel_url)
    channel_name = channel.channel_name
    ensure_channel_directory(channel_name)

    console.log(f":arrow_forward: Downloading {video_title!r} from {channel_name!r}...")

    stream.download(CHANNEL_DIRECTORY_TEMPLATE.format(channel_name=channel_name))


def schedule_download(video_url: str) -> None:
    schedule_thread = threading.Thread(target=download_video, args=(video_url,), daemon=False)
    schedule_thread.start()
    _thread_pool.append(schedule_thread)


if __name__ == "__main__":
    console.print(
        "Welcome to the YouTube Downloader!",
        style="bold underline blue",
        highlight=False,
    )
    console.print(
        "This tool allows you to quickly schedule downloads of YouTube videos.",
        style="dim",
        highlight=False,
    )
    current_directory = os.getcwd()
    console.print(
        f"All videos will be downloaded in their highest quality and saved in the current directory ([underline]{current_directory}[/underline]).",
        style="dim",
        highlight=False,
    )
    console.print(
        "To get started, just paste in the URL of the YouTube video you want to download.",
        style="dim",
        highlight=False,
    )
    console.print("\n")

    try:
        while True:
            video_url = console.input("YouTube > ").strip()
            if not video_url:
                continue
            if video_url.lower() in ("exit", "quit", "q"):
                raise KeyboardInterrupt # LOL
            
            schedule_download(video_url)
    except KeyboardInterrupt:
        if _thread_pool:
            console.log(
                "Waiting for all downloads to complete before exiting...",
                style="dim",
                highlight=False,
            )
            for thread in _thread_pool:
                thread.join()
        
        console.log("Exiting the downloader. Goodbye!", style="bold red")
        exit(0)
    
