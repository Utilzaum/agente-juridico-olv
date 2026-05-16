#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo de OCR do bot jurídico — backend offline.

Hierarquia de extração:
  1. GLM-OCR via Ollama  (primário — modelo local de visão)
  2. Tesseract + Pillow   (fallback para imagens sem Ollama)
  3. PyMuPDF              (extração de texto nativo em PDF)
  4. pdf2image + Tesseract(fallback PDF sem PyMuPDF)

Não importa o bot principal — sem risco de importação circular.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

# ──────────────────────────────────────────────
# Dependências opcionais
# ──────────────────────────────────────────────
try:
    from PIL import Image, ImageFilter, ImageOps
except Exception:
    Image = ImageFilter = ImageOps = None  # type: ignore

try:
    import pytesseract
except Exception as exc:
    pytesseract = None  # type: ignore
    _pytesseract_err = exc
else:
    _pytesseract_err = None

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None  # type: ignore

try:
    import cv2
    import numpy as np
except Exception:
    cv2 = np = None  # type: ignore

try:
    from pdf2image import convert_from_path
except Exception:
    convert_from_path = None  # type: ignore

try:
    import httpx as _httpx
except Exception:
    _httpx = None  # type: ignore

# ──────────────────────────────────────────────
# Configuração
# ──────────────────────────────────────────────
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

OCR_LANG      = os.getenv("OCR_LANG",      "por+eng")
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "").strip()
OLLAMA_URL    = os.getenv("OLLAMA_URL",    "http://localhost:11434")
GLM_OCR_MODEL = os.getenv("GLM_OCR_MODEL", "glm-ocr:q8_0")   # modelo de visão

if pytesseract is not None and TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


# ──────────────────────────────────────────────
# Utilidades de texto
# ──────────────────────────────────────────────
def _normalizar_texto(texto: str) -> str:
    """Remove artefatos comuns de OCR e excesso de espaços/quebras."""
    if not texto:
        return ""
    texto = texto.replace("\x0c", " ")
    texto = re.sub(r"[ \t]+",  " ",    texto)
    texto = re.sub(r"\n{3,}",  "\n\n", texto)
    texto = re.sub(r"[ ]+\n",  "\n",   texto)
    return texto.strip()


# ──────────────────────────────────────────────
# GLM-OCR via Ollama  (backend primário)
# ──────────────────────────────────────────────
def _imagem_para_base64(imagem: "Image.Image") -> str:
    """Converte PIL Image → base64 JPEG."""
    buf = io.BytesIO()
    imagem.convert("RGB").save(buf, format="JPEG", quality=92)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _glm_ocr_imagem(imagem: "Image.Image") -> str:
    """
    Envia a imagem ao GLM-OCR rodando no Ollama e devolve o texto extraído.
    Usa o endpoint /api/generate com campo `images`.
    """
    if _httpx is None:
        raise ImportError("httpx não está instalado — necessário para chamar o Ollama.")

    b64 = _imagem_para_base64(imagem)

    payload = {
        "model":  GLM_OCR_MODEL,
        "prompt": "Text Recognition:",  # instrução padrão do GLM-OCR
        "images": [b64],
        "stream": False,
    }

    try:
        resp = _httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json=payload,
            timeout=120.0,
        )
        resp.raise_for_status()
        data = resp.json()
        texto = data.get("response", "")
        logger.info("GLM-OCR: %d chars extraídos.", len(texto))
        return _normalizar_texto(texto)
    except Exception as exc:
        logger.warning("GLM-OCR falhou: %s", exc)
        raise


def _glm_ocr_arquivo(caminho: str) -> str:
    """
    Tenta OCR via GLM-OCR para imagens ou PDFs.
    PDFs são convertidos página a página antes de enviar.
    """
    if Image is None:
        raise ImportError("Pillow é necessário para abrir imagens.")

    path = Path(caminho)
    ext  = path.suffix.lower()

    # ── PDF ──────────────────────────────────────────────────────────────────
    if ext == ".pdf":
        paginas: list[Image.Image] = []

        if fitz is not None:
            doc = fitz.open(str(path))
            try:
                for pg in doc:
                    pix = pg.get_pixmap(dpi=300, alpha=False)
                    paginas.append(
                        Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    )
            finally:
                doc.close()
        elif convert_from_path is not None:
            paginas = convert_from_path(str(path), dpi=300)
        else:
            raise RuntimeError("Nenhum backend de PDF disponível (PyMuPDF ou pdf2image).")

        textos = []
        for img in paginas:
            try:
                textos.append(_glm_ocr_imagem(img))
            except Exception as exc:
                logger.warning("GLM-OCR falhou em página do PDF: %s", exc)
        return _normalizar_texto("\n\n".join(textos))

    # ── Imagem ───────────────────────────────────────────────────────────────
    with Image.open(str(path)) as img:
        return _glm_ocr_imagem(img)


