from ultralytics import YOLO


print("==============================")
print("Vehicle Tracker Test")
print("==============================")


model = YOLO("models/yolov8n.pt")


print("YOLO Model Loaded")

print("Tracker Ready")