"""Conservative dominant vehicle-colour estimation."""

from __future__ import annotations

import cv2
import numpy as np


class VehicleColorDetector:
    def detect(self, image: np.ndarray) -> tuple[str, float]:
        if image.size == 0:
            return "UNKNOWN", 0.0
        height, width = image.shape[:2]
        crop = image[int(height * 0.15):int(height * 0.8), int(width * 0.15):int(width * 0.85)]
        if crop.size == 0:
            return "UNKNOWN", 0.0
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV).reshape(-1, 3)
        saturation = float(np.median(hsv[:, 1]))
        value = float(np.median(hsv[:, 2]))
        if value < 45:
            return "BLACK", 0.75
        if saturation < 30 and value > 205:
            return "WHITE", 0.75
        if saturation < 35:
            return "SILVER/GRAY", 0.65
        hue = float(np.median(hsv[hsv[:, 1] > 40, 0])) if np.any(hsv[:, 1] > 40) else 0.0
        ranges = [
            ("RED", hue < 10 or hue >= 170), ("ORANGE", 10 <= hue < 22),
            ("YELLOW", 22 <= hue < 36), ("GREEN", 36 <= hue < 85),
            ("BLUE", 85 <= hue < 135), ("PURPLE", 135 <= hue < 170),
        ]
        for name, matches in ranges:
            if matches:
                return name, min(0.85, 0.45 + saturation / 510)
        return "UNKNOWN", 0.0

