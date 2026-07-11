import cv2
import os


video_path = "videos/traffic.mp4"


# Check video exists or not

if not os.path.exists(video_path):

    print("Video not found")

    exit()



# Open video

camera = cv2.VideoCapture(video_path)



if not camera.isOpened():

    print("Cannot open video")

    exit()



print("Traffic Video Started")



while True:


    success, frame = camera.read()



    if success == False:

        print("Video Finished")

        break



    cv2.imshow(
        "Traffic Camera",
        frame
    )



    key = cv2.waitKey(25)



    if key == ord("q"):

        break




camera.release()

cv2.destroyAllWindows()


print("Video Closed")