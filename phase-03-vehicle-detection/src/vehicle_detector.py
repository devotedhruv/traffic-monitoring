from ultralytics import YOLO
import cv2


model = YOLO("models/yolov8n.pt")


image_path = "images/test.jpg"


results = model(image_path)


for result in results:

    result.show()

    boxes = result.boxes

    print("Vehicles Detected:")

    for box in boxes:

        class_id = int(box.cls[0])

        confidence = float(box.conf[0])


        name = model.names[class_id]


        print(
            name,
            confidence
        )