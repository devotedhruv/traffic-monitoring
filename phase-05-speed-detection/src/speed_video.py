import sys
import os
import cv2
import time

from ultralytics import YOLO

# Project root path add
ROOT_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

sys.path.append(ROOT_DIR)

from config.speed_config import SPEED_LIMIT
from src.speed_calculator import SpeedCalculator


print("==============================")
print("Phase 5 Speed Detection")
print("==============================")


# Load YOLO Model
model = YOLO(
    os.path.join(
        ROOT_DIR,
        "models",
        "yolov8n.pt"
    )
)


# Video Path
video_path = os.path.join(
    ROOT_DIR,
    "videos",
    "traffic.mp4"
)


cap = cv2.VideoCapture(video_path)


if not cap.isOpened():
    print("Error: Video not found")
    exit()


print("Video Loaded Successfully")


# Speed calculator
speed_calculator = SpeedCalculator(
    distance_meter=10
)


# Store vehicle data
vehicle_times = {}



while True:


    ret, frame = cap.read()


    if not ret:
        print("Video Finished")
        break



    # YOLO Tracking
    results = model.track(
        frame,
        persist=True,
        tracker="bytetrack.yaml"
    )


    boxes = results[0].boxes



    if boxes.id is not None:


        ids = boxes.id.tolist()


        for vehicle_id in ids:


            vehicle_id = int(vehicle_id)


            current_time = time.time()



            # First time vehicle found
            if vehicle_id not in vehicle_times:

                vehicle_times[vehicle_id] = current_time



            else:

                start_time = vehicle_times[vehicle_id]


                elapsed_time = (
                    current_time -
                    start_time
                )


                speed = speed_calculator.calculate_speed(
                    elapsed_time
                )


                status = "NORMAL"


                if speed > SPEED_LIMIT:

                    status = "OVERSPEED"



                print(
                    f"Vehicle ID: {vehicle_id} | "
                    f"Speed: {speed} km/hr | "
                    f"Status: {status}"
                )



    # Draw detection box
    output = results[0].plot()


    cv2.imshow(
        "Vehicle Speed Detection",
        output
    )


    # Press Q to quit
    if cv2.waitKey(1) & 0xFF == ord("q"):

        break



cap.release()

cv2.destroyAllWindows()


print("Program Closed")