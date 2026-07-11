import cv2
from ultralytics import YOLO

from plate_detector import PlateDetector
from ocr_reader import OCRReader



model = YOLO(
    "models/yolov8n.pt"
)



video = cv2.VideoCapture(
    "videos/traffic.mp4"
)



plate_detector = PlateDetector()

ocr = OCRReader()



while True:


    ret, frame = video.read()


    if not ret:
        break



    results = model.track(
        frame,
        persist=True,
        tracker="bytetrack.yaml"
    )



    boxes = results[0].boxes



    if boxes.id is not None:


        for box in boxes.xyxy:


            x1,y1,x2,y2 = map(
                int,
                box
            )


            vehicle = frame[
                y1:y2,
                x1:x2
            ]


            if vehicle.size == 0:
                continue



            plate = plate_detector.detect(
                vehicle
            )


            number = ocr.read_plate(
                plate
            )



            if number:


                print(
                    "Number Plate:",
                    number
                )



    output = results[0].plot()



    cv2.imshow(
        "ANPR System",
        output
    )



    if cv2.waitKey(1)&0xff == ord("q"):
        break



video.release()

cv2.destroyAllWindows()