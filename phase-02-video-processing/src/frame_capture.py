

import cv2
import os


video_path = "videos/traffic.mp4"

save_folder = "frames"


if not os.path.exists(save_folder):
    os.makedirs(save_folder)


cap = cv2.VideoCapture(video_path)


if not cap.isOpened():

    print("Video cannot open")

    exit()


frame_number = 0


while True:

    ret, frame = cap.read()


    if not ret:
        break


    frame_number += 1


    filename = f"{save_folder}/frame_{frame_number}.jpg"


    cv2.imwrite(filename, frame)


    print("Saved:", filename)



cap.release()


print("All Frames Saved")