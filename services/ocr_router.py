#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCR Router v0.2 — GLM-OCR (Ollama) primário; Tesseract (core.bot_ocr) fallback.
Privacidade: tudo local, mesma filosofia do projeto."""
import os, base64, logging, time, requests
from pathlib import Path

logger = logging.getLogger(__name__)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
GLM_MODEL = os.getenv("GLM_OCR_MODEL", "glm-ocr")
GLM_TIMEOUT = int(os.getenv("GLM_OCR_TIMEOUT", "180"))

def _texto_digital_pdf(caminho):
    try:
        import fitz
        return "".join(p.get_text() for p in fitz.open(caminho)).strip()
    except Exception:
        return ""

def _pdf_para_imagens(caminho):
    try:
        import fitz
        return [_otimizar_imagem(pg.get_pixmap(dpi=150).tobytes("png")) for pg in fitz.open(caminho)]
    except Exception:
        return []

def _otimizar_imagem(bytes_img, max_lado=1408):
    """Redimensiona p/ caber na VRAM de GPU antiga (evita 500 por OOM na visão)."""
    try:
        import cv2, numpy as np
        arr = np.frombuffer(bytes_img, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None: return bytes_img
        h, w = img.shape[:2]
        esc = min(1.0, max_lado / max(h, w))
        if esc < 1.0:
            img = cv2.resize(img, None, fx=esc, fy=esc, interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
        return buf.tobytes() if ok else bytes_img
    except Exception:
        return bytes_img

def glm_disponivel():
    try:
        ms = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5).json().get("models", [])
        return any(GLM_MODEL in m.get("name", "") for m in ms)
    except Exception:
        return False

def _glm_ocr(imagens):
    payload = {"model": GLM_MODEL, "stream": False,
               "prompt": "Transcreva integralmente o texto deste documento brasileiro, "
                         "preservando linhas, números e datas. Responda apenas com o texto.",
               "images": [base64.b64encode(b).decode() for b in imagens],
               "options": {"temperature": 0.0}}
    for tent in (1, 2):
        r = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=GLM_TIMEOUT)
        if r.status_code == 200:
            return r.json().get("response", "").strip()
        logger.warning("⚠️ GLM-OCR tent. %d → HTTP %d", tent, r.status_code)
        time.sleep(2)
    raise RuntimeError(f"GLM-OCR HTTP {r.status_code}")

def extrair_texto(caminho):
    p = Path(caminho)
    if p.suffix.lower() == ".pdf":                      # 1) PDF digital: sem IA
        digital = _texto_digital_pdf(str(p))
        if len(digital) >= 200:
            logger.info("📄 OCR: texto digital (%d chars)", len(digital)); return digital
    if glm_disponivel():                                 # 2) GLM-OCR
        try:
            imgs = _pdf_para_imagens(str(p)) if p.suffix.lower() == ".pdf" else [_otimizar_imagem(p.read_bytes())]
            if imgs:
                texto = _glm_ocr(imgs)
                if len(texto) >= 40:
                    logger.info("🧠 OCR: GLM-OCR (%d chars)", len(texto)); return texto
        except Exception as e:
            logger.warning("⚠️ GLM-OCR falhou (%s) → fallback", e)
    from core.bot_ocr import extrair_texto_do_arquivo    # 3) Tesseract
    logger.info("📠 OCR: Tesseract (fallback)")
    return extrair_texto_do_arquivo(str(caminho))
