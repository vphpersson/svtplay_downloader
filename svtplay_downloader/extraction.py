from __future__ import annotations
from asyncio import gather as asyncio_gather
from urllib.parse import urlparse, ParseResult
from re import compile as re_compile
from typing import List, TypedDict, Tuple
from pathlib import PurePath

from aiohttp import ClientSession
from mpegdash.parser import MPEGDASHParser
from m3u8 import loads as m3u8_loads

from svtplay_downloader.streams import AudioStream, VideoStream, SubtitleStream
from svtplay_downloader.streams.dash import DashStream
from svtplay_downloader.streams.hls import HLSStream, HLSVideoStream


SVTPLAY_VIDEO_URL_PATH_PATTERN = re_compile(pattern=r'^/video/(?P<escenic_id>\d+)/.*$')
SVTPLAY_API_GRAPHQL_ENDPOINT_URL: str = 'https://api.svt.se/contento/graphql'
SVTPLAY_API_VIDEO_ENDPOINT_URL: str = 'https://api.svt.se/video'


class VideoReference(TypedDict):
    url: str
    format: str


class ProgramData(TypedDict):
    videoReferences: List[VideoReference]


async def get_streams_from_program_data(
    program_data: ProgramData,
    session: ClientSession
) -> Tuple[List[VideoStream], List[AudioStream], List[SubtitleStream]]:

    async def fetch(url: str) -> str:
        async with session.get(url) as response:
            return await response.text()

    manifest_list = await asyncio_gather(*[
        fetch(url=video_reference['url'])
        for video_reference in program_data['videoReferences']
    ])

    streams = []

    for manifest, video_reference in zip(manifest_list, program_data['videoReferences']):
        parsed_url: ParseResult = urlparse(url=video_reference['url'])
        base_url: str = parsed_url._replace(path=str(PurePath(parsed_url.path).parent), query=None).geturl()

        if video_reference['format'] in {'hls'}:
            m3u8_object = m3u8_loads(content=manifest)

            for media in m3u8_object.media:
                streams.append(HLSStream.from_media(media=media, base_url=base_url))

            for playlist in m3u8_object.playlists:
                streams.append(
                    HLSVideoStream(
                        m3u8_playlist_uri=playlist.uri,
                        base_url=base_url,
                        resolution=playlist.stream_info.resolution
                    )
                )

        elif video_reference['format'] in {'dash264', 'dashhbbtv'}:
            for adaptation_set in next(iter(MPEGDASHParser.parse(string_or_url=manifest).periods)).adaptation_sets:
                for representation in adaptation_set.representations:
                    streams.append(
                        DashStream.from_representation(
                            representation=representation,
                            base_url=base_url,
                            adaptation_set=adaptation_set
                        )
                    )

        else:
            a = 3
            ...

    video_streams: List[VideoStream] = []
    audio_streams: List[AudioStream] = []
    subtitle_streams: List[SubtitleStream] = []

    while len(streams) > 0:
        stream = streams.pop()
        if isinstance(stream, VideoStream):
            video_streams.append(stream)
        elif isinstance(stream, AudioStream):
            audio_streams.append(stream)
        elif isinstance(stream, SubtitleStream):
            subtitle_streams.append(stream)
        else:
            raise ValueError('dog')

    return video_streams, audio_streams, subtitle_streams


async def get_streams_from_svt_id(svt_id: str, session: ClientSession):
    """
    Obtain the streams of a video given its SVT ID.

    :param svt_id: The SVT ID of the video to whose streams to obtain.
    :param session: An HTTP session with which to obtain the streams.
    :return:
    """

    async with session.get(url=f'{SVTPLAY_API_VIDEO_ENDPOINT_URL}/{svt_id}') as response:
        program_data: ProgramData = await response.json()

    return await get_streams_from_program_data(program_data=program_data, session=session)


async def get_streams_from_escenic_id(escenic_id: int, session: ClientSession):
    """
    Obtain the streams of a video given its Escenic ID.

    :param escenic_id: The Escenic ID of the video whose streams to obtain.
    :param session: An HTTP session with which to obtain the streams.
    :return:
    """

    graphql_data = {'query': f'{{ listablesByEscenicId(escenicIds: [{escenic_id}]) {{ svtId }} }}'}
    async with session.post(url=SVTPLAY_API_GRAPHQL_ENDPOINT_URL, json=graphql_data) as response:
        svt_id: str = (await response.json())['data']['listablesByEscenicId'][0]['svtId']

    return await get_streams_from_svt_id(svt_id=svt_id, session=session)


async def get_streams_from_video_url(video_url: str, session: ClientSession):
    """
    Obtain the streams of a video given its Svtplay video URL.

    :param video_url: The video URL of the video whose streams to obtain.
    :param session: An HTTP session with which to obtain the streams.
    :return:
    """

    return await get_streams_from_escenic_id(
        escenic_id=int(
            SVTPLAY_VIDEO_URL_PATH_PATTERN.match(
                string=urlparse(url=video_url).path
            ).groupdict()['escenic_id']
        ),
        session=session
    )
