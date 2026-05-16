#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo de OCR do bot jurídico.

Este arquivo deve conter apenas funções de extração de texto.
Ele não deve importar o bot principal, evitando importação circular.
"""

from __future__ import annotations

import os
import re
import logging
from pathlib import Path
from typing import Optional

# Dependências opcionais: o módulo continua importável mesmo se algumas delas
# não estiverem instaladas, desde que haja pelo menos Pillow + pytesseract.
try:
    from PIL import Image, ImageFilter, ImageOps, ImageEnhance
except Exception:  # pragma: no cover
    Image = None  # type: ignore
    ImageFilter = None  # type: ignore
    ImageOps = None  # type: ignore
    ImageEnhance = None  # type: ignore

try:
    import pytesseract
except Exception as exc:  # pragma: no cover
    pytesseract = None  # type: ignore
    _pytesseract_import_error = exc
else:
    _pytesseract_import_error = None

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None  # type: ignore

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore
    np = None  # type: ignore

try:
    from pdf2image import convert_from_path
except Exception:  # pragma: no cover
    convert_from_path = None  # type: ignore

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

OCR_LANG = os.getenv("OCR_LANG", "por+eng")
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "").strip()

if pytesseract is not None and TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


def _normalizar_texto(texto: str) -> str:
    """Remove excesso de quebras, espaços e artefatos comuns de OCR."""
    if not texto:
        return ""

    texto = texto.replace("\x0c", " ")
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    texto = re.sub(r"[ ]+\n", "\n", texto)
    texto = texto.strip()
    return texto


def _preprocessar_imagem_pil(imagem: "Image.Image") -> "Image.Image":
    """
    Pré-processamento leve e robusto para OCR.
    Mantém o pipeline simples para reduzir dependências.
    """
    if Image is None:
        return imagem

    imagem = imagem.convert("RGB")

    # Aumenta a resolução em imagens pequenas.
    largura, altura = imagem.size
    if largura < 1400:
        fator = max(2, int(1600 / max(largura, 1)))
        imagem = imagem.resize((largura * fator, altura * fator))

    # Cinza + autocontraste
    imagem = ImageOps.grayscale(imagem)
    imagem = ImageOps.autocontrast(imagem)

    # Suavização leve / nitidez
    imagem = imagem.filter(ImageFilter.SHARPEN)

    # Se OpenCV estiver disponível, aplica limiarização adaptativa.
    if cv2 is not None and np is not None:
        arr = np.array(imagem)
        arr = cv2.GaussianBlur(arr, (3, 3), 0)
        arr = cv2.adaptiveThreshold(
            arr,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            11,
        )
        imagem = Image.fromarray(arr)

    return imagem


def _ocr_imagem(imagem: "Image.Image") -> str:
    """Executa OCR em uma imagem PIL já pré-processada."""
    if pytesseract is None:
        raise ImportError(
            "pytesseract não está instalado. "
            "Instale a dependência ou ajuste o ambiente."
        ) from _pytesseract_import_error

    imagem = _preprocessar_imagem_pil(imagem)

    config = "--oem 3 --psm 6"
    texto = pytesseract.image_to_string(imagem, lang=OCR_LANG, config=config)
    return _normalizar_texto(texto)


def _extrair_texto_pdf_pymupdf(caminho_pdf: str) -> str:
    """
    Tenta primeiro extrair texto real do PDF. Se vier pouco ou nada,
    faz renderização da página e roda OCR.
    """
    if fitz is None:
        return ""

    documento = fitz.open(caminho_pdf)
    try:
        textos = []
        texto_total = []

        for pagina in documento:
            texto = pagina.get_text("text") or ""
            texto = _normalizar_texto(texto)
            if texto:
                textos.append(texto)
                texto_total.append(texto)

        combinado = "\n\n".join(textos).strip()
        if len(combinado) >= 120:
            return combinado

        # Fallback OCR por imagem renderizada
        imagens = []
        for pagina in documento:
            pix = pagina.get_pixmap(dpi=300, alpha=False)
            if Image is None:
                continue
            imagem = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            imagens.append(imagem)

        if imagens and pytesseract is not None:
            ocr_pages = []
            for imagem in imagens:
                try:
                    ocr_pages.append(_ocr_imagem(imagem))
                except Exception as exc:
                    logger.warning("Falha ao aplicar OCR em página do PDF: %s", exc)
            return _normalizar_texto("\n\n".join(ocr_pages))

        return combinado
    finally:
        documento.close()


def _extrair_texto_pdf_pdf2image(caminho_pdf: str) -> str:
    """
    Fallback para PDF quando PyMuPDF não estiver disponível.
    Requer pdf2image e, em geral, poppler no sistema.
    """
    if convert_from_path is None:
        return ""

    if Image is None:
        raise ImportError("Pillow não está disponível para processar imagens de PDF.")

    paginas = convert_from_path(caminho_pdf, dpi=300)
    textos = []
    for pagina in paginas:
        try:
            textos.append(_ocr_imagem(pagina))
        except Exception as exc:
            logger.warning("Falha ao aplicar OCR em página do PDF: %s", exc)
    return _normalizar_texto("\n\n".join(textos))


def _extrair_texto_imagem(caminho_imagem: str) -> str:
    """Extrai texto de arquivo de imagem comum."""
    if Image is None:
        raise ImportError("Pillow não está disponível para abrir imagens.")

    with Image.open(caminho_imagem) as imagem:
        return _ocr_imagem(imagem)


def extrair_texto_do_arquivo(caminho_arquivo: str) -> str:
    """
    Extrai texto de PDF ou imagem.

    Retorna string vazia quando a extração falhar, sem interromper o bot.
    """
    try:
        if not caminho_arquivo:
            return ""

        caminho = Path(caminho_arquivo)
        if not caminho.exists():
            logger.warning("Arquivo não encontrado: %s", caminho_arquivo)
            return ""

        extensao = caminho.suffix.lower()

        if extensao == ".pdf":
            texto = _extrair_texto_pdf_pymupdf(str(caminho))
            if texto.strip():
                return texto

            texto = _extrair_texto_pdf_pdf2image(str(caminho))
            return texto.strip()

        # Qualquer outro formato é tratado como imagem.
        texto = _extrair_texto_imagem(str(caminho))
        return texto.strip()

    except Exception as exc:
        logger.exception("Erro na extração OCR de %s: %s", caminho_arquivo, exc)
        return ""


def extrair_texto_imagem(caminho_imagem: str) -> str:
    """Alias público para imagens."""
    return extrair_texto_do_arquivo(caminho_imagem)


def extrair_texto_pdf(caminho_pdf: str) -> str:
    """Alias público para PDF."""
    return extrair_texto_do_arquivo(caminho_pdf)


__all__ = [
    "extrair_texto_do_arquivo",
    "extrair_texto_imagem",
    "extrair_texto_pdf",
]


if __name__ == "__main__":  # pragma: no cover
    import sys

    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 2:
        print("Uso: python -m core.bot_ocr <arquivo.pdf|imagem>")
        raise SystemExit(1)

    caminho = sys.argv[1]
    print(extrair_texto_do_arquivo(caminho))
