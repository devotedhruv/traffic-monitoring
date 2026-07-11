from ultralytics import YOLO


class VehicleTracker:


    def __init__(self):

        self.model = YOLO(
            "models/yolov8n.pt"
        )



    def track(self, frame):

        results = self.model.track(
            frame,
            persist=True,
            tracker="bytetrack.yaml"
        )

        return results