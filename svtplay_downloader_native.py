#!/usr/bin/env -S python -u

from asyncio import run as asyncio_run
from json import dumps as json_dumps, loads as json_loads
from sys import stdin, stdout, exit
from struct import unpack as struct_unpack, pack as struct_pack
from tempfile import NamedTemporaryFile
from subprocess import call as subprocess_call
from pathlib import PurePath
from urllib.parse import urlparse
from time import time
from typing import Optional
from logging import getLogger, FileHandler

from aiohttp import ClientSession

from svtplay_downloader.extraction import get_streams_from_video_url


LOG = getLogger(__name__)
NUM_MESSAGE_LENGTH_SPECIFIER_BYTES = 4


def make_outgoing_message_bytes(message: str) -> bytes:
    content_bytes: bytes = message.encode(encoding='utf-8')
    return struct_pack('=I', len(content_bytes)) + content_bytes


# TODO: Return whatever `write` returns?
def write_message_bytes(message_bytes: bytes) -> None:
    stdout.buffer.write(message_bytes)
    stdout.buffer.flush()


def write_message(message: str) -> None:
    return write_message_bytes(message_bytes=make_outgoing_message_bytes(message=message))


async def download_from_video_url(video_url: str):

    start_time: Optional[float] = None
    overall_num_bytes_downloaded = 0

    def make_per_downloaded_segment_callback(media_type: str):
        num_segments_downloaded = 0
        num_bytes_downloaded = 0

        def wrapped_per_downloaded_segment_callback(_: int, total_num_segments: int, __: str, segment_byte_size: int):
            nonlocal start_time, overall_num_bytes_downloaded, num_segments_downloaded, num_bytes_downloaded
            num_segments_downloaded += 1
            num_bytes_downloaded += segment_byte_size
            overall_num_bytes_downloaded += segment_byte_size

            write_message(
                json_dumps({
                    'progress': {
                        'num_segments_downloaded': num_segments_downloaded,
                        'num_bytes_downloaded': num_bytes_downloaded,
                        'overall_num_bytes_downloaded': overall_num_bytes_downloaded,
                        'total_num_segments': total_num_segments,
                        'elapsed_seconds': time() - start_time,
                        'media_type': media_type
                    }
                })
            )

        return wrapped_per_downloaded_segment_callback

    async with ClientSession() as session:
        start_time = time()
        video_streams, audio_streams, _ = await get_streams_from_video_url(video_url=video_url, session=session)
        video_streams.sort(key=lambda video_stream: video_stream.resolution, reverse=True)

        video_data = await video_streams[0].download(
            session=session,
            per_downloaded_segment_callback=make_per_downloaded_segment_callback(media_type='video')
        )
        audio_data = await audio_streams[0].download(
            session=session,
            per_downloaded_segment_callback=make_per_downloaded_segment_callback(media_type='audio')
        )

    with NamedTemporaryFile() as video_file, NamedTemporaryFile() as audio_file:
        video_file.write(video_data)
        audio_file.write(audio_data)

        subprocess_call(
            ['ffmpeg', '-i', video_file.name, '-i', audio_file.name, '-c', 'copy', f'{PurePath(urlparse(video_url).path).name}.mp4']
        )


async def main():
    LOG.addHandler(hdlr=FileHandler(filename='svtplay_downloader_native.log'))

    incoming_message = json_loads(
        stdin.buffer.read(
            struct_unpack('=I', stdin.buffer.read(NUM_MESSAGE_LENGTH_SPECIFIER_BYTES))[0]
        ).decode(encoding='utf-8')
    )

    if not isinstance(incoming_message, dict):
        LOG.error(incoming_message)
        error_text = f'The input was not deserialized into a `dict`, rather a {type(incoming_message)}.'
        write_message(message=json_dumps(dict(error=error_text)))
        LOG.error(error_text)
        exit(1)

    await download_from_video_url(video_url=incoming_message['url'])


if __name__ == '__main__':
    try:
        asyncio_run(main())
    except Exception as e:
        write_message(json_dumps(dict(error='Unexpected error.')))
        LOG.exception(e)
        exit(1)

