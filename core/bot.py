#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot Executor Jurídico - Kit Inicial (OLLAMA LOCAL)
Versão com UI conversacional responsiva, cadastro unificado e persistência em SQLite
"""
import os, sys, asyncio, atexit, json, logging, re, shutil, time, zipfile, sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx
import requests
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CallbackContext, CommandHandler, ContextTypes,
    ConversationHandler, MessageHandler, filters, CallbackQueryHandler,
)
from telegram.request import HTTPXRequest
from telegram.error import NetworkError, TimedOut

# ✅ IMPORTS DA UI
from core.ui.cards import card_cliente, card_preview, card_sucesso, card_erro
from core.ui.keyboards import get_correction_keyboard, get_preview_keyboard
from core.ui.progress import format_progress

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    cv2 = None

try:
    from docxtpl import DocxTemplate
    DOCXTPL_AVAILABLE = True
except ImportError:
    DOCXTPL_AVAILABLE = False
    DocxTemplate = None

from core.bot_ocr import extrair_texto_do_arquivo

# =========================
# 🔒 LOCK COM VALIDAÇÃO DE PID
# =========================
LOCK = "/tmp/bot_executor.lock"

def is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False

if os.path.exists(LOCK):
    try:
        with open(LOCK, "r") as f:
            old_pid = int(f.read().strip())
        if is_pid_alive(old_pid):
            print(f"⚠️ Instância já rodando (PID {old_pid}).")
            sys.exit(1)
        else:
            print("🔄 PID órfão detectado. Removendo lock...")
            os.remove(LOCK)
    except (ValueError, FileNotFoundError):
        os.remove(LOCK)

with open(LOCK, "w") as f:
    f.write(str(os.getpid()))

@atexit.register
def remover_lock():
    try: os.remove(LOCK)
    except Exception: pass

# =========================
# BANCO DE DADOS (CLIENTES)
# =========================
def get_base_dir() -> Path:
    current = Path(__file__).resolve()
    for parent in [current.parent, *current.parents]:
        if parent.name == "agente_juridico": return parent
    return current.parent

BASE_DIR = get_base_dir()
DB_PATH = BASE_DIR / "clientes.db"

def init_db():
    """Inicializa o banco de dados para persistir o cadastro dos clientes"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS clientes
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      cpf TEXT UNIQUE,
                      nome TEXT,
                      data_nascimento TEXT,
                      endereco TEXT,
                      email TEXT,
                      profissao TEXT,
                      estado_civil TEXT,
                      nacionalidade TEXT,
                      area_juridica TEXT,
                      criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()
        conn.close()
        logger.info(f"✅ Banco de dados inicializado em {DB_PATH}")
    except Exception as e:
        logger.error(f"Erro ao inicializar banco: {e}")

