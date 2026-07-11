from ocr_reader import OCRReader


class PlateManager:


    def __init__(self):

        self.ocr = OCRReader()



    def read(self, plate_image):

        if plate_image is None:
            return ""


        text = self.ocr.read_plate(
            plate_image
        )


        return text