"""OCR local (Tesseract) com pré-processamento p/ prints e tabelas do PJe."""
from __future__ import annotations

def ocr_imagem(caminho: str, lang: str = "por") -> str:
    import pytesseract
    from PIL import Image
    img = None
    try:  # pré-processamento opcional (OpenCV) melhora MUITO print/tabela
        import cv2
        raw = cv2.imread(str(caminho))
        if raw is not None:
            cinza = cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY)
            if cinza.shape[1] < 1800:  # amplia prints pequenos
                cinza = cv2.resize(cinza, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            _, img = cv2.threshold(cinza, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    except Exception:
        pass
    if img is None:
        img = Image.open(caminho)
    return pytesseract.image_to_string(img, lang=lang, config="--oem 3 --psm 6")
