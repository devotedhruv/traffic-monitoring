import pytesseract
import cv2


pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


class OCRReader:


    def read_plate(self, image):


        gray = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2GRAY
        )


        gray = cv2.threshold(
            gray,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )[1]


        text = pytesseract.image_to_string(
            gray,
            lang="nep+eng",
            config="--psm 8"
        )


        return text.strip()