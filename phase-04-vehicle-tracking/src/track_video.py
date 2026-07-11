from ultralytics import YOLO
import cv2



model = YOLO(
    "models/yolov8n.pt"
)



video_path = "videos/traffic.mp4"


cap = cv2.VideoCapture(video_path)



while True:


    ret, frame = cap.read()


    if not ret:
        break



    results = model.track(
        frame,
        persist=True,
        tracker="bytetrack.yaml"
    )



    output = results[0].plot()



    cv2.imshow(
        "Vehicle Tracking",
        output
    )



    if cv2.waitKey(1) & 0xFF == ord("q"):
        break



cap.release()

cv2.destroyAllWindows()