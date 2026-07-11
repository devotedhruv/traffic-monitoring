import cv2
import os


video_path = "videos/traffic.mp4"


if not os.path.exists(video_path):
    print("Video not found")
    exit()


cap = cv2.VideoCapture(video_path)


if not cap.isOpened():
    print("Cannot open video")
    exit()


total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

fps = cap.get(cv2.CAP_PROP_FPS)

width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))

height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))


print("==============================")
print("Video Information")
print("==============================")

print("Total Frames:", total_frames)
print("FPS:", fps)
print("Width:", width)
print("Height:", height)


cap.release()