#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Motor documental do Previdenciário.
Cópia adaptada dos utilitários genéricos do core/bot.py (Cível), pois core/bot.py
NÃO pode ser importado (trava PID no import). Dívida registrada: quando o padrão
se provar em 3 kits, extrair para camada compartilhada.
"""
import os, sys, re, json, time, shutil, asyncio, logging, zipfile, requests
from pathlib import Path
from typing import Any, Dict
from dotenv import load_dotenv

load_dotenv()
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False; cv2 = None

from services.ocr_router import extrair_texto as extrair_texto_do_arquivo  # v0.2 GLM-OCR

logger = logging.getLogger(__name__)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL_PREV", "qwen2.5:3b-instruct-q4_K_M")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
BASE_TEMP = ROOT / "temp_prev"

CAMPOS_PADRAO = {"nome": "", "cpf": "", "data_nascimento": "", "endereco": "",
                 "email": "", "nacionalidade": "brasileira",
                 "estado_civil": "", "profissao": ""}
CAMPOS_EXIBICAO = {"nome": "👤 Nome", "cpf": "🆔 CPF", "data_nascimento": "🎂 Nascimento",
                   "endereco": "📍 Endereço", "email": "📧 E-mail",
                   "nacionalidade": "🌎 Nacionalidade", "estado_civil": "💍 Estado Civil",
                   "profissao": "💼 Profissão"}
CAMPO_POR_CALLBACK = {"edit_nome": "nome", "edit_cpf": "cpf", "edit_data_nascimento": "data_nascimento",
                      "edit_endereco": "endereco", "edit_email": "email",
                      "edit_nacionalidade": "nacionalidade", "edit_estado_civil": "estado_civil",
                      "edit_profissao": "profissao"}

def limpar_nome(texto):
    if not texto: return ""
    texto = re.sub(r"[0-9]", "", texto)
    texto = re.sub(r"[^\w\sÀ-ÿ]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    lixo = {"DOCUMENTO", "AUXILIAR", "NOTA", "FISCAL", "ENERGIA", "ELETRICA", "ELÉTRICA",
            "LIGHT", "CENTRO", "BRASIL", "REPUBLICA", "REPÚBLICA", "INSS", "BENEFICIO", "BENEFÍCIO"}
    palavras = [p for p in texto.split() if p.upper() not in lixo and len(p) > 1]
    return " ".join(palavras[:6]).upper() if len(palavras) >= 2 else (palavras[0].upper() if palavras else "")

TOKENS_EMPRESA = ("COMPANHIA", "CIA.", "CIA ", "LTDA", "S.A.", "S/A", "ENERGIA",
                  "ELÉTRICA", "ELETRICA", "BANCO", "SEGURADORA", "TELECOM")
def nome_parece_empresa(nome):
    n = (nome or "").upper()
    return any(t in n for t in TOKENS_EMPRESA)

def formatar_cpf(cpf):
    cpf = re.sub(r"\D", "", str(cpf))
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}" if len(cpf) == 11 else cpf

def extrair_json_de_texto(texto):
    if not texto: return {}
    texto = re.sub(r"```json\s*|```", "", texto, flags=re.IGNORECASE)
    match = re.search(r"\{.*\}", texto, re.DOTALL)
    if not match: return {}
    try: return json.loads(match.group(0))
    except Exception: return {}

def limpar_temporarios(*paths):
    for p in paths:
        if not p: continue
        try:
            p = Path(p)
            if p.exists(): p.unlink()
        except Exception: pass

def validar_arquivo_entrada(caminho):
    try:
        p = Path(caminho)
        return p.exists() and p.stat().st_size >= 1000
    except Exception: return False

def normalizar_imagem_para_ocr(origem, destino):
    try:
        o, d = Path(origem), Path(destino)
        if not o.exists(): return origem
        if CV2_AVAILABLE and o.suffix.lower() not in {".pdf", ".doc", ".docx"}:
            img = cv2.imread(str(o))
            if img is None:
                shutil.copy2(origem, destino); return destino
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
            cv2.imwrite(str(d), gray); return destino
        shutil.copy2(origem, destino); return destino
    except Exception: return origem

def corrigir_docx(caminho):
    try:
        orig = Path(caminho)
        if not orig.exists(): return caminho
        novo = str(orig).replace(".docx", "_fix.docx")
        with zipfile.ZipFile(orig, 'r') as zin, zipfile.ZipFile(novo, 'w', zipfile.ZIP_DEFLATED) as zout:
            seen = set()
            for item in zin.infolist():
                if item.filename not in seen:
                    seen.add(item.filename)
                    zout.writestr(item, zin.read(item.filename))
        return novo
    except Exception as exc:
        logging.warning("Falha ao corrigir DOCX, usando original: %s", exc)
        return caminho

def localizar_template_prev(*nomes):
    candidatos = []
    for nome in nomes:
        candidatos += [ROOT / "services" / "templates" / "previdenciario" / nome,
                       ROOT / "templates" / "previdenciario" / nome,
                       Path.cwd() / "templates" / "previdenciario" / nome]
    for c in candidatos:
        if c.exists(): return str(c)
    for nome in nomes:
        for f in (ROOT / "services").rglob(nome):
            if f.is_file(): return str(f)
    raise FileNotFoundError(f"Template previdenciário não encontrado: {', '.join(nomes)}")

async def extrair_com_llm_local(texto_ocr, chat_id=0):
    if not texto_ocr: return {}
    inicio = time.time()
    prompt = f"""
