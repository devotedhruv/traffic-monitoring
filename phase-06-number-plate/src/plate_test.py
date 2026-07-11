import pytesseract
import cv2


pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


print("==============================")
print("ANPR Plate Test")
print("==============================")


img = cv2.imread("plates/test.jpg")


if img is None:
    print("❌ Image not found")
    exit()


print("✅ Image loaded")


text = pytesseract.image_to_string(
    img,
    lang="nep+eng",
    config="--psm 8"
)


print("RAW OCR:")
print(repr(text))


print("Detected Plate:")
print(text.strip())