import abc
from pathlib import Path
from typing import Optional, Union, Callable

import numpy as np
from typing_extensions import Self

__all__ = ['EphysRecording', 'ProcessedEphysRecording']


class EphysRecording(metaclass=abc.ABCMeta):

    @property
    @abc.abstractmethod
    def data_path(self) -> Optional[Path]:
        pass

    @property
    def total_channels(self) -> int:
        return len(self.channel_list)

    @property
    def channel_list(self) -> np.ndarray:
        return np.arange(self.total_channels)

    @property
    @abc.abstractmethod
    def total_samples(self) -> int:
        pass

    @property
    @abc.abstractmethod
    def sample_rate(self) -> float:
        pass

    @property
    def total_duration(self) -> float:
        return self.total_samples / self.sample_rate

    @property
    def time_start(self) -> float:
        return 0

    @property
    def t(self) -> np.ndarray:
        return np.linspace(0, self.total_duration, self.total_samples) + self.time_start

    @abc.abstractmethod
    def __getitem__(self, item) -> np.ndarray:
        pass

    @property
    def meta(self) -> dict[str, str]:
        return {}


class ProcessedEphysRecording(EphysRecording):
    def __init__(self, time: np.ndarray,
                 channels: np.ndarray,
                 data: np.ndarray,
                 meta: dict[str, str] = None):
        if time.ndim != 1 or channels.ndim != 1 or data.shape != (len(channels), len(time)):
            raise ValueError(f'{time.ndim=}, {channels.ndim=}, {data.shape=}')

        self.__t = time.astype(float)
        self.__c = channels.astype(int)
        self.__d = data
        self.__m = {}
        if meta is not None:
            self.__m.update(meta)

    @property
    def data_path(self) -> Optional[Path]:
        return None

    @property
    def channel_list(self) -> np.ndarray:
        return self.__c

    @property
    def total_samples(self) -> int:
        return len(self.__t)

    @property
    def total_duration(self) -> float:
        return float(self.__t[-1] - self.__t[0])

    @property
    def sample_rate(self) -> float:
        return 1 / np.median(np.diff(self.__t))

    @property
    def time_start(self) -> float:
        return float(self.__t[0])

    @property
    def t(self) -> np.ndarray:
        return self.__t

    @property
    def dtype(self) -> np.dtype:
        return self.__d.dtype

    def __getitem__(self, item):
        return self.__d[item]

    def __setitem__(self, key, value):
        self.__d[key] = value

    @property
    def __array_interface__(self):
        return self.__d.__array_interface__

    def __array__(self):
        return self.__d

    @property
    def meta(self) -> dict[str, str]:
        return self.__m

    def fma(self, a: float, b: float = 0) -> Self:
        return ProcessedEphysRecording(self.__t, self.__c, self.__d * a + b)

    def with_time_range(self, t: tuple[float, float]) -> Self:
        x = np.nonzero(np.logical_and(t[0] <= self.__t, self.__t <= t[1]))[0]
        return ProcessedEphysRecording(self.__t[x], self.__c, self.__d[:, x])

    def with_time(self, t: Union[float, np.ndarray, Callable[[np.ndarray], np.ndarray]]) -> Self:
        if isinstance(t, (int, float, np.number)):
            t = self.__t + t
        elif isinstance(t, np.ndarray):
            if t.shape != self.__t.shape:
                raise ValueError()
        elif callable(t):
            t = t(self.__t)
        else:
            raise TypeError()

        return ProcessedEphysRecording(t, self.__c, self.__d)

    def with_channel(self, channel: np.ndarray) -> Self:
        return ProcessedEphysRecording(self.__t, self.__c[channel], self.__d[channel, :])