Analise o texto OCR de um documento brasileiro (RG, CNH, fatura, conta) e extraia APENAS os dados da PESSOA FÍSICA titular/cliente.
Texto OCR:
{texto_ocr[:2500]}
Regras críticas:
1. nome: pessoa física titular/cliente. NUNCA razão social (contém COMPANHIA/CIA/LTDA/S.A./S/A/ENERGIA/BANCO). Em CNH use o campo NOME/NAME/NOMBRE; NUNCA filiação (pai/mãe).
2. cpf: somente número rotulado como CPF, 11 dígitos. NUNCA código de barras, linha digitável ou nº de registro.
3. data_nascimento: somente data rotulada NASC/NASCIMENTO, DD/MM/AAAA.
4. endereco: endereço completo do titular/cliente, absorvendo CEP.
5. profissao: somente se rotulada; não deduza.
Retorne EXCLUSIVAMENTE um JSON válido (use null se não encontrar):
{{"nome": ..., "cpf": ..., "data_nascimento": ..., "endereco": ...,
"email": ..., "nacionalidade": ..., "estado_civil": ..., "profissao": ...}}
Responda APENAS JSON."""
    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
               "format": "json", "options": {"temperature": 0.1, "num_predict": 2048}}
    try:
        resp = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=45)
        resp.raise_for_status()
        dados = extrair_json_de_texto(resp.json().get("response", ""))
        if dados.get("nome"): dados["nome"] = limpar_nome(str(dados["nome"]))
        if dados.get("cpf"): dados["cpf"] = re.sub(r"\D", "", str(dados["cpf"]))[:11]
        if dados.get("email"):
            e = str(dados["email"]).strip()
            dados["email"] = e if re.match(r"^[\w.\-+]+@[\w.\-]+\.\w+$", e) else None
        logger.info("⚡ Extração local: %.2fs | chat %s", time.time() - inicio, chat_id)
        return {k: v for k, v in dados.items() if v not in (None, "", "null")}
    except requests.exceptions.Timeout:
        logger.warning("⏱️ Timeout Ollama - fallback regex"); return {}
    except requests.exceptions.ConnectionError:
        logger.error("❌ Ollama indisponível em %s", OLLAMA_URL); return {"_erro_llm": True}
    except Exception as exc:
        logger.error("❌ Erro extração local: %s", exc); return {}

async def extrair_com_regex(texto_ocr):
    dados = {}
    m = re.search(r"(?:NOME|NOME DO TITULAR)\s*[:\-]?\s*([A-ZÀ-Ü\s]{5,})", texto_ocr, re.IGNORECASE)
    if not m: m = re.search(r"\b([A-ZÀ-Ü]{2,}(?:\s+[A-ZÀ-Ü]{2,}){1,5})\b", texto_ocr)
    if m: dados["nome"] = limpar_nome(m.group(1))
    m = re.search(r"\d{3}\.\d{3}\.\d{3}-\d{2}|\b\d{11}\b", texto_ocr)
    if m: dados["cpf"] = re.sub(r"\D", "", m.group(0))
    m = re.search(r"(?:NASC(?:IMENTO)?|DATA\s+DE\s+NASC(?:IMENTO)?)[^\d]*(\d{2}/\d{2}/\d{4})", texto_ocr, re.IGNORECASE)
    if m: dados["data_nascimento"] = m.group(1)
    m = re.search(r"(?:RUA|AV|AVENIDA|ESTRADA|ALAMEDA|TRAVESSA)[^\n]{10,}", texto_ocr, re.IGNORECASE)
    if m: dados["endereco"] = m.group(0).strip()
    m = re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", texto_ocr)
    if m: dados["email"] = m.group(0).strip()
    return dados

async def processar_documento(caminho_arquivo, chat_id=0):
    if not os.path.exists(caminho_arquivo): return {}
    texto_raw = await asyncio.to_thread(extrair_texto_do_arquivo, caminho_arquivo)
    if not texto_raw: return {}
    dados = await extrair_com_llm_local(texto_raw, chat_id=chat_id) or {}
    for k, v in (await extrair_com_regex(texto_raw)).items():
        if v and not dados.get(k): dados[k] = v
    if dados.get("nome"): dados["nome"] = limpar_nome(str(dados["nome"]))
    if nome_parece_empresa(dados.get("nome")): dados.pop("nome", None)
    if str(dados.get("profissao", "")).strip().lower() in ("energia", "eletrica", "elétrica"):
        dados.pop("profissao", None)
    if dados.get("cpf"): dados["cpf"] = re.sub(r"\D", "", str(dados["cpf"]))
    return dados
