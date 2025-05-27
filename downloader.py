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

PATH_EXCLUDED_CHARACTERS = {"\\", "/"}

console = Console()
install(console=console)

_thread_pool: list[threading.Thread] = []


def _make_path_safe(file_name: str) -> str:
    return str(filter(lambda c: c not in PATH_EXCLUDED_CHARACTERS, file_name))


def _format_channel_directory(channel_name: str) -> str:
    return CHANNEL_DIRECTORY_TEMPLATE.format(channel_name=channel_name)


def _format_download_path(channel_name: str, video_title: str) -> str:
    video_title = _make_path_safe(video_title)

    return DOWNLOAD_PATH_TEMPLATE.format(
        channel_name=channel_name, video_title=video_title
    )


def _format_temporary_file_path(uuid: str) -> str:
    return TEMPORARY_FILE_PATH.format(uuid=uuid)


def ensure_channel_directory(channel_name: str) -> None:
    channel_directory = _format_channel_directory(channel_name)
    if os.path.exists(channel_directory):
        return
    os.makedirs(channel_directory, exist_ok=True)


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
    temp_file_path = _format_temporary_file_path(conversion_id)

    video_stream.download(temp_file_path, skip_existing=True, filename="video.mp4")
    audio_stream.download(temp_file_path, skip_existing=True, filename="audio.mp4")

    return temp_file_path


def _merge_streams(stream_path: str) -> str:
    output_path = f"{stream_path}/merged.mp4"
    cmd = [
        "ffmpeg",
        "-y",  # Overwrite output file without asking
        "-hide_banner",  # Hide FFmpeg banner
        "-loglevel",
        "error",  # Suppress logs except errors
        "-i",
        f"{stream_path}/video.mp4",  # Input video file
        "-i",
        f"{stream_path}/audio.mp4",  # Input audio file
        "-c",
        "copy",  # Copy both video and audio codecs (no re-encoding)
        "-map",
        "0:v:0",  # Select video stream from first input
        "-map",
        "1:a:0",  # Select audio stream from second input
        output_path,  # Output file
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

    output_file = _merge_streams(download_path)
    final_path = _format_download_path(
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


def _output_header() -> None:
    console.print(
        "Welcome to the YouTube Downloader!",
        style="bold underline blue",
        highlight=False,
    )


def _output_tutorial(download_path: str) -> None:
    console.print(
        "This tool allows you to quickly schedule downloads of YouTube videos.",
        style="dim",
        highlight=False,
    )
    console.print(
        "All videos will be downloaded in their highest quality and saved "
        f"in the current directory ([underline]{download_path}[/underline]).",
        style="dim",
        highlight=False,
    )
    console.print(
        "To get started, just paste in the URL of the YouTube video you want to download.",
        style="dim",
        highlight=False,
    )
    console.print("\n")


def _output_exit_message() -> None:
    console.log("Exiting the downloader. Goodbye!", style="bold red")


def _output_waiting_threads_message() -> None:
    console.log(
        "Waiting for all downloads to complete before exiting...",
        style="dim",
        highlight=False,
    )


def _output_ffmpeg_not_found() -> None:
    console.log(
        ":no_entry: FFmpeg is not installed or not found in your PATH.",
        style="bold red",
    )

    console.log(
        ":information_source: FFMPEG is required for merging audio and video streams. "
        "You can download it from https://ffmpeg.org/download.html",
        style="dim",
    )


if __name__ == "__main__":
    current_directory = os.getcwd()

    _output_header()
    _output_tutorial(current_directory)

    if not shutil.which("ffmpeg"):
        _output_ffmpeg_not_found()
        exit(1)

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
            _output_waiting_threads_message()
            for thread in _thread_pool:
                thread.join()

        _output_exit_message()
        exit(0)
