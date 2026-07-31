from __future__ import annotations

import math
import re
import zlib
from dataclasses import asdict, dataclass
from itertools import islice
from pathlib import Path
from typing import Callable, Iterable, Iterator

import numpy as np
import torch
from torch import nn

from .cdm_agent import EventScore, ProvenanceEvent, RELATION_STAGE


RELATIONS = tuple(RELATION_STAGE)
KINDS = {
    "unknown": 0,
    "subject": 1,
    "file": 2,
    "netflow": 3,
}


@dataclass(frozen=True)
class PairwiseCalibration:
    raw_threshold: float
    raw_scale: float
    threshold: float
    count: int


class PairwiseNetwork(nn.Module):
    def __init__(
        self,
        token_buckets: int,
    ):
        super().__init__()
        self.kind = nn.Embedding(len(KINDS) * len(KINDS), 8)
        self.token = nn.Embedding(token_buckets, 32)
        self.decoder = nn.Sequential(
            nn.Linear(105, 128),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(128, len(RELATIONS)),
        )

    def forward(
        self,
        kind: torch.Tensor,
        path: torch.Tensor,
        source_image: torch.Tensor,
        target_image: torch.Tensor,
        depth: torch.Tensor,
    ) -> torch.Tensor:
        features = torch.cat(
            (
                self.kind(kind),
                self.token(path).mean(dim=1),
                self.token(source_image).mean(dim=1),
                self.token(target_image).mean(dim=1),
                depth.unsqueeze(1),
            ),
            dim=1,
        )
        return self.decoder(features)