# ──────────────────────────────────────────────
# Pré-processamento Pillow/OpenCV  (fallback)
# ──────────────────────────────────────────────
def _preprocessar_pil(imagem: "Image.Image") -> "Image.Image":
    if Image is None:
        return imagem

    imagem = imagem.convert("RGB")
    w, h   = imagem.size
    if w < 1400:
        fator = max(2, int(1600 / max(w, 1)))
        imagem = imagem.resize((w * fator, h * fator))

    imagem = ImageOps.grayscale(imagem)
    imagem = ImageOps.autocontrast(imagem)
    imagem = imagem.filter(ImageFilter.SHARPEN)

    if cv2 is not None and np is not None:
        arr = np.array(imagem)
        arr = cv2.GaussianBlur(arr, (3, 3), 0)
        arr = cv2.adaptiveThreshold(
            arr, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31, 11,
        )
        imagem = Image.fromarray(arr)

    return imagem


def _tesseract_imagem(imagem: "Image.Image") -> str:
    if pytesseract is None:
        raise ImportError(
            "pytesseract não está instalado."
        ) from _pytesseract_err
    imagem = _preprocessar_pil(imagem)
    texto  = pytesseract.image_to_string(
        imagem, lang=OCR_LANG, config="--oem 3 --psm 6"
    )
    return _normalizar_texto(texto)


# ──────────────────────────────────────────────
# Backends PDF (fallback Tesseract)
# ──────────────────────────────────────────────
def _pdf_pymupdf_tesseract(caminho_pdf: str) -> str:
    if fitz is None:
        return ""

    doc = fitz.open(caminho_pdf)
    try:
        textos: list[str] = []
        for pg in doc:
            t = _normalizar_texto(pg.get_text("text") or "")
            if t:
                textos.append(t)

        combinado = "\n\n".join(textos).strip()
        if len(combinado) >= 120:
            return combinado

        # Fallback OCR por renderização
        imgs: list[Image.Image] = []
        if Image is not None:
            for pg in doc:
                pix = pg.get_pixmap(dpi=300, alpha=False)
                imgs.append(
                    Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                )

        ocrs: list[str] = []
        for img in imgs:
            try:
                ocrs.append(_tesseract_imagem(img))
            except Exception as exc:
                logger.warning("Tesseract falhou em página: %s", exc)

        return _normalizar_texto("\n\n".join(ocrs)) if ocrs else combinado
    finally:
        doc.close()


def _pdf_pdf2image_tesseract(caminho_pdf: str) -> str:
    if convert_from_path is None or Image is None:
        return ""
    paginas = convert_from_path(caminho_pdf, dpi=300)
    textos  = []
    for pg in paginas:
        try:
            textos.append(_tesseract_imagem(pg))
        except Exception as exc:
            logger.warning("Tesseract (pdf2image) falhou: %s", exc)
    return _normalizar_texto("\n\n".join(textos))


# ──────────────────────────────────────────────
# Ponto de entrada público
# ──────────────────────────────────────────────
def extrair_texto_do_arquivo(caminho_arquivo: str) -> str:
    """
    Extrai texto de qualquer PDF ou imagem.

    Ordem de tentativa:
      1. GLM-OCR  (Ollama local — mais preciso para documentos)
      2. Tesseract (fallback offline puro)
      3. PyMuPDF texto nativo (só PDF)

    Retorna string vazia em caso de falha total, sem propagar exceção.
    """
    if not caminho_arquivo:
        return ""

    caminho = Path(caminho_arquivo)
    if not caminho.exists():
        logger.warning("Arquivo não encontrado: %s", caminho_arquivo)
        return ""

    ext = caminho.suffix.lower()

    # ── Tentativa 1: GLM-OCR via Ollama ──────────────────────────────────────
    try:
        texto = _glm_ocr_arquivo(str(caminho))
        if texto.strip():
            logger.info("GLM-OCR: extração bem-sucedida.")
            return texto
    except Exception as exc:
        logger.warning("GLM-OCR indisponível, usando fallback Tesseract: %s", exc)

    # ── Tentativa 2: Tesseract (imagem direta) ────────────────────────────────
    if ext != ".pdf" and Image is not None:
        try:
            with Image.open(str(caminho)) as img:
                texto = _tesseract_imagem(img)
            if texto.strip():
                return texto
        except Exception as exc:
            logger.warning("Tesseract falhou: %s", exc)

    # ── Tentativa 3: PDF com Tesseract ────────────────────────────────────────
    if ext == ".pdf":
        texto = _pdf_pymupdf_tesseract(str(caminho))
        if texto.strip():
            return texto

        texto = _pdf_pdf2image_tesseract(str(caminho))
        if texto.strip():
            return texto

    logger.error("Nenhum backend conseguiu extrair texto de: %s", caminho_arquivo)
    return ""


# ── Aliases públicos ──────────────────────────
def extrair_texto_imagem(caminho: str) -> str:
    return extrair_texto_do_arquivo(caminho)


def extrair_texto_pdf(caminho: str) -> str:
    return extrair_texto_do_arquivo(caminho)


__all__ = [
    "extrair_texto_do_arquivo",
    "extrair_texto_imagem",
    "extrair_texto_pdf",
]


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 2:
        print("Uso: python bot_ocr.py <arquivo.pdf|imagem>")
        raise SystemExit(1)
    print(extrair_texto_do_arquivo(sys.argv[1]))
