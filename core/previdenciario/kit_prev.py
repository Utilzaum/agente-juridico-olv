#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kit Previdenciário: 4 documentos, render docxtpl + PDF via perfil LibreOffice isolado."""
import io, re, sys, asyncio, logging, threading
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from docxtpl import DocxTemplate
from core.previdenciario import engine_prev as eng
from services.conversor_pdf import converter_para_pdf  # perfil /tmp/libreoffice → não briga com o Cível

logger = logging.getLogger(__name__)
_LIBRE_LOCK = threading.Lock()  # serializa só dentro DESTE processo

def _converter_com_lock(caminho):
    """Lock DENTRO da thread: nunca bloqueia o event loop."""
    with _LIBRE_LOCK:
        return converter_para_pdf(caminho)

DOCUMENTOS_KIT_PREV = [
    ("PROCURACAO",        "procuracao_previdenciaria.docx",        "Procuração Previdenciária"),
    ("HIPOSSUFICIENCIA",  "declaracao_de_hipossuficiencia.docx",   "Declaração de Hipossuficiência"),
    ("RENUNCIA_TETO",     "renuncia_teto_juizado.docx",            "Renúncia ao Teto (Juizado)"),
    ("CONTRATO_HONORARIOS","contrato_honorarios_previdenciario.docx","Contrato de Honorários"),
]

def rotulo_doc(tipo): return next((r[2] for r in DOCUMENTOS_KIT_PREV if r[0] == tipo), tipo)

def garantir_pastas(): eng.BASE_TEMP.mkdir(parents=True, exist_ok=True)

def contexto_kit_prev(dados):
    return {"nome": dados.get("nome", ""), "cpf": eng.formatar_cpf(dados.get("cpf", "")),
            "data_nascimento": dados.get("data_nascimento", ""), "endereco": dados.get("endereco", ""),
            "email": dados.get("email", ""), "nacionalidade": dados.get("nacionalidade", "brasileira"),
            "estado_civil": dados.get("estado_civil", ""), "profissao": dados.get("profissao", ""),
            "data": datetime.now().strftime("%d/%m/%Y")}

async def _gerar_documento(dados, tipo, nome_template):
    res = {"tipo": tipo, "template": nome_template, "caminho": None, "ok": False}
    doc = DocxTemplate(eng.localizar_template_prev(nome_template))
    ctx = contexto_kit_prev(dados)
    doc.render(ctx)
    nome = re.sub(r"[^\w\s]", "", ctx.get("nome", "CLIENTE")).strip().replace(" ", "_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho_docx = eng.BASE_TEMP / f"{nome}_{tipo}_{ts}.docx"
    buf = io.BytesIO(); doc.save(buf); caminho_docx.write_bytes(buf.getvalue())
    corrigido = eng.corrigir_docx(str(caminho_docx))
    pdf = None
    try: pdf = await asyncio.to_thread(_converter_com_lock, corrigido)
    except Exception as exc: logger.warning("⚠️ PDF falhou (%s): %s", tipo, exc)
    if pdf and Path(pdf).exists():
        eng.limpar_temporarios(caminho_docx, corrigido)
        res["caminho"], res["ok"] = pdf, True
    elif Path(corrigido).exists():  # fallback: entrega docx a entregar nada
        eng.limpar_temporarios(caminho_docx)
        res["caminho"], res["ok"] = corrigido, True
    else:
        eng.limpar_temporarios(caminho_docx, corrigido)
    return res

async def gerar_kit_prev(dados):
    garantir_pastas()
    return list(await asyncio.gather(*[
        _gerar_documento(dados, t, tpl) for t, tpl, _ in DOCUMENTOS_KIT_PREV]))