class PairwiseSeedDetector:
    def __init__(
        self,
        device: str = "cpu",
        seed: int = 3407,
        token_buckets: int = 1 << 17,
    ):
        self.device = torch.device(device)
        self.seed = seed
        self.token_buckets = token_buckets
        self.token_cache: dict[str, np.ndarray] = {}
        torch.manual_seed(seed)
        if self.device.type == "cuda":
            torch.cuda.manual_seed_all(seed)
        self.model = PairwiseNetwork(token_buckets).to(self.device)
        self.calibration: PairwiseCalibration | None = None

    def fit(
        self,
        events: Iterable[ProvenanceEvent],
        batch_size: int = 65536,
        learning_rate: float = 1e-3,
        progress: Callable[[int, float], None] | None = None,
    ) -> dict[str, float | int]:
        optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=learning_rate,
            weight_decay=1e-5,
        )
        self.model.train()
        process_images: dict[str, str] = {}
        total_loss = 0.0
        count = 0
        for batch in self._batches(events, batch_size):
            tensors, labels = self._encode(batch, process_images)
            optimizer.zero_grad(set_to_none=True)
            logits = self.model(*tensors)
            loss = nn.functional.cross_entropy(logits, labels)
            loss.backward()
            optimizer.step()
            batch_count = len(batch)
            count += batch_count
            total_loss += float(loss.detach()) * batch_count
            if progress is not None:
                progress(count, total_loss / count)
        return {
            "events": count,
            "mean_loss": total_loss / max(count, 1),
        }

    def calibrate(
        self,
        events: Iterable[ProvenanceEvent],
        batch_size: int = 65536,
        progress: Callable[[int, float], None] | None = None,
    ) -> PairwiseCalibration:
        losses = []
        process_images: dict[str, str] = {}
        count = 0
        maximum = 0.0
        for batch in self._batches(events, batch_size):
            raw = self._raw_losses(batch, process_images)
            losses.append(raw)
            count += len(raw)
            maximum = max(maximum, float(raw.max(initial=0.0)))
            if progress is not None:
                progress(count, maximum)
        values = (
            np.concatenate(losses)
            if losses
            else np.asarray([1.0], dtype=np.float32)
        )
        scale = float(np.quantile(values, 0.95))
        scale = max(scale, 1e-6)
        threshold = self._normalize(maximum, scale)
        self.calibration = PairwiseCalibration(
            raw_threshold=maximum,
            raw_scale=scale,
            threshold=threshold,
            count=count,
        )
        return self.calibration

    def iter_scores(
        self,
        events: Iterable[ProvenanceEvent],
        batch_size: int = 65536,
    ) -> Iterator[EventScore]:
        if self.calibration is None:
            raise RuntimeError("calibration is required")
        process_images: dict[str, str] = {}
        for batch in self._batches(events, batch_size):
            raw = self._raw_losses(batch, process_images)
            scores = 1.0 - np.exp(
                -raw / max(self.calibration.raw_scale, 1e-6)
            )
            for event, score in zip(batch, scores):
                value = float(score)
                yield EventScore(
                    event=event,
                    score=value,
                    structural=value,
                    trace=0.0,
                    path=value,
                )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "seed": self.seed,
                "token_buckets": self.token_buckets,
                "relations": RELATIONS,
                "state_dict": self.model.state_dict(),
                "calibration": (
                    asdict(self.calibration)
                    if self.calibration is not None
                    else None
                ),
            },
            path,
        )

    @classmethod
    def load(
        cls,
        path: Path,
        device: str = "cpu",
    ) -> PairwiseSeedDetector:
        payload = torch.load(path, map_location=device)
        if tuple(payload["relations"]) != RELATIONS:
            raise ValueError("relation vocabulary mismatch")
        detector = cls(
            device=device,
            seed=int(payload["seed"]),
            token_buckets=int(payload["token_buckets"]),
        )
        detector.model.load_state_dict(payload["state_dict"])
        calibration = payload.get("calibration")
        if calibration is not None:
            detector.calibration = PairwiseCalibration(**calibration)
        return detector

    def _raw_losses(
        self,
        batch: list[ProvenanceEvent],
        process_images: dict[str, str],
    ) -> np.ndarray:
        self.model.eval()
        tensors, labels = self._encode(batch, process_images)
        with torch.inference_mode():
            logits = self.model(*tensors)
            losses = nn.functional.cross_entropy(
                logits,
                labels,
                reduction="none",
            )
        return losses.detach().cpu().numpy().astype(np.float32, copy=False)

    def _encode(
        self,
        batch: list[ProvenanceEvent],
        process_images: dict[str, str],
    ) -> tuple[tuple[torch.Tensor, ...], torch.Tensor]:
        size = len(batch)
        kinds = np.empty(size, dtype=np.int64)
        paths = np.empty((size, 8), dtype=np.int64)
        source_images = np.empty((size, 8), dtype=np.int64)
        target_images = np.empty((size, 8), dtype=np.int64)
        depths = np.empty(size, dtype=np.float32)
        labels = np.empty(size, dtype=np.int64)
        relation_index = {relation: index for index, relation in enumerate(RELATIONS)}
        for index, event in enumerate(batch):
            source = KINDS.get(event.source_kind, 0)
            target = KINDS.get(event.target_kind, 0)
            path = event.path or "<missing>"
            kinds[index] = source * len(KINDS) + target
            paths[index] = self._tokens(path)
            source_images[index] = self._tokens(
                process_images.get(event.source, "<missing>")
                if event.source_kind == "subject"
                else "<missing>"
            )
            target_images[index] = self._tokens(
                process_images.get(event.target, "<missing>")
                if event.target_kind == "subject"
                else "<missing>"
            )
            depths[index] = min(path.count("/"), 16) / 16
            labels[index] = relation_index[event.relation]
            if event.relation == "EVENT_EXECUTE" and event.path:
                if event.source_kind == "subject":
                    process_images[event.source] = event.path
                if event.target_kind == "subject":
                    process_images[event.target] = event.path
        tensors = (
            torch.from_numpy(kinds).to(self.device),
            torch.from_numpy(paths).to(self.device),
            torch.from_numpy(source_images).to(self.device),
            torch.from_numpy(target_images).to(self.device),
            torch.from_numpy(depths).to(self.device),
        )
        return tensors, torch.from_numpy(labels).to(self.device)

    def _tokens(self, value: str) -> np.ndarray:
        cached = self.token_cache.get(value)
        if cached is not None:
            return cached
        tokens = re.findall(r"[a-z]+|\d+", value.lower())
        if not tokens:
            tokens = ["<missing>"]
        selected = tokens[:4] + tokens[-4:]
        selected.extend(["<pad>"] * (8 - len(selected)))
        encoded = np.asarray(
            [
                zlib.crc32(
                    token.encode("utf-8", errors="ignore")
                )
                % self.token_buckets
                for token in selected
            ],
            dtype=np.int64,
        )
        self.token_cache[value] = encoded
        return encoded

    @staticmethod
    def _normalize(value: float, scale: float) -> float:
        return 1.0 - math.exp(-value / max(scale, 1e-6))

    @staticmethod
    def _batches(
        events: Iterable[ProvenanceEvent],
        size: int,
    ) -> Iterator[list[ProvenanceEvent]]:
        iterator = iter(events)
        while True:
            batch = list(islice(iterator, size))
            if not batch:
                return
            yield batch