def salvar_cliente(dados: dict) -> bool:
    """Salva ou atualiza o cadastro do cliente no banco"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO clientes 
                     (cpf, nome, data_nascimento, endereco, email, profissao, estado_civil, nacionalidade, area_juridica)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (dados.get('cpf'), dados.get('nome'), dados.get('data_nascimento'),
                   dados.get('endereco'), dados.get('email'), dados.get('profissao'),
                   dados.get('estado_civil'), dados.get('nacionalidade'), dados.get('area_juridica')))
        conn.commit()
        conn.close()
        logger.info(f"✅ Cliente {dados.get('nome')} salvo no banco.")
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar cliente no banco: {e}")
        return False

# =========================
# CORREÇÃO DE DOCX E PDF
# =========================
def corrigir_docx(caminho: str) -> str:
    try:
        caminho_orig = Path(caminho)
        if not caminho_orig.exists(): return caminho
        novo_caminho = str(caminho_orig).replace(".docx", "_fix.docx")
        with zipfile.ZipFile(caminho_orig, 'r') as zin:
            with zipfile.ZipFile(novo_caminho, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
                seen = set()
                for item in zin.infolist():
                    if item.filename not in seen:
                        seen.add(item.filename)
                        zout.writestr(item, zin.read(item.filename))
        return novo_caminho
    except Exception as exc:
        logging.warning("Falha ao corrigir DOCX, usando original: %s", exc)
        return caminho

import threading

# 🔒 LibreOffice não suporta instâncias simultâneas no mesmo perfil.
_LIBREOFFICE_LOCK = threading.Lock()

def _tentar_conversao_once(caminho_docx: str) -> Optional[str]:
    import subprocess
    try:
        docx_path = Path(caminho_docx)
        outdir = docx_path.parent
        res1 = subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "odt", str(docx_path), "--outdir", str(outdir)],
            capture_output=True, text=True, timeout=60
        )
        if res1.returncode != 0:
            res_fallback = subprocess.run(
                ["libreoffice", "--headless", "--convert-to", "pdf", str(docx_path), "--outdir", str(outdir)],
                capture_output=True, text=True, timeout=60
            )
            if res_fallback.returncode != 0: return None
            pdf_path = docx_path.with_suffix(".pdf")
            return str(pdf_path) if pdf_path.exists() else None
        
        caminho_odt = docx_path.with_suffix(".odt")
        if not caminho_odt.exists(): return None
        res2 = subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pdf", str(caminho_odt), "--outdir", str(outdir)],
            capture_output=True, text=True, timeout=60
        )
        try: caminho_odt.unlink()
        except Exception: pass
        if res2.returncode != 0: return None
        pdf_path = docx_path.with_suffix(".pdf")
        return str(pdf_path) if pdf_path.exists() else None
    except Exception as exc:
        logging.error("Erro na conversão DOCX/PDF: %s", exc)
        return None

def converter_docx_para_pdf(caminho_docx: str, tentativas: int = 3) -> Optional[str]:
    # Conversão com lock + retry (nunca concorre com outra instância).
    for tentativa in range(1, tentativas + 1):
        with _LIBREOFFICE_LOCK:
            pdf = _tentar_conversao_once(caminho_docx)
        if pdf:
            return pdf
        logger.warning("⚠️ Conversão PDF falhou (tentativa %d/%d): %s",
                       tentativa, tentativas, caminho_docx)
        time.sleep(2 * tentativa)
    return None

# =========================
# CONFIGURAÇÃO
# =========================
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "hf.co/unsloth/LFM2.5-1.2B-Instruct-GGUF:Q4_K_M")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
ALLOW_EXTERNAL_FALLBACK = os.getenv("ALLOW_EXTERNAL_FALLBACK", "false").lower() == "true"

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_TEMP_DIR = BASE_DIR / "temp"
DIR_ORIGINAL = BASE_TEMP_DIR / "original"
DIR_PROCESSADO = BASE_TEMP_DIR / "processado"

def garantir_pastas() -> None:
    BASE_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    DIR_ORIGINAL.mkdir(parents=True, exist_ok=True)
    DIR_PROCESSADO.mkdir(parents=True, exist_ok=True)

def verificar_ollama() -> bool:
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
        return resp.status_code == 200
    except Exception: return False

def log_desempenho(inicio: float, modelo: str, chat_id: int) -> None:
    duracao = time.time() - inicio
    logger.info("⚡ Extração local: %.2fs | Modelo: %s | Chat: %s", duracao, modelo, chat_id)

# =========================
# ESTADO DA CONVERSA
# =========================
AGUARDANDO_DOCUMENTO = 0
AGUARDANDO_CORRECAO = 1

# Modelo de dados unificado (Sem RG, Sem CEP independente)
CAMPOS_PADRAO: Dict[str, str] = {
    "nome": "", "cpf": "", "data_nascimento": "", "endereco": "",
    "email": "", "nacionalidade": "brasileira",
    "estado_civil": "", "profissao": "", "area_juridica": ""
}

CAMPOS_EXIBICAO: Dict[str, str] = {
    "nome": "👤 Nome", "cpf": "🆔 CPF", "data_nascimento": "🎂 Data de Nascimento",
    "endereco": "📍 Endereço", "email": "📧 E-mail",
    "nacionalidade": "🌎 Nacionalidade", "estado_civil": "💍 Estado Civil",
    "profissao": "💼 Profissão", "area_juridica": "⚖️ Área Jurídica"
}

CAMPO_POR_CALLBACK = {
    "edit_nome": "nome", "edit_cpf": "cpf", "edit_data_nascimento": "data_nascimento",
    "edit_endereco": "endereco", "edit_email": "email",
    "edit_nacionalidade": "nacionalidade", "edit_estado_civil": "estado_civil",
    "edit_profissao": "profissao", "edit_area_juridica": "area_juridica"
}

def get_editing_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Cancelar edição", callback_data="cancel_edit")]
    ])

_user_sessions: Dict[int, Dict[str, Any]] = {}

def get_user_data(chat_id: int) -> Dict[str, Any]:
    if chat_id not in _user_sessions:
        _user_sessions[chat_id] = {
            "dados": dict(CAMPOS_PADRAO),
            "confidence": None,
        }
    return _user_sessions[chat_id]

def reset_user_data(chat_id: int) -> None:
    _user_sessions[chat_id] = {
        "dados": dict(CAMPOS_PADRAO),
        "confidence": None,
    }

# =========================
# UTILITÁRIOS
# =========================
def limpar_nome(texto: str) -> str:
    if not texto: return ""
    texto = re.sub(r"[0-9]", "", texto)
    texto = re.sub(r"[^\w\sÀ-ÿ]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    lixo = {"DOCUMENTO", "AUXILIAR", "NOTA", "FISCAL", "ENERGIA", "ELETRICA", "ELÉTRICA",
            "LIGHT", "CENTRO", "BRASIL", "REPUBLICA", "REPÚBLICA"}
    palavras = [p for p in texto.split() if p.upper() not in lixo and len(p) > 1]
    if len(palavras) >= 2: return " ".join(palavras[:6]).upper()
    if len(palavras) == 1: return palavras[0].upper()
    return ""

def formatar_cpf(cpf: str) -> str:
    cpf = re.sub(r"\D", "", str(cpf))
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}" if len(cpf) == 11 else cpf

def extrair_json_de_texto(texto: str) -> dict:
    if not texto: return {}
    texto = re.sub(r"```json\s*|```", "", texto, flags=re.IGNORECASE)
    match = re.search(r"\{.*\}", texto, re.DOTALL)
    if not match: return {}
    try: return json.loads(match.group(0))
    except Exception: return {}

def limpar_temporarios(*paths: Optional[Path | str]) -> None:
    for p in paths:
        if not p: continue
        try:
            path = Path(p)
            if path.exists(): path.unlink()
        except Exception: pass

def validar_arquivo_entrada(caminho: str) -> bool:
    try:
        path = Path(caminho)
        return path.exists() and path.stat().st_size >= 1000
    except Exception: return False

def normalizar_imagem_para_ocr(origem: str, destino: str) -> str:
    try:
        origem_path, destino_path = Path(origem), Path(destino)
        if not origem_path.exists(): return origem
        if CV2_AVAILABLE and origem_path.suffix.lower() not in {".pdf", ".doc", ".docx"}:
            img = cv2.imread(str(origem_path))
            if img is None:
                shutil.copy2(origem, destino); return destino
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
            cv2.imwrite(str(destino_path), gray); return destino
        shutil.copy2(origem, destino); return destino
    except Exception: return origem

def localizar_template(*nomes: str) -> str:
    candidatos: List[Path] = []
    for nome in nomes:
        candidatos.extend([
            BASE_DIR / "templates" / nome,
            BASE_DIR / "core" / "templates" / nome,
            BASE_DIR / "services" / "templates" / nome,
            Path.cwd() / "templates" / nome
        ])
    for cand in candidatos:
        if cand.exists(): return str(cand)
    for nome in nomes:
        for encontrado in BASE_DIR.rglob(nome):
            if encontrado.is_file(): return str(encontrado)
    raise FileNotFoundError(f"Template não encontrado. Tentado: {', '.join(nomes)}")

def mensagem_boas_vindas() -> str:
    return (
        "━━━━━━━━━━━━━━━━━━\n"
        "⚖️ <b>BOT JURÍDICO PRO</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🤖 <b>100% Local com IA</b>\n"
        "📸 <b>Envie:</b>\n"
        "• Foto do RG/CNH\n"
        "• PDF do documento\n"
        "• Comprovante de residência\n"
        "✨ <b>Extração automática + correção fácil</b>\n"
        "━━━━━━━━━━━━━━━━━━"
    )

# =========================
# 🧠 INTERPRETADOR INTELIGENTE
# =========================
def interpretar_input_livre(texto: str) -> dict:
    if not texto or not texto.strip(): return {}
    texto_original = texto.strip()
    texto = texto_original.lower()
    resultado = {}
    
    if re.match(r"^[\w.\-+]+@[\w.\-]+\.\w+$", texto):
        resultado["email"] = texto_original
        return resultado
        
    tokens = re.split(r'[\s,]+| e ', texto)
    tokens = [t.strip() for t in tokens if t.strip()]
    
    nacionalidades_map = {
        "brasileiro": "brasileiro", "brasileira": "brasileira",
        "argentino": "argentino", "argentina": "argentina",
        "português": "português", "portuguesa": "portuguesa",
        "americano": "americano", "americana": "americana",
    }
    estados_civis_map = {
        "solteiro": "solteiro", "solteira": "solteira",
        "casado": "casado", "casada": "casada",
        "divorciado": "divorciado", "divorciada": "divorciada",
        "viuvo": "viúvo", "viuva": "viúva",
        "uniao estavel": "união estável", "união estável": "união estável",
    }
    profissoes_comuns = {
        "autonomo": "autônomo", "autônomo": "autônomo",
        "do lar": "do lar", "engenheiro": "engenheiro",
        "advogado": "advogado", "medico": "médico",
        "professor": "professor", "estudante": "estudante",
        "desempregado": "desempregado", "aposentado": "aposentado",
    }
    
    nacionalidade_encontrada = None
    estado_civil_encontrado = None
    profissao_tokens = []
    
    for token in tokens:
        token_limpo = token.lower().rstrip('.,;')
        if token_limpo in nacionalidades_map: nacionalidade_encontrada = nacionalidades_map[token_limpo]
        if token_limpo in estados_civis_map: estado_civil_encontrado = estados_civis_map[token_limpo]
        if token_limpo in profissoes_comuns: profissao_tokens.append(profissoes_comuns[token_limpo])
        
    if nacionalidade_encontrada: resultado["nacionalidade"] = nacionalidade_encontrada
    if estado_civil_encontrado: resultado["estado_civil"] = estado_civil_encontrado
    if profissao_tokens: resultado["profissao"] = " ".join(profissao_tokens)
    
    if not resultado and len(tokens) <= 3 and not any(c.isdigit() for c in texto):
        if not any(p in texto for p in ["rua", "avenida", "av", "nº", "numero", "número"]):
            resultado["profissao"] = texto_original.lower()
            
    return resultado

# =========================
# EXTRAÇÃO COM OLLAMA LOCAL
# =========================
async def extrair_com_llm_local(texto_ocr: str, chat_id: int = 0) -> Dict[str, Any]:
    if not texto_ocr: return {}
    inicio = time.time()
    
    prompt = f"""
