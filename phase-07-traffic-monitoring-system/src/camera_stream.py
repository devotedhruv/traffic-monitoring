import cv2


class Camera:


    def __init__(self, path):

        self.video = cv2.VideoCapture(path)



    def read(self):

        return self.video.read()



    def release(self):

        self.video.release()