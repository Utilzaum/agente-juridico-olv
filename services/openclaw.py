# versão simplificada robusta

import pyautogui
import subprocess
import time
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def converter_para_pdf_com_openclaw(caminho_docx: str):
    caminho = Path(caminho_docx).resolve()
    pdf = caminho.with_suffix(".pdf")

    subprocess.Popen(["libreoffice", "--writer", str(caminho)])

    time.sleep(5)

    # foca janela
    resultado = subprocess.run(
        ["xdotool", "search", "--onlyvisible", "--class", "libreoffice"],
        capture_output=True, text=True
    )

    window_id = resultado.stdout.strip().split("\n")[0]
    subprocess.run(["wmctrl", "-i", "-a", window_id])

    time.sleep(2)

    pyautogui.hotkey("ctrl", "shift", "e")
    time.sleep(3)
    pyautogui.press("enter")

    for _ in range(20):
        if pdf.exists():
            return str(pdf)
        time.sleep(1)

    raise RuntimeError("PDF não gerado")
