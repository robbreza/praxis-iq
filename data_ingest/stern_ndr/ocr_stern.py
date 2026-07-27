"""OCR pipeline for scanned NDR itineraries (e.g. E:\\HPSCANS\\stern.pdf — a Sterne Agee software
roadshow, analyst R. Breza, US May 2014 + UK Jan 2015). The scan has NO text layer, so text
extraction returns nothing; this rasterizes each page with PyMuPDF (fitz) at 300 dpi and runs
Tesseract OCR over the images.

Setup (Windows, one-time):
  winget install --id UB-Mannheim.TesseractOCR --silent   # the OCR engine (-> C:\\Program Files\\Tesseract-OCR)
  python -m pip install --user pytesseract pymupdf pillow  # python wrappers (fitz renders, pytesseract OCRs)

Usage: python ocr_stern.py <scanned.pdf>   -> prints OCR text (redirect to a .txt).
"""
import sys
import pytesseract
import fitz  # PyMuPDF

# Tesseract isn't on this session's PATH; point at the UB-Mannheim install.
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def ocr_pdf(path, dpi=300):
    doc = fitz.open(path)
    out = []
    for i in range(doc.page_count):
        pix = doc.load_page(i).get_pixmap(dpi=dpi)
        img = f"{path}.p{i}.png"
        pix.save(img)
        out.append(pytesseract.image_to_string(img))
    return "\n".join(out)


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else r"E:\HPSCANS\stern.pdf"
    print(ocr_pdf(src))
