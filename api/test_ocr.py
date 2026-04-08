import os
import fitz
import pytesseract
from PIL import Image

def test_ocr():
    # 1. Download PDF byte stream from Supabase Storage
    os.environ['SUPABASE_URL'] = 'https://bjvtippltzerfnjvzbgb.supabase.co'
    os.environ['SUPABASE_SERVICE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJqdnRpcHBsdHplcmZuanZ6YmdiIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTE3OTA1MiwiZXhwIjoyMDkwNzU1MDUyfQ.nIizOga0sCh24F2DUB2WEQqew899dOhN22plOaWvOlU'
    from supabase import create_client
    sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_KEY'])
    print("Downloading PDF...")
    pdf_data = sb.storage.from_('books').download('7583e35a-5972-4030-beed-d1a5644fc469.pdf')

    # 2. Open PDF and get page 941 (index 940)
    doc = fitz.open(stream=pdf_data, filetype="pdf")
    page = doc[940]
    
    # 3. Render page to image with high resolution (dpi=300)
    print("Rendering page 941 to image...")
    pix = page.get_pixmap(dpi=300)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    # 4. Save image for reference
    img_path = "/tmp/page_941.png"
    img.save(img_path)
    print(f"Saved image to {img_path}")

    # 5. Run Tesseract OCR
    print("Running OCR (lang=vie)...")
    text = pytesseract.image_to_string(img, lang="vie")

    print("\n" + "="*50)
    print("OCR RESULT (First 1500 chars):")
    print("="*50)
    print(text[:1500])
    print("="*50)
    
if __name__ == "__main__":
    test_ocr()
