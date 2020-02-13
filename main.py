#!/usr/bin/env python3

from __future__ import annotations
from asyncio import run as asyncio_run
from datetime import datetime
from tempfile import NamedTemporaryFile
from subprocess import call as subprocess_call
from urllib.parse import urlparse
from pathlib import PurePath

from aiohttp import ClientSession
from terminal_utils.Progressor import Progressor

from svtplay_downloader.extraction import get_streams_from_video_url


async def download_from_video_url(video_url: str):

    progressor = Progressor()

    def make_per_downloaded_segment_callback():
        num_segments_downloaded = 0

        def wrapped_per_downloaded_segment_callback(_: int, num_total: int, __: str):
            nonlocal num_segments_downloaded
            num_segments_downloaded += 1
            progressor.print_progress(iteration=num_segments_downloaded, total=num_total)

        return wrapped_per_downloaded_segment_callback

    async with ClientSession() as session:
        video_streams, audio_streams, _ = await get_streams_from_video_url(video_url=video_url, session=session)

        video_streams.sort(key=lambda video_stream: video_stream.resolution, reverse=True)

        video_data = await video_streams[0].download(
            session=session,
            per_downloaded_segment_callback=make_per_downloaded_segment_callback()
        )
        audio_data = await audio_streams[0].download(
            session=session,
            per_downloaded_segment_callback=make_per_downloaded_segment_callback()
        )

    with NamedTemporaryFile() as video_file, NamedTemporaryFile() as audio_file:
        video_file.write(video_data)
        audio_file.write(audio_data)

        subprocess_call(
            ['ffmpeg', '-i', video_file.name, '-i', audio_file.name, '-c', 'copy', f'{PurePath(urlparse(video_url).path).name}.mp4']
        )


async def main():
    d1 = datetime.now()
    await download_from_video_url('https://www.svtplay.se/video/25352127/pa-sparet/pa-sparet-sasong-30-avsnitt-9')
    print(datetime.now() - d1)


if __name__ == '__main__':
    asyncio_run(main())
