import numpy as np

from dataclasses import dataclass
from torch.utils.tensorboard.writer import SummaryWriter
from typing import List, Optional, Sequence, TypeVar


@dataclass
class Episode:
    score: float = 0
    length: int = 0


StatisticSelf = TypeVar("StatisticSelf", bound="Statistic")


@dataclass
class Statistic:
    values: np.ndarray
    round_digits: int = 2

    @property
    def mean(self) -> float:
        return np.mean(self.values).item()

    @property
    def std(self) -> float:
        return np.std(self.values).item()

    @property
    def min(self) -> float:
        return np.min(self.values).item()

    @property
    def max(self) -> float:
        return np.max(self.values).item()

    def sum(self) -> float:
        return np.sum(self.values).item()

    def __len__(self) -> int:
        return len(self.values)

    def _diff(self: StatisticSelf, o: StatisticSelf) -> float:
        return (self.mean - self.std) - (o.mean - o.std)

    def __gt__(self: StatisticSelf, o: StatisticSelf) -> bool:
        return self._diff(o) > 0

    def __ge__(self: StatisticSelf, o: StatisticSelf) -> bool:
        return self._diff(o) >= 0

    def __repr__(self) -> str:
        mean = round(self.mean, self.round_digits)
        std = round(self.std, self.round_digits)
        if self.round_digits == 0:
            mean = int(mean)
            std = int(std)
        return f"{mean} +/- {std}"

    def to_dict(self) -> dict[str, float]:
        return {
            "mean": self.mean,
            "std": self.std,
            "min": self.min,
            "max": self.max,
        }


EpisodesStatsSelf = TypeVar("EpisodesStatsSelf", bound="EpisodesStats")


class EpisodesStats:
    episodes: Sequence[Episode]
    simple: bool
    score: Statistic
    length: Statistic

    def __init__(self, episodes: Sequence[Episode], simple: bool = False) -> None:
        self.episodes = episodes
        self.simple = simple
        self.score = Statistic(np.array([e.score for e in episodes]))
        self.length = Statistic(np.array([e.length for e in episodes]), round_digits=0)

    def __gt__(self: EpisodesStatsSelf, o: EpisodesStatsSelf) -> bool:
        return self.score > o.score

    def __ge__(self: EpisodesStatsSelf, o: EpisodesStatsSelf) -> bool:
        return self.score >= o.score

    def __repr__(self) -> str:
        return (
            f"Score: {self.score} ({round(self.score.mean - self.score.std, 2)}) | "
            f"Length: {self.length}"
        )

    def _asdict(self) -> dict:
        return {
            "n_episodes": len(self.episodes),
            "score": self.score.to_dict(),
            "length": self.length.to_dict(),
        }

    def write_to_tensorboard(
        self, tb_writer: SummaryWriter, main_tag: str, global_step: Optional[int] = None
    ) -> None:
        stats = {"mean": self.score.mean}
        if not self.simple:
            stats.update(
                {
                    "min": self.score.min,
                    "max": self.score.max,
                    "result": self.score.mean - self.score.std,
                }
            )
        tb_writer.add_scalars(
            main_tag,
            stats,
            global_step=global_step,
        )


class EpisodeAccumulator:
    def __init__(self, num_envs: int):
        self.episodes = []
        self.current_episodes = [Episode() for _ in range(num_envs)]

    def step(self, reward: np.ndarray, done: np.ndarray) -> None:
        for idx, current in enumerate(self.current_episodes):
            current.score += reward[idx]
            current.length += 1
            if done[idx]:
                self.episodes.append(current)
                self.on_done(idx, current)
                self.current_episodes[idx] = Episode()

    def __len__(self) -> int:
        return len(self.episodes)

    def on_done(self, ep_idx: int, episode: Episode) -> None:
        pass

    def stats(self) -> EpisodesStats:
        return EpisodesStats(self.episodes)


class RolloutStats(EpisodeAccumulator):
    def __init__(self, num_envs: int, print_n_episodes: int, tb_writer: SummaryWriter):
        super().__init__(num_envs)
        self.print_n_episodes = print_n_episodes
        self.epochs: List[EpisodesStats] = []
        self.tb_writer = tb_writer

    def on_done(self, ep_idx: int, episode: Episode) -> None:
        if (
            self.print_n_episodes >= 0
            and len(self.episodes) % self.print_n_episodes == 0
        ):
            sample = self.episodes[-self.print_n_episodes :]
            epoch = EpisodesStats(sample)
            self.epochs.append(epoch)
            total_steps = np.sum([e.length for e in self.episodes])
            print(
                f"Episode: {len(self.episodes)} | "
                f"{epoch} | "
                f"Total Steps: {total_steps}"
            )
            epoch.write_to_tensorboard(self.tb_writer, "train", global_step=total_steps)
