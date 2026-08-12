"""Optional OCR engines plus conservative multi-frame plate aggregation."""

from __future__ import annotations

import logging
import shutil
import subprocess
import threading
from collections import Counter, defaultdict, deque
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from services.plate_validator import PlateValidator
from services.types import PlateRead

log = logging.getLogger("trafficops.plate_ocr")


class OCREngine(Protocol):
    available: bool

    def read(self, image: np.ndarray) -> list[tuple[str, float]]: ...


class UnavailableOCREngine:
    available = False

    def read(self, image: np.ndarray) -> list[tuple[str, float]]:
        return []


class EasyOCREngine:
    def __init__(self, languages: tuple[str, ...] = ("en",), gpu: bool = False):
        try:
            import easyocr

            self.reader = easyocr.Reader(list(languages), gpu=gpu, verbose=False)
            self.available = True
        except Exception as exc:  # Optional model/runtime dependency.
            self.reader = None
            self.available = False
            log.warning("EasyOCR unavailable: %s", exc)

    def read(self, image: np.ndarray) -> list[tuple[str, float]]:
        if self.reader is None:
            return []
        return [(str(text), float(confidence)) for _, text, confidence in self.reader.readtext(image)]


class TesseractOCREngine:
    def __init__(self, languages: str = "eng", command: str = "tesseract"):
        self.languages = languages
        self.command = shutil.which(command) if command else None
        self.available = self.command is not None

    def read(self, image: np.ndarray) -> list[tuple[str, float]]:
        if self.command is None or image.size == 0:
            return []
        import cv2

        encoded, payload = cv2.imencode(".png", image)
        if not encoded:
            return []
        try:
            completed = subprocess.run(
                [
                    self.command, "stdin", "stdout", "-l", self.languages,
                    "--psm", "7", "tsv",
                ],
                input=payload.tobytes(),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=8,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            log.warning("Tesseract plate read failed: %s", exc)
            return []
        grouped: dict[tuple[str, ...], list[tuple[str, float]]] = defaultdict(list)
        lines = completed.stdout.decode(errors="ignore").splitlines()[1:]
        for line in lines:
            columns = line.split("\t", 11)
            if len(columns) < 12:
                continue
            confidence, text = columns[10], columns[11]
            try:
                score = max(0.0, min(1.0, float(confidence) / 100.0))
            except (TypeError, ValueError):
                continue
            if str(text).strip():
                grouped[tuple(columns[1:5])].append((str(text).strip(), score))
        return [
            (" ".join(text for text, _ in words), sum(score for _, score in words) / len(words))
            for words in grouped.values() if words
        ]


@dataclass(frozen=True)
class _Observation:
    text: str
    confidence: float
    timestamp: float


class PlateAggregator:
    def __init__(
        self,
        validator: PlateValidator | None = None,
        confirmed_threshold: float = 0.78,
        possible_threshold: float = 0.5,
        minimum_confirmed_observations: int = 2,
        history_size: int = 12,
    ):
        self.validator = validator or PlateValidator()
        self.confirmed_threshold = confirmed_threshold
        self.possible_threshold = possible_threshold
        self.minimum_confirmed_observations = minimum_confirmed_observations
        self._observations: dict[int, deque[_Observation]] = defaultdict(
            lambda: deque(maxlen=history_size)
        )
        self._lock = threading.Lock()

    def add(self, tracking_id: int, text: str, confidence: float, timestamp: float) -> PlateRead:
        valid, normalized = self.validator.validate(text)
        if valid:
            with self._lock:
                self._observations[tracking_id].append(
                    _Observation(normalized, max(0.0, min(1.0, confidence)), timestamp)
                )
        return self.result(tracking_id)

    def result(self, tracking_id: int) -> PlateRead:
        with self._lock:
            observations = list(self._observations.get(tracking_id, ()))
        if not observations:
            return PlateRead()
        counts = Counter(observation.text for observation in observations)
        weighted: dict[str, float] = defaultdict(float)
        confidence_totals: dict[str, float] = defaultdict(float)
        for observation in observations:
            weighted[observation.text] += max(0.05, observation.confidence)
            confidence_totals[observation.text] += observation.confidence
        winner = max(weighted, key=weighted.get)
        winner_count = counts[winner]
        mean_confidence = confidence_totals[winner] / winner_count
        consistency = winner_count / len(observations)
        aggregate_confidence = mean_confidence * (0.65 + 0.35 * consistency)
        if aggregate_confidence >= self.confirmed_threshold and winner_count >= self.minimum_confirmed_observations:
            status = "CONFIRMED"
        elif aggregate_confidence >= self.possible_threshold:
            status = "POSSIBLE"
        else:
            return PlateRead(observations=len(observations))
        return PlateRead(
            text=winner,
            confidence=round(aggregate_confidence, 3),
            status=status,
            observations=len(observations),
        )


class PlateOCRService:
    """Runs OCR off the frame-processing thread and caches results per track."""

    def __init__(
        self,
        engine: OCREngine | None = None,
        aggregator: PlateAggregator | None = None,
        interval_frames: int = 8,
    ):
        self.engine = engine or UnavailableOCREngine()
        self.aggregator = aggregator or PlateAggregator()
        self.interval_frames = max(1, interval_frames)
        self._last_frame: dict[int, int] = {}
        self._pending: dict[int, Future[list[tuple[str, float]]]] = {}
        self._timestamps: dict[int, float] = {}
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="plate-ocr")

    @property
    def available(self) -> bool:
        return bool(self.engine.available)

    def submit(self, tracking_id: int, image: np.ndarray, frame_index: int, timestamp: float) -> None:
        if not self.available or tracking_id in self._pending:
            return
        if frame_index - self._last_frame.get(tracking_id, -self.interval_frames) < self.interval_frames:
            return
        self._last_frame[tracking_id] = frame_index
        self._timestamps[tracking_id] = timestamp
        self._pending[tracking_id] = self._executor.submit(self.engine.read, image.copy())

    def result(self, tracking_id: int) -> PlateRead:
        future = self._pending.get(tracking_id)
        if future is not None and future.done():
            self._pending.pop(tracking_id, None)
            timestamp = self._timestamps.pop(tracking_id, 0.0)
            try:
                candidates = future.result()
            except Exception:
                log.exception("OCR worker failed for track %s", tracking_id)
                candidates = []
            for text, confidence in candidates:
                self.aggregator.add(tracking_id, text, confidence, timestamp)
        return self.aggregator.result(tracking_id)

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)


def create_ocr_engine(
    name: str,
    gpu: bool = False,
    command: str = "tesseract",
    languages: str = "eng",
) -> OCREngine:
    normalized = name.strip().lower()
    if normalized == "easyocr":
        return EasyOCREngine(gpu=gpu)
    if normalized == "tesseract":
        return TesseractOCREngine(languages=languages, command=command)
    return UnavailableOCREngine()
