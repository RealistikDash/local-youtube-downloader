from __future__ import annotations

import sys
import os
import uuid
import shutil
import threading
import subprocess

from rich.console import Console
from rich.traceback import install
from pytubefix import YouTube
from pytubefix import Channel
from pytubefix import StreamQuery
from pytubefix import Stream

DOWNLOAD_PATH_TEMPLATE = "./{channel_name}/{video_title}.mp4"
CHANNEL_DIRECTORY_TEMPLATE = "./{channel_name}/"
TEMPORARY_FILE_PATH = "./tmp_{uuid}/"

console = Console()
install(console=console)

_thread_pool: list[threading.Thread] = []


def ensure_channel_directory(channel_name: str) -> None:
    if os.path.exists(CHANNEL_DIRECTORY_TEMPLATE.format(channel_name=channel_name)):
        return
    os.makedirs(
        CHANNEL_DIRECTORY_TEMPLATE.format(channel_name=channel_name), exist_ok=True
    )


def _select_audio_video_stream(streams: StreamQuery) -> tuple[Stream, Stream] | None:
    video_stream = (
        streams.filter(adaptive=True, file_extension="mp4", only_video=True)
        .order_by("resolution")
        .last()
    )
    audio_stream = (
        streams.filter(adaptive=True, file_extension="mp4", only_audio=True)
        .order_by("abr")
        .last()
    )

    if not video_stream or not audio_stream:
        return None

    return video_stream, audio_stream


def _handle_stream_download(video_stream: Stream, audio_stream: Stream) -> str:
    conversion_id = uuid.uuid4().hex
    temp_file_path = TEMPORARY_FILE_PATH.format(uuid=conversion_id)

    video_stream.download(temp_file_path, skip_existing=True, filename="video.mp4")
    audio_stream.download(temp_file_path, skip_existing=True, filename="audio.mp4")

    return temp_file_path


def _merge_streams(stream_path: str) -> str:
    output_path = f"{stream_path}/merged.mp4"
    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output file without asking
        "-hide_banner",  # Hide FFmpeg banner
        "-loglevel", "error",  # Suppress logs except errors
        "-i", f"{stream_path}/video.mp4",  # Input video file
        "-i", f"{stream_path}/audio.mp4",  # Input audio file
        "-c", "copy",  # Copy both video and audio codecs (no re-encoding)
        "-map", "0:v:0",  # Select video stream from first input
        "-map", "1:a:0",  # Select audio stream from second input
        output_path  # Output file
    ]
    subprocess.run(cmd, check=True)
    return output_path


def _cleanup_temp_files(stream_path: str) -> None:
    shutil.rmtree(stream_path, ignore_errors=True)


def download_video(video_url: str) -> None:
    video = YouTube(video_url)

    try:
        video.check_availability()
    except Exception as e:
        console.log(f":no_entry: Video {video_url!r} is not available: {e!r}")
        return

    selected_streams = _select_audio_video_stream(video.streams)
    if not selected_streams:
        console.log(f":no_entry: No suitable stream found for {video.title!r}.")
        return

    video_stream, audio_stream = selected_streams

    channel = Channel(video.channel_url)
    channel_name = channel.channel_name

    console.log(f":arrow_forward: Downloading {video.title!r} from {channel_name!r}...")

    download_path = _handle_stream_download(video_stream, audio_stream)

    console.log(
        f":hourglass_flowing_sand: Merging audio and video streams for {video.title!r}..."
    )
    output_file = _merge_streams(download_path)
    final_path = DOWNLOAD_PATH_TEMPLATE.format(
        channel_name=channel_name, video_title=video.title
    )

    ensure_channel_directory(channel_name)
    shutil.move(output_file, final_path)

    _cleanup_temp_files(download_path)

    console.log(
        f":white_check_mark: Successfully downloaded {video.title!r} by {channel_name!r}.",
    )


def schedule_download(video_url: str) -> None:
    schedule_thread = threading.Thread(
        target=download_video, args=(video_url,), daemon=False
    )
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
        "All videos will be downloaded in their highest quality and saved "
        f"in the current directory ([underline]{current_directory}[/underline]).",
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
                raise KeyboardInterrupt  # LOL

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
