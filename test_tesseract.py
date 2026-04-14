import pytesseract
try:
    print(pytesseract.get_tesseract_version())
    print("Installed languages:", pytesseract.get_languages())
except Exception as e:
    print("Error:", e)