Analise o texto OCR de um documento brasileiro e extraia APENAS os dados do TITULAR.
Texto OCR:
{texto_ocr[:2500]}
Retorne EXCLUSIVAMENTE um JSON válido com estes campos (use null se não encontrar):
{{
"nome": "nome completo do titular",
"cpf": "apenas números, 11 dígitos",
"data_nascimento": "DD/MM/AAAA",
"endereco": "endereço completo incluindo CEP, rua, número, bairro, cidade, UF",
"email": "e-mail ou null",
"nacionalidade": "nacionalidade ou null",
"estado_civil": "estado civil ou null",
"profissao": "profissão ou null"
}}
Regras críticas:
1. data_nascimento deve ser de nascimento.
2. CPF deve ter exatamente 11 dígitos numéricos.
3. O endereço deve ser completo, absorvendo o CEP.
4. Responda APENAS com JSON, sem markdown, sem explicações.
""".strip()
    
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1, "num_predict": 2048}
    }
    try:
        response = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=45)
        response.raise_for_status()
        content = response.json().get("response", "")
        dados = extrair_json_de_texto(content)
        
        if dados.get("nome"): dados["nome"] = limpar_nome(str(dados["nome"]))
        if dados.get("cpf"): dados["cpf"] = re.sub(r"\D", "", str(dados["cpf"]))[:11]
        if dados.get("email"):
            email = str(dados["email"]).strip()
            dados["email"] = email if re.match(r"^[\w.\-+]+@[\w.\-]+\.\w+$", email) else None
            
        dados_filtrados = {k: v for k, v in dados.items() if v not in (None, "", "null")}
        log_desempenho(inicio, OLLAMA_MODEL, chat_id)
        return dados_filtrados
    except requests.exceptions.Timeout:
        logger.warning("⏱️ Timeout no Ollama - usando fallback regex")
        return {}
    except requests.exceptions.ConnectionError:
        logger.error("❌ Ollama indisponível em %s", OLLAMA_URL)
        return {"_erro_llm": True}
    except Exception as exc:
        logger.error("❌ Erro na extração local: %s", exc)
        return {}

async def extrair_com_regex(texto_ocr: str) -> Dict[str, Any]:
    dados: Dict[str, Any] = {}
    nome_match = re.search(r"(?:NOME|NOME DO TITULAR)\s*[:\-]?\s*([A-ZÀ-Ü\s]{5,})", texto_ocr, re.IGNORECASE)
    if nome_match:
        dados["nome"] = limpar_nome(nome_match.group(1))
    else:
        nome_match = re.search(r"\b([A-ZÀ-Ü]{2,}(?:\s+[A-ZÀ-Ü]{2,}){1,5})\b", texto_ocr)
        if nome_match:
            dados["nome"] = limpar_nome(nome_match.group(1))
            
    cpf_match = re.search(r"\d{3}\.\d{3}\.\d{3}-\d{2}|\b\d{11}\b", texto_ocr)
    if cpf_match:
        dados["cpf"] = re.sub(r"\D", "", cpf_match.group(0))
        
    nasc_match = re.search(r"(?:NASC(?:IMENTO)?|DATA\s+DE\s+NASC(?:IMENTO)?)[^\d]*(\d{2}/\d{2}/\d{4})", texto_ocr, re.IGNORECASE)
    if nasc_match:
        dados["data_nascimento"] = nasc_match.group(1)
        
    endereco_match = re.search(r"(?:RUA|AV|AVENIDA|ESTRADA|ALAMEDA|TRAVESSA)[^\n]{10,}", texto_ocr, re.IGNORECASE)
    if endereco_match:
        dados["endereco"] = endereco_match.group(0).strip()
        
    email_match = re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", texto_ocr)
    if email_match:
        dados["email"] = email_match.group(0).strip()
        
    return dados

# =========================
# PROCESSAMENTO PRINCIPAL
# =========================
async def processar_documento(caminho_arquivo: str, chat_id: int = 0) -> Dict[str, Any]:
    if not os.path.exists(caminho_arquivo): return {}
    texto_raw = await asyncio.to_thread(extrair_texto_do_arquivo, caminho_arquivo)
    if not texto_raw: return {}
    
    dados_llm = await extrair_com_llm_local(texto_raw, chat_id=chat_id)
    dados_regex = await extrair_com_regex(texto_raw)
    
    dados = dados_llm or {}
    for k, v in dados_regex.items():
        if v and not dados.get(k):
            dados[k] = v
            
    if dados.get("nome"): dados["nome"] = limpar_nome(str(dados["nome"]))
    if dados.get("cpf"): dados["cpf"] = re.sub(r"\D", "", str(dados["cpf"]))
    if dados.get("email"): dados["email"] = str(dados["email"]).strip()
    if dados.get("nacionalidade"): dados["nacionalidade"] = str(dados["nacionalidade"]).strip().lower()
    if dados.get("estado_civil"): dados["estado_civil"] = str(dados["estado_civil"]).strip().lower()
    if dados.get("profissao"): dados["profissao"] = str(dados["profissao"]).strip().lower()
    
    return dados

# =========================
# GERAÇÃO DOS DOCUMENTOS
# =========================
def contexto_kit(chat_id: int) -> Dict[str, str]:
    ud = get_user_data(chat_id)
    return {
        "nome": ud.get("dados", {}).get("nome", ""),
        "cpf": formatar_cpf(ud.get("dados", {}).get("cpf", "")),
        "endereco": ud.get("dados", {}).get("endereco", ""),
        "nacionalidade": ud.get("dados", {}).get("nacionalidade", "brasileira"),
        "estado_civil": ud.get("dados", {}).get("estado_civil", ""),
        "profissao": ud.get("dados", {}).get("profissao", ""),
        "email": ud.get("dados", {}).get("email", ""),
        "area_juridica": ud.get("dados", {}).get("area_juridica", "Direito Civil"),
        "data": datetime.now().strftime("%d/%m/%Y"),
    }

async def gerar_procuracao(chat_id: int) -> str:
    import io
    if not DOCXTPL_AVAILABLE: raise RuntimeError("docxtpl não está instalado")
    template_path = localizar_template("modelo_procuracao.docx")
    doc = DocxTemplate(template_path)
    doc.render(contexto_kit(chat_id))
    nome_cliente = re.sub(r"[^\w\s]", "", contexto_kit(chat_id).get("nome", "CLIENTE")).strip().replace(" ", "_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho_docx = BASE_TEMP_DIR / f"{nome_cliente}_PROCURACAO_{ts}.docx"
    buf = io.BytesIO()
    doc.save(buf)
    caminho_docx.write_bytes(buf.getvalue())
    caminho_docx_corrigido = corrigir_docx(str(caminho_docx))
    caminho_pdf = await asyncio.to_thread(converter_docx_para_pdf, caminho_docx_corrigido)
    limpar_temporarios(caminho_docx)
    if caminho_docx_corrigido != str(caminho_docx):
        limpar_temporarios(caminho_docx_corrigido)
    return caminho_pdf if caminho_pdf else str(caminho_docx)

async def gerar_hipossuficiencia(chat_id: int) -> str:
    import io
    if not DOCXTPL_AVAILABLE: raise RuntimeError("docxtpl não está instalado")
    template_path = localizar_template("modelo_hipossuficiencia.docx")
    doc = DocxTemplate(template_path)
    doc.render(contexto_kit(chat_id))
    nome_cliente = re.sub(r"[^\w\s]", "", contexto_kit(chat_id).get("nome", "CLIENTE")).strip().replace(" ", "_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho_docx = BASE_TEMP_DIR / f"{nome_cliente}_DECLARACAO_HIPOSSUFICIENCIA_{ts}.docx"
    buf = io.BytesIO()
    doc.save(buf)
    caminho_docx.write_bytes(buf.getvalue())
    caminho_docx_corrigido = corrigir_docx(str(caminho_docx))
    caminho_pdf = await asyncio.to_thread(converter_docx_para_pdf, caminho_docx_corrigido)
    limpar_temporarios(caminho_docx)
    if caminho_docx_corrigido != str(caminho_docx):
        limpar_temporarios(caminho_docx_corrigido)
    return caminho_pdf if caminho_pdf else str(caminho_docx)

async def gerar_contrato(chat_id: int) -> str:
    import io
    if not DOCXTPL_AVAILABLE: raise RuntimeError("docxtpl não está instalado")
    template_path = localizar_template("modelo_honorarios.docx")
    doc = DocxTemplate(template_path)
    doc.render(contexto_kit(chat_id))
    nome_cliente = re.sub(r"[^\w\s]", "", contexto_kit(chat_id).get("nome", "CLIENTE")).strip().replace(" ", "_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho_docx = BASE_TEMP_DIR / f"{nome_cliente}_CONTRATO_HONORARIOS_{ts}.docx"
    buf = io.BytesIO()
    doc.save(buf)
    caminho_docx.write_bytes(buf.getvalue())
    caminho_docx_corrigido = corrigir_docx(str(caminho_docx))
    caminho_pdf = await asyncio.to_thread(converter_docx_para_pdf, caminho_docx_corrigido)
    limpar_temporarios(caminho_docx)
    if caminho_docx_corrigido != str(caminho_docx):
        limpar_temporarios(caminho_docx_corrigido)
    return caminho_pdf if caminho_pdf else str(caminho_docx)

DOCUMENTOS_KIT = [
    ("PROCURACAO",                  "modelo_procuracao.docx",       "Procuração"),
    ("DECLARACAO_HIPOSSUFICIENCIA", "modelo_hipossuficiencia.docx", "Declaração de Hipossuficiência"),
    ("CONTRATO_HONORARIOS",         "modelo_honorarios.docx",       "Contrato de Honorários"),
]

def rotulo_doc(tipo: str) -> str:
    return next((r[2] for r in DOCUMENTOS_KIT if r[0] == tipo), tipo)

async def _gerar_documento(chat_id: int, tipo: str, nome_template: str) -> Dict[str, Any]:
    """Gera 1 documento do kit. Nunca retorna caminho inexistente: ok=False indica falha."""
    import io
    res = {"tipo": tipo, "template": nome_template, "caminho": None, "ok": False}
    if not DOCXTPL_AVAILABLE:
        raise RuntimeError("docxtpl não está instalado")
    doc = DocxTemplate(localizar_template(nome_template))
    doc.render(contexto_kit(chat_id))
    nome_cliente = re.sub(r"[^\w\s]", "", contexto_kit(chat_id).get("nome", "CLIENTE")).strip().replace(" ", "_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho_docx = BASE_TEMP_DIR / f"{nome_cliente}_{tipo}_{ts}.docx"
    buf = io.BytesIO()
    doc.save(buf)
    caminho_docx.write_bytes(buf.getvalue())
    caminho_docx_corrigido = corrigir_docx(str(caminho_docx))
    caminho_pdf = await asyncio.to_thread(converter_docx_para_pdf, caminho_docx_corrigido)
    if caminho_pdf:
        limpar_temporarios(caminho_docx, caminho_docx_corrigido)
        res["caminho"], res["ok"] = caminho_pdf, True
    elif Path(caminho_docx_corrigido).exists():
        # Fallback: entrega o .docx em vez de entregar nada
        limpar_temporarios(caminho_docx)
        res["caminho"], res["ok"] = caminho_docx_corrigido, True
    else:
        limpar_temporarios(caminho_docx, caminho_docx_corrigido)
    return res

async def gerar_kit_inicial(chat_id: int) -> List[Dict[str, Any]]:
    # O render (docxtpl) continua paralelo; só o LibreOffice é serializado pelo lock.
    return list(await asyncio.gather(*[
        _gerar_documento(chat_id, tipo, tpl) for tipo, tpl, _ in DOCUMENTOS_KIT
    ]))

# =========================
# 🔥 UI CONVERSACIONAL
# =========================
async def _atualizar_mensagem_viva(context: ContextTypes.DEFAULT_TYPE, chat_id: int,
                                   texto: str, reply_markup=None, parse_mode="HTML"):
    msg_id = context.user_data.get("correction_msg_id")
    try:
        if msg_id:
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=msg_id, text=texto,
                reply_markup=reply_markup, parse_mode=parse_mode
            )
        else:
            raise ValueError("Sem mensagem anterior")
    except Exception:
        nova_msg = await context.bot.send_message(
            chat_id=chat_id, text=texto, reply_markup=reply_markup, parse_mode=parse_mode
        )
        context.user_data["correction_msg_id"] = nova_msg.message_id

async def _mostrar_cartao_principal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ud = get_user_data(chat_id)
    card = card_cliente(ud["dados"], ud.get("confidence"))
    keyboard = get_correction_keyboard()
    await _atualizar_mensagem_viva(context, chat_id, card, keyboard)

async def _apagar_mensagem_usuario(update: Update):
    try:
        if update.message:
            await update.message.delete()
    except Exception:
        pass

# =========================
# HANDLERS TELEGRAM
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_html(mensagem_boas_vindas())

async def cmd_dados(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        chat_id = update.message.chat_id
        ud = get_user_data(chat_id)
        dados = ud.get("dados", {})
        if not any(dados.values()):
            await update.message.reply_text("📭 Nenhum dado cadastrado ainda.")
            return
        card = card_cliente(dados, ud.get("confidence"))
        await update.message.reply_html(card)

async def cmd_limpar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        chat_id = update.message.chat_id
        reset_user_data(chat_id)
        context.user_data.clear()
        await update.message.reply_html(card_sucesso("✨ Todos os dados foram apagados!"))

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message:
        msg_id = context.user_data.get("correction_msg_id")
        if msg_id:
            try: await context.bot.delete_message(update.message.chat_id, msg_id)
            except Exception: pass
        context.user_data.clear()
        await update.message.reply_text("❌ Operação cancelada.")
        return ConversationHandler.END

async def handle_documento(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.message
    if message is None: return ConversationHandler.END
    chat_id = message.chat_id
    context.user_data.clear()
    
    if message.document:
        file_obj = message.document
        file_name = getattr(file_obj, "file_name", "") or "documento"
        ext = Path(file_name).suffix.lower() or ".bin"
    elif message.photo:
        file_obj = message.photo[-1]
        ext = ".jpg"
    else:
        return ConversationHandler.END
        
    logger.info("📄 Novo documento recebido | Chat: %s | Ext: %s", chat_id, ext)
    
    status_msg = await message.reply_text(
        "🔍 <b>Analisando documento...</b>\n⏳ Processando OCR...", parse_mode="HTML"
    )
    
    path_original: Optional[Path] = None
    path_processado: Optional[Path] = None
    
    try:
        garantir_pastas()
        file_id = file_obj.file_id
        path_original = DIR_ORIGINAL / f"{file_id}_original{ext}"
        path_processado = DIR_PROCESSADO / f"{file_id}_processado{ext}"
        tg_file = await file_obj.get_file()
        await tg_file.download_to_drive(str(path_original))
        
        if not validar_arquivo_entrada(str(path_original)):
            raise ValueError("Arquivo de entrada inválido ou corrompido")
            
        await status_msg.edit_text(
            "🔍 <b>Analisando documento...</b>\n🤖 Extraindo dados com IA...", parse_mode="HTML"
        )
        
        caminho_para_ocr = str(path_original)
        if ext not in {".pdf", ".doc", ".docx"}:
            caminho_para_ocr = normalizar_imagem_para_ocr(str(path_original), str(path_processado))
            
        texto_raw = await asyncio.to_thread(extrair_texto_do_arquivo, caminho_para_ocr)
        if not texto_raw:
            await status_msg.delete()
            await message.reply_html(card_erro("❌ Não foi possível extrair texto do documento."))
            return ConversationHandler.END
            
        dados = await processar_documento(str(path_original), chat_id=chat_id)
        erro_llm = dados.pop("_erro_llm", False)
        
        if dados:
            ud = get_user_data(chat_id)
            campos_preenchidos = []
            for campo, valor in dados.items():
                if campo in CAMPOS_PADRAO and valor not in (None, ""):
                    ud["dados"][campo] = str(valor).strip()
                    campos_preenchidos.append(CAMPOS_EXIBICAO.get(campo, campo))
                    
            await status_msg.delete()
            
            status_text = f"✅ <b>Documento processado!</b>\n"
            status_text += f"📋 <b>{len(campos_preenchidos)} campos extraídos</b>\n"
            if erro_llm:
                status_text += "⚠️ IA local indisponível, usando extração básica.\n"
            status_text += "\n📝 <b>Revise os dados abaixo:</b>"
            await message.reply_html(status_text)
            
            ud["confidence"] = 0.85
            card = card_cliente(ud["dados"], ud["confidence"])
            keyboard = get_correction_keyboard()
            
            sent_msg = await message.reply_html(card, reply_markup=keyboard)
            context.user_data["correction_msg_id"] = sent_msg.message_id
            return AGUARDANDO_CORRECAO
        else:
            await status_msg.delete()
            await message.reply_text(
                "❌ <b>Não foi possível extrair dados automaticamente.</b>\n"
                "📸 <b>Sugestões:</b>\n"
                "• Envie uma foto mais nítida do documento\n"
                "• Tente com um PDF digitalizado\n"
                "• Ou digite os dados manualmente", parse_mode="HTML"
            )
            return ConversationHandler.END
            
    except Exception as exc:
        logger.exception("Erro ao processar documento")
        try: await status_msg.delete()
        except Exception: pass
        await message.reply_html(card_erro(f"❌ Erro ao processar: {str(exc)[:100]}"))
        return ConversationHandler.END
    finally:
        limpar_temporarios(path_original, path_processado)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = query.message.chat_id
    data = query.data
    ud = get_user_data(chat_id)
    
    # ===== CONFIRMAR DADOS COM VALIDAÇÕES =====
    if data == "confirm":
        dados = ud["dados"]
        erros = []
        
        # Validação de Nome
        if not dados.get("nome") or not dados.get("nome").strip():
            erros.append("👤 <b>Nome</b> é obrigatório.")
            
        # Validação e normalização de CPF
        cpf_raw = re.sub(r"\D", "", str(dados.get("cpf", "")))
        if len(cpf_raw) != 11:
            erros.append("🆔 <b>CPF</b> deve ter exatamente 11 dígitos.")
        else:
            dados["cpf"] = cpf_raw
            
        # Validação de Endereço
        if not dados.get("endereco") or not dados.get("endereco").strip():
            erros.append("📍 <b>Endereço</b> é obrigatório.")
            
        # Validação e normalização de E-mail
        email = str(dados.get("email", "")).strip()
        if not email or not re.match(r"^[\w.\-+]+@[\w.\-]+\.\w+$", email):
            erros.append("📧 <b>E-mail</b> inválido ou obrigatório.")
        else:
            dados["email"] = email

        if erros:
            erro_msg = "⚠️ <b>Dados incompletos ou inválidos:</b>\n\n" + "\n".join(erros)
            await _atualizar_mensagem_viva(context, chat_id, erro_msg, get_correction_keyboard())
            return

        # Salvando no banco de dados central
        salvar_cliente(dados)
        
        await query.answer("✅ Dados confirmados!")
        keyboard = get_preview_keyboard()
        preview_text = (
            card_preview(dados) +
            "\n✅ <b>Dados prontos!</b> Clique em 'Gerar Kit' para criar os documentos."
        )
        await _atualizar_mensagem_viva(context, chat_id, preview_text, keyboard)
        return
        
    # ===== GERAR KIT =====
    elif data == "generate_kit":
        await query.answer("🚀 Gerando documentos...")
        await _atualizar_mensagem_viva(
            context, chat_id,
            "🚀 <b>Gerando kit inicial...</b>\n⏳ Preparando documentos...", None
        )
        await cmd_kit(update, context)
        return
        
    # ===== EDITAR DADOS =====
    elif data == "edit_data":
        await query.answer("📝 Modo de edição")
        keyboard = get_correction_keyboard()
        edit_text = "✏️ <b>EDIÇÃO DE DADOS</b>\nSelecione o campo que deseja alterar:"
        await _atualizar_mensagem_viva(context, chat_id, edit_text, keyboard)
        return
        
    # ===== REEXTRAIR =====
    elif data == "reextract":
        await query.answer("📸 Envie um novo documento para reextrair", show_alert=True)
        return
        
    # ===== CANCELAR =====
    elif data == "cancel":
        await query.answer("Operação cancelada")
        try: await query.message.delete()
        except Exception: pass
        context.user_data.clear()
        return ConversationHandler.END
        
    # ===== CANCELAR EDIÇÃO DE CAMPO =====
    elif data == "cancel_edit":
        await query.answer("Edição cancelada")
        context.user_data.pop("campo_editando", None)
        await _mostrar_cartao_principal(update, context)
        return
    # ===== REGERAR DOCUMENTOS FALTANTES =====
    elif data == "regen_missing":
        pendentes = context.user_data.pop("docs_pendentes", [])
        if not pendentes:
            await query.answer("✅ Nada pendente.")
            return
        await query.answer("🔄 Regerando documentos...")
        await _atualizar_mensagem_viva(context, chat_id, "🔄 <b>Regerando documentos faltantes...</b>", None)
        retry = await asyncio.gather(*[
            _gerar_documento(chat_id, p["tipo"], p["template"]) for p in pendentes])
        enviados, ainda = await _enviar_documentos(retry, query.message, context, chat_id)
        if ainda:
            context.user_data["docs_pendentes"] = ainda
            await _atualizar_mensagem_viva(
                context, chat_id, "❌ <b>Ainda há falhas.</b> Toque para tentar de novo.",
                InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Tentar novamente", callback_data="regen_missing")]]))
        else:
            await _atualizar_mensagem_viva(context, chat_id, "✅ <b>Todos os documentos foram entregues!</b>", None)
            reset_user_data(chat_id)
            context.user_data.clear()
        return

        
    # ===== EDITAR CAMPO ESPECÍFICO =====
    elif data.startswith("edit_"):
        campo = CAMPO_POR_CALLBACK.get(data)
        if campo:
            context.user_data["campo_editando"] = campo
            nome_campo = CAMPOS_EXIBICAO[campo]
            await query.answer(f"Editando: {nome_campo}")
            
            valor_atual = ud["dados"].get(campo, "")
            if valor_atual:
                info_valor = f"\n📌 <b>Valor atual:</b> <code>{valor_atual}</code>"
            else:
                info_valor = "\n📌 <i>Campo vazio</i>"
                
            keyboard = get_editing_keyboard()
            edit_text = (
                f"✏️ <b>EDITANDO: {nome_campo}</b>\n"
                f"{info_valor}\n"
                f"📝 <b>Digite o novo valor:</b>\n"
                f"<i>(ou clique em Cancelar edição para voltar)</i>"
            )
            await _atualizar_mensagem_viva(context, chat_id, edit_text, keyboard)
            return

async def processar_correcao(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None: return AGUARDANDO_CORRECAO
    texto = update.message.text.strip()
    chat_id = update.message.chat_id
    ud = get_user_data(chat_id)
    
    # ===== EDIÇÃO DE CAMPO ESPECÍFICO =====
    campo_editando = context.user_data.get("campo_editando")
    if campo_editando:
        ud["dados"][campo_editando] = texto
        context.user_data.pop("campo_editando", None)
        await _apagar_mensagem_usuario(update)
        
        nome_campo = CAMPOS_EXIBICAO[campo_editando]
        confirmacao = f"✅ <b>{nome_campo} atualizado!</b>\n<code>{texto}</code>"
        await _atualizar_mensagem_viva(context, chat_id, confirmacao, None)
        await asyncio.sleep(1.5)
        await _mostrar_cartao_principal(update, context)
        return AGUARDANDO_CORRECAO
        
    # ===== COMANDOS DE TEXTO =====
    if texto.upper() == "OK":
        await _apagar_mensagem_usuario(update)
        await _mostrar_cartao_principal(update, context)
        return AGUARDANDO_CORRECAO
        
    if texto.upper() == "LIMPAR":
        await _apagar_mensagem_usuario(update)
        reset_user_data(chat_id)
        context.user_data.clear()
        msg_id = context.user_data.get("correction_msg_id")
        if msg_id:
            try: await context.bot.delete_message(chat_id, msg_id)
            except Exception: pass
        await update.message.reply_html(card_sucesso("✨ Todos os dados foram apagados!"))
        return ConversationHandler.END
        
    # ===== INTERPRETAÇÃO LIVRE =====
    interpretado = interpretar_input_livre(texto)
    if interpretado:
        campos_afetados = []
        for campo, valor in interpretado.items():
            if campo in CAMPOS_PADRAO:
                ud["dados"][campo] = valor
                campos_afetados.append(CAMPOS_EXIBICAO.get(campo, campo))
                
        if campos_afetados:
            await _apagar_mensagem_usuario(update)
            nomes = ", ".join(campos_afetados)
            confirmacao = f"✅ <b>Atualizado:</b> {nomes}"
            await _atualizar_mensagem_viva(context, chat_id, confirmacao, None)
            await asyncio.sleep(1.5)
            await _mostrar_cartao_principal(update, context)
            return AGUARDANDO_CORRECAO
            
    # ===== SINTAXE CAMPO=VALOR =====
    if "=" in texto:
        matches = re.findall(r"(\w+)=([^=]+?)(?=\s+\w+=|$)", texto)
        atualizados = []
        for campo, valor in matches:
            chave = campo.lower().strip()
            if chave in CAMPOS_PADRAO:
                ud["dados"][chave] = valor.strip()
                atualizados.append(chave)
                
        if atualizados:
            await _apagar_mensagem_usuario(update)
            nomes = ", ".join(CAMPOS_EXIBICAO.get(c, c) for c in atualizados)
            confirmacao = f"✅ <b>Atualizado:</b> {nomes}"
            await _atualizar_mensagem_viva(context, chat_id, confirmacao, None)
            await asyncio.sleep(1.5)
            await _mostrar_cartao_principal(update, context)
            return AGUARDANDO_CORRECAO
            
    # ===== NADA RECONHECIDO =====
    await _apagar_mensagem_usuario(update)
    ajuda = (
        "❌ <b>Formato não reconhecido</b>\n"
        "💡 <b>Como usar:</b>\n"
        "• <b>Clique</b> nos botões abaixo para editar\n"
        "• <b>Digite</b> palavras-chave: <i>casado engenheiro brasileiro</i>\n"
        "• <b>Use</b> campo=valor: <i>estado_civil=casado</i>\n"
        "⬇️ <b>Use os botões abaixo:</b>"
    )
    keyboard = get_correction_keyboard()
    await _atualizar_mensagem_viva(context, chat_id, ajuda, keyboard)
    return AGUARDANDO_CORRECAO

async def _enviar_documentos(resultados: List[Dict[str, Any]], reply_channel,
                             context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    # Envia os docs gerados; falhas viram 'pendentes' (antes eram puladas em silêncio).
    enviados, pendentes = [], []
    for i, res in enumerate(resultados, 1):
        caminho = res.get("caminho")
        if res.get("ok") and caminho and os.path.exists(caminho):
            nome_arquivo = Path(caminho).stem
            porcentagem = int((i / len(resultados)) * 100)
            barras = "▓" * (porcentagem // 5) + "░" * (20 - porcentagem // 5)
            await _atualizar_mensagem_viva(
                context, chat_id,
                f"🚀 <b>GERANDO KIT INICIAL</b>\n📄 Enviando: <b>{nome_arquivo}</b>\n{barras} {porcentagem}%", None)
            with open(caminho, "rb") as f:
                await reply_channel.reply_document(
                    document=f, filename=Path(caminho).name,
                    caption=f"📄 {nome_arquivo.replace('_fix', '').replace('_', ' ').title()}")
            try: os.remove(caminho)
            except Exception: pass
            enviados.append(res["tipo"])
        else:
            pendentes.append(res)
    return enviados, pendentes

async def cmd_kit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        reply_channel = update.message
        is_callback = False
    elif update.callback_query:
        reply_channel = update.callback_query.message
        is_callback = True
    else:
        return
        
    chat_id = update.effective_chat.id
    ud = get_user_data(chat_id)
    dados = ud.get("dados", {})
    
    if not DOCXTPL_AVAILABLE:
        msg = "❌ Sistema de documentos não disponível."
        if is_callback: await _atualizar_mensagem_viva(context, chat_id, msg, None)
        else: await reply_channel.reply_text(msg)
        return
        
    progresso = (
        "🚀 <b>GERANDO KIT INICIAL</b>\n"
        "⏳ Preparando documentos...\n"
        "░░░░░░░░░░░░░░░░░░░░ 0%"
    )
    await _atualizar_mensagem_viva(context, chat_id, progresso, None)
    
    try:
        resultados = await gerar_kit_inicial(chat_id)
        enviados, pendentes = await _enviar_documentos(resultados, reply_channel, context, chat_id)
        # 🔁 RETRY AUTOMÁTICO: detectou faltante → regera antes de avisar
        if pendentes:
            await _atualizar_mensagem_viva(
                context, chat_id,
                "🔄 <b>Falha detectada!</b> Regerando: " +
                ", ".join(rotulo_doc(p["tipo"]) for p in pendentes) + "...", None)
            retry = await asyncio.gather(*[
                _gerar_documento(chat_id, p["tipo"], p["template"]) for p in pendentes])
            ok2, pendentes = await _enviar_documentos(retry, reply_channel, context, chat_id)
            enviados += ok2
        if not pendentes:
            sucesso = (
                "✅ <b>KIT INICIAL COMPLETO!</b>\n"
                "📋 <b>Documentos gerados:</b>\n"
                "1. Procuração\n"
                "2. Declaração de Hipossuficiência\n"
                "3. Contrato de Honorários\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "📌 <b>Envie outro documento</b> para iniciar novo processo."
            )
            await _atualizar_mensagem_viva(context, chat_id, sucesso, None)
            reset_user_data(chat_id)
            context.user_data.clear()
        else:
            # ⚠️ Kit parcial: mensagem honesta + botão de regeração manual
            context.user_data["docs_pendentes"] = pendentes
            nomes = "\n".join("• " + rotulo_doc(p["tipo"]) for p in pendentes)
            teclado = InlineKeyboardMarkup([[InlineKeyboardButton(
                "🔄 Regerar documentos faltantes", callback_data="regen_missing")]])
            await _atualizar_mensagem_viva(
                context, chat_id,
                f"⚠️ <b>Kit parcial:</b> {len(enviados)}/3 documentos entregues.\n"
                f"<b>Faltando:</b>\n{nomes}\n\n👇 Toque para regerar agora:", teclado)
        
    except Exception as exc:
        logger.exception("Erro ao gerar kit")
        erro_msg = f"❌ <b>Erro ao gerar documentos:</b>\n<code>{str(exc)[:100]}</code>"
        await _atualizar_mensagem_viva(context, chat_id, erro_msg, None)

async def erro_global(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Erro global: %s", context.error)

# =========================
# 🚀 MAIN
# =========================
def build_app() -> Application:
    if not TOKEN: raise ValueError("TELEGRAM_BOT_TOKEN não configurado.")
    garantir_pastas()
    init_db()  # ✅ Inicializa o banco de clientes
    
    if not verificar_ollama():
        logger.warning("⚠️ Ollama não detectado em %s - extração local pode falhar", OLLAMA_URL)
        
    print("=" * 60)
    print("🤖 Bot Jurídico Pro - UI Conversacional v3.0 (Cadastro Unificado)")
    print(f"🔗 Ollama: {OLLAMA_URL} | Modelo: {OLLAMA_MODEL}")
    print(f"📦 docxtpl: {'✅' if DOCXTPL_AVAILABLE else '❌'}")
    print(f"📁 BASE_DIR: {BASE_DIR}")
    print(f"💾 DB_PATH: {DB_PATH}")
    print("=" * 60)
    
    request = HTTPXRequest(connect_timeout=60, read_timeout=120, write_timeout=60, pool_timeout=60)
    app = Application.builder().token(TOKEN).request(request).build()
    
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.PHOTO | filters.Document.ALL, handle_documento)],
        states={
            AGUARDANDO_CORRECAO: [
                CommandHandler("kit", cmd_kit),
                CommandHandler("dados", cmd_dados),
                CommandHandler("limpar", cmd_limpar),
                CommandHandler("cancel", cancelar),
                # ✅ Regex corrigida para casar com edit_nome, edit_cpf, etc.
                    CallbackQueryHandler(handle_callback, pattern=r"^(edit_.*|confirm|generate_kit|edit_data|reextract|cancel|cancel_edit|regen_missing)$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, processar_correcao),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancelar)],
        allow_reentry=True,
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("kit", cmd_kit))
    app.add_handler(CommandHandler("dados", cmd_dados))
    app.add_handler(CommandHandler("limpar", cmd_limpar))
    app.add_handler(CommandHandler("cancel", cancelar))
    app.add_handler(conv_handler)
    app.add_error_handler(erro_global)
    
    return app

async def run_bot():
    app = build_app()
    while True:
        try:
            print("🚀 Bot iniciando polling...")
            await app.initialize()
            await app.start()
            await app.updater.start_polling(drop_pending_updates=True)
            await asyncio.Event().wait()
        except (NetworkError, TimedOut) as e:
            print(f"⚠️ Falha de rede: {e}")
            print("🔁 Reconectando em 5 segundos...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"❌ Erro inesperado: {e}")
            await asyncio.sleep(5)
        finally:
            try: await app.shutdown()
            except Exception: pass

if __name__ == "__main__":
    asyncio.run(run_bot())
