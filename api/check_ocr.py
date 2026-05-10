from services.ocr_engine import is_ocr_available
status = is_ocr_available()
print("OCR Status:")
for engine, ok in status.items():
    icon = "✅" if ok else "❌"
    print(f"  {engine}: {icon}")
