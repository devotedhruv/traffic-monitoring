import cv2


class PlateDetector:


    def detect(self, vehicle_image):


        height, width = vehicle_image.shape[:2]


        # bottom area assume as plate area
        plate = vehicle_image[
            int(height*0.6):height,
            int(width*0.2):int(width*0.8)
        ]


        return plate