from __future__ import annotations
from dataclasses import dataclass
from abc import ABC
from pathlib import PurePath
from urllib.parse import urlparse, ParseResult
from typing import Tuple, Iterator
from itertools import chain

from mpegdash.nodes import AdaptationSet, Representation, SegmentTemplate
from aiohttp import ClientSession

from svtplay_downloader.streams import Stream, AudioStream, VideoStream, SubtitleStream
from svtplay_downloader.internal_utils import expand_var


@dataclass
class DashStream(Stream, ABC):

    representation: Representation

    async def generate_urls(self, session: ClientSession) -> Tuple[int, Iterator[str]]:

        # NOTE: Svtplay-dl uses only the first one
        segment_template: SegmentTemplate = next(iter(self.representation.segment_templates))

        name_template = expand_var(
            string=segment_template.media,
            expand_map={'representationid': self.representation.id, 'bandwidth': self.representation.bandwidth},
            var_char='$'
        )

        num_segments = sum(
            (timeline_segment.r or 0)
            for segment_timeline in segment_template.segment_timelines
            for timeline_segment in segment_timeline.Ss
        )

        parsed_base_url: ParseResult = urlparse(url=self.base_url)

        return num_segments + 1, chain(
            (
                parsed_base_url._replace(
                    path=str(PurePath(parsed_base_url.path) / segment_template.initialization)
                ).geturl(),
            ),
            (
                parsed_base_url._replace(
                    path=str(
                        PurePath(parsed_base_url.path) / expand_var(
                            string=name_template,
                            expand_map={'number': i},
                            var_char='$',
                            exception_on_unexpanded=True
                        )
                    )
                ).geturl()
                for i in range(num_segments)
            )
        )

    @classmethod
    def from_representation(cls, representation: Representation, base_url: str, adaptation_set: AdaptationSet) -> DashStream:
        if adaptation_set.content_type == 'audio':
            return DashAudioStream(representation=representation, base_url=base_url, language=adaptation_set.lang)
        elif adaptation_set.content_type == 'video':
            return DashVideoStream(
                base_url=base_url,
                representation=representation,
                resolution=(representation.width, representation.height)
            )
        elif adaptation_set.content_type == 'text':
            return DashSubtitleStream(
                base_url=base_url,
                representation=representation,
                language=adaptation_set.lang,
            )
        else:
            raise ValueError('hello')


@dataclass
class DashAudioStream(AudioStream, DashStream):
    pass


@dataclass
class DashVideoStream(VideoStream, DashStream):
    pass


@dataclass
class DashSubtitleStream(SubtitleStream, DashStream):
    pass
