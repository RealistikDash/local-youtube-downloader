# Local YouTube Downloader
A tool to quickly download YouTube videos locally and organise them by channel name. 
<img width="906" alt="image" src="https://github.com/user-attachments/assets/ab168efb-7a6a-4f32-a279-0100ca303224" />



### Rationale
I wanted to watch YouTube videos on a 14 hour flight. There is no tool available (to my limited knowledge) that automatically downloads a YouTube video and organises it how I like it.

### How it works/how to use it?
- Open the program. A new console window should appear.
- Paste any YouTube video link.
- A video download will be scheduled. You will be able to schedule more videos in this time.
- The video will be downloaded in the highest quality available and located in `./<channel_name>/<video_title>`
- Et voila!

Note that to achieve the best quality, **FFMPEG** is required to combine the audio and video streams together (YouTube only offers combined ones for qualities under 360p).
