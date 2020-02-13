from dataclasses import dataclass
from abc import ABC, abstractmethod
from asyncio import gather as asyncio_gather
from typing import Tuple, Iterator, Optional, Callable, Any

from aiohttp import ClientSession


@dataclass
class Stream(ABC):

    base_url: str

    @abstractmethod
    async def generate_urls(self, session: ClientSession) -> Tuple[int, Iterator[str]]:
        raise NotImplementedError

    # TODO: Create a method that downloads to a file, provided as an argument.
    # TODO: Rename this to something that indicates that it downloads to memory.
    async def download(
        self,
        session: ClientSession,
        num_concurrent: int = 10,
        per_downloaded_segment_callback: Optional[Callable[[int, int, str], Any]] = None
    ) -> bytes:
        """
        Download the media of the stream into memory.

        The segments compromising the media are downloaded concurrently.

        As the order of completed downloads cannot be guaranteed when the downloads are performed concurrently,
        each download needs to keep track of the ordinal number of the segment that is being downloaded. This number
        is used as an index into  an array that collects the data of each downloaded segment. When all downloads are
        complete, the data of the array is joined and returned.

        :param session: An HTTP with which to perform the downloads.
        :param num_concurrent: The number of concurrent downloads. Limited by the number of segments to download.
        :param per_downloaded_segment_callback: A callback function that is called after a segment has been successfully
            downloaded.
        :return: The data of the media of the stream.
        """

        num_download_items, url_iterator = await self.generate_urls(session=session)
        enumerated_url_iterator = enumerate(url_iterator)
        download_arr = [None] * num_download_items

        async def download_url() -> None:
            nonlocal download_arr
            for i, url in enumerated_url_iterator:
                async with session.get(url) as response:
                    download_arr[i] = await response.read()
                    if per_downloaded_segment_callback:
                        per_downloaded_segment_callback(i, num_download_items, url)

        await asyncio_gather(*[download_url() for _ in range(min(num_download_items, num_concurrent))])

        return b''.join(download_arr)


@dataclass
class AudioStream(ABC):
    language: str


@dataclass
class SubtitleStream(ABC):
    language: str


@dataclass
class VideoStream(ABC):
    resolution: Tuple[int, int]

