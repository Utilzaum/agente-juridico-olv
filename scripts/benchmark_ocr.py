#!/usr/bin/env python3
import sys, time
from pathlib import Path
import sys as _s; _s.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.ocr_router import extrair_texto
from core.bot_ocr import extrair_texto_do_arquivo
for f in sys.argv[1:]:
    t0 = time.time(); a = extrair_texto(f); t1 = time.time()
    b = extrair_texto_do_arquivo(f); t2 = time.time()
    print(f"\n=== {Path(f).name}\n--- ROUTER/GLM ({t1-t0:.1f}s):\n{a[:700]}\n--- TESSERACT ({t2-t1:.1f}s):\n{b[:700]}")
