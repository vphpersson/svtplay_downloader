from __future__ import annotations
from dataclasses import dataclass
from abc import ABC
from urllib.parse import urlparse, ParseResult
from pathlib import PurePath
from typing import Tuple, Iterator

from aiohttp import ClientSession
from m3u8 import loads as m3u8_loads, Media as HLSMedia

from svtplay_downloader.streams import Stream, AudioStream, VideoStream, SubtitleStream


@dataclass
class HLSStream(Stream, ABC):

    m3u8_playlist_uri: str

    async def generate_urls(self, session: ClientSession) -> Tuple[int, Iterator[str]]:

        parsed_base_url: ParseResult = urlparse(url=self.base_url)
        playlist_url: str = parsed_base_url._replace(
            path=str(PurePath(parsed_base_url.path) / self.m3u8_playlist_uri)
        ).geturl()

        async with session.get(url=playlist_url) as response:
            m3u_thing = m3u8_loads(content=await response.text())

        return len(m3u_thing.segments), (
            parsed_base_url._replace(
                path=str((PurePath(parsed_base_url.path) / self.m3u8_playlist_uri).parent / segment.uri)
            ).geturl()
            for segment in m3u_thing.segments
        )

    @classmethod
    def from_media(cls, media: HLSMedia, base_url: str) -> HLSStream:
        if media.type == 'AUDIO':
            return HLSAudioStream(
                base_url=base_url,
                language=media.language,
                m3u8_playlist_uri=media.uri
            )
        elif media.type == 'SUBTITLES':
            return HLSSubtitleStream(
                base_url=base_url,
                language=media.language,
                m3u8_playlist_uri=media.uri
            )


@dataclass
class HLSAudioStream(AudioStream, HLSStream):
    pass


@dataclass
class HLSSubtitleStream(SubtitleStream, HLSStream):
    pass


@dataclass
class HLSVideoStream(VideoStream, HLSStream):
    pass
