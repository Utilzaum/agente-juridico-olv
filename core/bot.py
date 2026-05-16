#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot Executor Jurídico - Kit Inicial (OLLAMA LOCAL)
Fluxo:
1) Recebe foto/PDF do documento do cliente
2) Faz OCR
3) Tenta extrair dados com Ollama local (GPU)
4) Complementa com regex
5) Permite correção interativa dos dados (com interpretador inteligente)
6) Gera apenas o kit inicial:
- Procuração
- Declaração de hipossuficiência
- Contrato de honorários
"""
import os, sys, asyncio, atexit, json, logging, re, shutil, time, zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application, CallbackContext, CommandHandler, ContextTypes,
    ConversationHandler, MessageHandler, filters,
)
from telegram.request import HTTPXRequest
from telegram.error import NetworkError, TimedOut  # ✅ ADICIONADO

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
# 🔒 LOCK COM VALIDAÇÃO DE PID (CORREÇÃO CRÍTICA)
# =========================
LOCK = "/tmp/bot_executor.lock"

def is_pid_alive(pid: int) -> bool:
    """Verifica se um PID realmente está rodando no OS."""
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
# CORREÇÃO DE DOCX
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

def converter_docx_para_pdf(caminho_docx: str) -> Optional[str]:
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

# =========================
# CONFIGURAÇÃO
# =========================
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:2b")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
ALLOW_EXTERNAL_FALLBACK = os.getenv("ALLOW_EXTERNAL_FALLBACK", "false").lower() == "true"

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

def get_base_dir() -> Path:
    current = Path(__file__).resolve()
    for parent in [current.parent, *current.parents]:
        if parent.name == "agente_juridico": return parent
    return current.parent

BASE_DIR = get_base_dir()
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
AGUARDANDO_CORRECAO = 1
AGUARDANDO_NOVO_VALOR = 2

CAMPOS_PADRAO: Dict[str, str] = {
    "nome": "", "cpf": "", "data_nascimento": "", "endereco": "",
    "cep": "", "email": "", "nacionalidade": "brasileira",
    "estado_civil": "", "profissao": "", "area_juridica": "",
}
CAMPOS_EXIBICAO: Dict[str, str] = {
    "nome": "👤 Nome", "cpf": "🆔 CPF", "data_nascimento": "🎂 Data de Nascimento",
    "endereco": "📍 Endereço", "cep": "📮 CEP", "email": "📧 E-mail",
    "nacionalidade": "🌎 Nacionalidade", "estado_civil": "💍 Estado Civil",
    "profissao": "💼 Profissão", "area_juridica": "⚖️ Área Jurídica",
}
ORDEM_CAMPOS = ["nome", "cpf", "data_nascimento", "endereco", "cep", "email",
                "nacionalidade", "estado_civil", "profissao", "area_juridica"]
CAMPO_POR_NUMERO = {
    "1": "nome", "2": "cpf", "3": "data_nascimento", "4": "endereco",
    "5": "cep", "6": "email", "7": "nacionalidade", "8": "estado_civil",
    "9": "profissao", "10": "area_juridica",
}

_user_sessions: Dict[int, Dict[str, str]] = {}

def get_user_data(chat_id: int) -> Dict[str, str]:
    if chat_id not in _user_sessions: _user_sessions[chat_id] = dict(CAMPOS_PADRAO)
    return _user_sessions[chat_id]

def reset_user_data(chat_id: int) -> None:
    _user_sessions[chat_id] = dict(CAMPOS_PADRAO)

# =========================
# UTILITÁRIOS
# =========================
def limpar_nome(texto: str) -> str:
    if not texto: return ""
    texto = re.sub(r"[0-9]", "", texto)
    texto = re.sub(r"[^\w\sÀ-ÿ]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    lixo = {"DOCUMENTO", "AUXILIAR", "NOTA", "FISCAL", "ENERGIA", "ELETRICA", "ELÉTRICA", "LIGHT", "CENTRO", "BRASIL", "REPUBLICA", "REPÚBLICA"}
    palavras = [p for p in texto.split() if p.upper() not in lixo and len(p) > 1]
    if len(palavras) >= 2: return " ".join(palavras[:6]).upper()
    if len(palavras) == 1: return palavras[0].upper()
    return ""

def formatar_cpf(cpf: str) -> str:
    cpf = re.sub(r"\D", "", str(cpf))
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}" if len(cpf) == 11 else cpf

def formatar_cep(cep: str) -> str:
    cep = re.sub(r"\D", "", str(cep))
    return f"{cep[:5]}-{cep[5:]}" if len(cep) == 8 else cep

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
        candidatos.extend([BASE_DIR / "templates" / nome, BASE_DIR / "core" / "templates" / nome, BASE_DIR / "services" / "templates" / nome, Path.cwd() / "templates" / nome])
    for cand in candidatos:
        if cand.exists(): return str(cand)
    for nome in nomes:
        for encontrado in BASE_DIR.rglob(nome):
            if encontrado.is_file(): return str(encontrado)
    raise FileNotFoundError(f"Template não encontrado. Tentado: {', '.join(nomes)}")

def mostrar_dados_completo(chat_id: int) -> str:
    ud = get_user_data(chat_id)
    linhas = ["DADOS DO CLIENTE:"]
    for campo in ORDEM_CAMPOS:
        valor = ud.get(campo, "")
        if not valor: continue
        if campo == "cpf": valor = formatar_cpf(valor)
        elif campo == "cep": valor = formatar_cep(valor)
        linhas.append(f"{CAMPOS_EXIBICAO[campo]}: {valor}")
    return "Nenhum dado cadastrado." if len(linhas) == 1 else "\n".join(linhas)

def mostrar_menu_correcao() -> str:
    return (
        "Deseja corrigir algum dado?\n"
        "Digite o número do campo:\n"
        "1 - Nome    2 - CPF    3 - Data de Nascimento    4 - Endereço\n"
        "5 - CEP     6 - E-mail 7 - Nacionalidade         8 - Estado Civil\n"
        "9 - Profissão              10 - Área Jurídica\n"
        "Digite OK para continuar.\n"
        "Digite limpar para reiniciar todos os dados.\n"
        "💡 DICA: Você pode digitar diretamente:\n"
        "• brasileiro(a), casado(a), solteiro(a), engenheiro, etc.\n"
        "• email@exemplo.com\n"
        "• Ou múltiplos: 'casado engenheiro brasileiro'"
    )

def mensagem_boas_vindas() -> str:
    return (
        "🤖 Bot Jurídico Profissional (100% Local)\n"
        "Envie uma foto ou PDF do documento do cliente.\n"
        "O bot tentará extrair automaticamente os dados e então permitirá correção.\n"
        "Comandos:\n"
        "/kit - Gerar o kit inicial\n"
        "/dados - Ver dados cadastrados\n"
        "/limpar - Apagar todos os dados\n"
        "/cancel - Cancelar operação"
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
    nacionalidades_map = {"brasileiro": "brasileiro", "brasileira": "brasileira", "argentino": "argentino", "argentina": "argentina", "português": "português", "portuguesa": "portuguesa", "americano": "americano", "americana": "americana", "italiano": "italiano", "italiana": "italiana", "espanhol": "espanhol", "espanhola": "espanhola", "francês": "francês", "francesa": "francesa", "alemão": "alemão", "alema": "alemã", "japones": "japonês", "japonesa": "japonesa", "chinês": "chinês", "chinesa": "chinesa"}
    estados_civis_map = {"solteiro": "solteiro", "solteira": "solteira", "solteir": "solteiro", "casado": "casado", "casada": "casada", "casad": "casado", "divorciado": "divorciado", "divorciada": "divorciada", "divorci": "divorciado", "separado": "separado", "separada": "separada", "separ": "separado", "viuvo": "viúvo", "viuva": "viúva", "viúv": "viúvo", "uniao estavel": "união estável", "união estável": "união estável"}
    profissoes_comuns = {"autonomo": "autônomo", "autônomo": "autônomo", "autonoma": "autônoma", "autônoma": "autônoma", "do lar": "do lar", "dolar": "do lar", "engenheiro": "engenheiro", "engenheira": "engenheira", "advogado": "advogado", "advogada": "advogada", "medico": "médico", "médico": "médico", "medica": "médica", "médica": "médica", "professor": "professor", "professora": "professora", "estudante": "estudante", "desempregado": "desempregado", "desempregada": "desempregada", "aposentado": "aposentado", "aposentada": "aposentada", "contador": "contador", "contadora": "contadora", "administrador": "administrador", "administradora": "administradora", "programador": "programador", "programadora": "programadora", "designer": "designer", "arquiteto": "arquiteto", "arquiteta": "arquiteta", "dentista": "dentista", "enfermeiro": "enfermeiro", "enfermeira": "enfermeira", "vendedor": "vendedor", "vendedora": "vendedora", "motorista": "motorista", "pensionista": "pensionista"}
    nacionalidade_encontrada = estado_civil_encontrado = None
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
"endereco": "endereço completo",
"cep": "apenas números, 8 dígitos",
"email": "e-mail ou null",
"nacionalidade": "nacionalidade ou null",
"estado_civil": "estado civil ou null",
"profissao": "profissão ou null"
}}
Regras críticas:
1. data_nascimento deve ser de nascimento (ignore vencimento, emissão, validade).
2. CPF deve ter exatamente 11 dígitos numéricos.
3. Se não houver e-mail, retorne null (não invente).
4. Responda APENAS com JSON, sem markdown, sem explicações.
""".strip()
    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "options": {"temperature": 0.1, "num_predict": 500}}
    try:
        response = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=45)
        response.raise_for_status()
        content = response.json().get("response", "")
        dados = extrair_json_de_texto(content)
        if dados.get("nome"): dados["nome"] = limpar_nome(str(dados["nome"]))
        if dados.get("cpf"): dados["cpf"] = re.sub(r"\D", "", str(dados["cpf"]))[:11]
        if dados.get("cep"): dados["cep"] = re.sub(r"\D", "", str(dados["cep"]))[:8]
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
        if ALLOW_EXTERNAL_FALLBACK and DEEPSEEK_API_KEY:
            logger.info("🔄 Tentando fallback para DeepSeek...")
            return await extrair_com_deepseek_fallback(texto_ocr)
        return {"_erro_llm": True}
    except Exception as exc:
        logger.error("❌ Erro na extração local: %s", exc)
        return {}

async def extrair_com_deepseek_fallback(texto_ocr: str) -> Dict[str, Any]: return {}

async def extrair_com_regex(texto_ocr: str) -> Dict[str, Any]:
    dados: Dict[str, Any] = {}
    nome_match = re.search(r"(?:NOME|NOME DO TITULAR)\s*[:\-]?\s*([A-ZÀ-Ü\s]{5,})", texto_ocr, re.IGNORECASE)
    if nome_match: dados["nome"] = limpar_nome(nome_match.group(1))
    else:
        nome_match = re.search(r"\b([A-ZÀ-Ü]{2,}(?:\s+[A-ZÀ-Ü]{2,}){1,5})\b", texto_ocr)
        if nome_match: dados["nome"] = limpar_nome(nome_match.group(1))
    cpf_match = re.search(r"\d{3}\.\d{3}\.\d{3}-\d{2}|\b\d{11}\b", texto_ocr)
    if cpf_match: dados["cpf"] = re.sub(r"\D", "", cpf_match.group(0))
    nasc_match = re.search(r"(?:NASC(?:IMENTO)?|DATA\s+DE\s+NASC(?:IMENTO)?)[^\d]*(\d{2}/\d{2}/\d{4})", texto_ocr, re.IGNORECASE)
    if nasc_match: dados["data_nascimento"] = nasc_match.group(1)
    endereco_match = re.search(r"(?:RUA|AV|AVENIDA|ESTRADA|ALAMEDA|TRAVESSA)[^\n]{10,}", texto_ocr, re.IGNORECASE)
    if endereco_match: dados["endereco"] = endereco_match.group(0).strip()
    cep_match = re.search(r"\b\d{5}-?\d{3}\b", texto_ocr)
    if cep_match: dados["cep"] = re.sub(r"\D", "", cep_match.group(0))
    email_match = re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", texto_ocr)
    if email_match: dados["email"] = email_match.group(0).strip()
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
        if v and not dados.get(k): dados[k] = v
    if dados.get("nome"): dados["nome"] = limpar_nome(str(dados["nome"]))
    if dados.get("cpf"): dados["cpf"] = re.sub(r"\D", "", str(dados["cpf"]))
    if dados.get("cep"): dados["cep"] = re.sub(r"\D", "", str(dados["cep"]))
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
        "nome": ud.get("nome", ""), "cpf": formatar_cpf(ud.get("cpf", "")),
        "endereco": ud.get("endereco", ""), "nacionalidade": ud.get("nacionalidade", "brasileira"),
        "estado_civil": ud.get("estado_civil", ""), "profissao": ud.get("profissao", ""),
        "email": ud.get("email", ""), "area_juridica": ud.get("area_juridica", "Direito Civil"),
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
    if caminho_docx_corrigido != str(caminho_docx): limpar_temporarios(caminho_docx_corrigido)
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
    if caminho_docx_corrigido != str(caminho_docx): limpar_temporarios(caminho_docx_corrigido)
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
    if caminho_docx_corrigido != str(caminho_docx): limpar_temporarios(caminho_docx_corrigido)
    return caminho_pdf if caminho_pdf else str(caminho_docx)

async def gerar_kit_inicial(chat_id: int) -> List[str]:
    resultados = await asyncio.gather(gerar_procuracao(chat_id), gerar_hipossuficiencia(chat_id), gerar_contrato(chat_id))
    return [r for r in resultados if r]

# =========================
# HANDLERS TELEGRAM
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message: await update.message.reply_text(mensagem_boas_vindas())

async def cmd_dados(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message: await update.message.reply_text(mostrar_dados_completo(update.message.chat_id))

async def cmd_limpar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        reset_user_data(update.message.chat_id)
        context.user_data.pop("campo_editando", None)
        await update.message.reply_text("Todos os dados foram apagados.")

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message:
        context.user_data.pop("campo_editando", None)
        await update.message.reply_text("Operação cancelada.")
    return ConversationHandler.END

async def handle_documento(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.message
    if message is None: return ConversationHandler.END
    chat_id = message.chat_id if message else 0
    if message.document:
        file_obj = message.document
        file_name = getattr(file_obj, "file_name", "") or "documento"
        ext = Path(file_name).suffix.lower() or ".bin"
    elif message.photo:
        file_obj = message.photo[-1]
        ext = ".jpg"
    else: return ConversationHandler.END

    logger.info("📄 Novo documento recebido | Chat: %s | Ext: %s", chat_id, ext)
    status = await message.reply_text("Processando documento...")
    path_original: Optional[Path] = None
    path_processado: Optional[Path] = None
    try:
        garantir_pastas()
        file_id = file_obj.file_id
        path_original = DIR_ORIGINAL / f"{file_id}_original{ext}"
        path_processado = DIR_PROCESSADO / f"{file_id}_processado{ext}"
        tg_file = await file_obj.get_file()
        await tg_file.download_to_drive(str(path_original))
        if not validar_arquivo_entrada(str(path_original)): raise ValueError("Arquivo de entrada inválido ou corrompido")
        caminho_para_ocr = str(path_original)
        if ext not in {".pdf", ".doc", ".docx"}:
            caminho_para_ocr = normalizar_imagem_para_ocr(str(path_original), str(path_processado))
        
        texto_raw = await asyncio.to_thread(extrair_texto_do_arquivo, caminho_para_ocr)
        if not texto_raw:
            await status.delete()
            await message.reply_text("Não consegui extrair texto do documento.")
            return ConversationHandler.END
            
        dados = await processar_documento(str(path_original), chat_id=chat_id)
        erro_llm = dados.pop("_erro_llm", False)
        
        if dados:
            ud = get_user_data(chat_id)
            for campo, valor in dados.items():
                if campo in CAMPOS_PADRAO and valor not in (None, ""): ud[campo] = str(valor).strip()
            await status.delete()
            if erro_llm: await message.reply_text("⚠️ IA local indisponível. Extração realizada apenas via Regex.")
            await message.reply_text(mostrar_dados_completo(chat_id))
            await message.reply_text(mostrar_menu_correcao())
            return AGUARDANDO_CORRECAO
        else:
            await status.delete()
            await message.reply_text("Não consegui extrair dados automaticamente.\nMas você pode digitar manualmente:\nEx: 'brasileiro casado engenheiro'\nou enviar outro documento.")
            return ConversationHandler.END
    except Exception as exc:
        logger.exception("Erro ao processar documento")
        try: await status.delete()
        except Exception: pass
        await message.reply_text(f"Erro ao processar documento: {exc}")
        return ConversationHandler.END
    finally:
        limpar_temporarios(path_original, path_processado)

async def processar_correcao(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None: return AGUARDANDO_CORRECAO
    texto = update.message.text.strip()
    chat_id = update.message.chat_id
    ud = get_user_data(chat_id)
    texto_upper = texto.upper()
    if texto_upper == "OK":
        await update.message.reply_text("Dados salvos. Use /kit para gerar a procuração, a declaração de hipossuficiência e o contrato.")
        return ConversationHandler.END
    if texto_upper == "LIMPAR":
        reset_user_data(chat_id); context.user_data.pop("campo_editando", None)
        await update.message.reply_text("Todos os dados foram apagados.")
        return ConversationHandler.END
    interpretado = interpretar_input_livre(texto)
    if interpretado:
        atualizados = []
        for campo, valor in interpretado.items():
            if campo in CAMPOS_PADRAO:
                ud[campo] = valor
                atualizados.append(CAMPOS_EXIBICAO.get(campo, campo))
        if atualizados:
            await update.message.reply_text(f"✅ Campo(s) identificado(s) automaticamente:\n{' • '.join(atualizados)}")
            await update.message.reply_text(mostrar_dados_completo(chat_id))
            await update.message.reply_text(mostrar_menu_correcao())
        return AGUARDANDO_CORRECAO
    if texto in CAMPO_POR_NUMERO:
        campo = CAMPO_POR_NUMERO[texto]
        context.user_data["campo_editando"] = campo
        await update.message.reply_text(f"Informe o novo valor para {CAMPOS_EXIBICAO[campo]}:")
        return AGUARDANDO_NOVO_VALOR
    if "=" in texto:
        matches = re.findall(r"(\w+)=([^=]+?)(?=\s+\w+=|$)", texto)
        atualizados: List[str] = []
        for campo, valor in matches:
            chave = campo.lower().strip()
            if chave in CAMPOS_PADRAO:
                ud[chave] = valor.strip()
                atualizados.append(CAMPOS_EXIBICAO.get(chave, chave))
        if atualizados:
            await update.message.reply_text(f"Campos atualizados: {', '.join(atualizados)}")
            await update.message.reply_text(mostrar_dados_completo(chat_id))
            await update.message.reply_text(mostrar_menu_correcao())
        return AGUARDANDO_CORRECAO
    await update.message.reply_text("Opção inválida.\nDigite um número de 1 a 10, use campo=valor, ou digite algo como:\n• brasileiro(a), casado(a), solteiro(a)\n• engenheiro, advogado, autônomo\n• email@exemplo.com\n• Ou múltiplos: 'casado engenheiro brasileiro'")
    return AGUARDANDO_CORRECAO

async def processar_novo_valor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None: return AGUARDANDO_CORRECAO
    texto = update.message.text.strip()
    chat_id = update.message.chat_id
    campo = context.user_data.get("campo_editando")
    if not campo: return AGUARDANDO_CORRECAO
    ud = get_user_data(chat_id)
    ud[campo] = texto
    context.user_data.pop("campo_editando", None)
    await update.message.reply_text(f"{CAMPOS_EXIBICAO[campo]} atualizado para: {texto}")
    await update.message.reply_text(mostrar_dados_completo(chat_id))
    await update.message.reply_text(mostrar_menu_correcao())
    return AGUARDANDO_CORRECAO

async def cmd_kit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None: return
    chat_id = update.message.chat_id
    ud = get_user_data(chat_id)
    obrigatorios = ["nome", "cpf", "endereco", "email"]
    faltando = [c for c in obrigatorios if not ud.get(c)]
    if faltando:
        nomes = ", ".join(CAMPOS_EXIBICAO[c] for c in faltando)
        await update.message.reply_text(f"Dados incompletos.\nFaltam: {nomes}\nEnvie um documento ou corrija os dados pelo menu.")
        return
    if not DOCXTPL_AVAILABLE:
        await update.message.reply_text("docxtpl não está instalado."); return
    await update.message.reply_text("Gerando kit inicial...\nProcuração, declaração de hipossuficiência e contrato de honorários.")
    try:
        caminhos = await gerar_kit_inicial(chat_id)
        for caminho in caminhos:
            if caminho and os.path.exists(caminho):
                with open(caminho, "rb") as f:
                    await update.message.reply_document(document=f, filename=Path(caminho).name, caption="Documento gerado")
                try: os.remove(caminho)
                except Exception: pass
        await update.message.reply_text("✅ Kit inicial completo.")
    except Exception as exc:
        logger.exception("Erro ao gerar kit")
        await update.message.reply_text(f"Erro ao gerar documentos: {exc}")

async def erro_global(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Erro global: %s", context.error)

# =========================
# 🚀 MAIN COM AUTO-RECONEXÃO (CORREÇÃO FINAL)
# =========================
def build_app() -> Application:
    if not TOKEN: raise ValueError("TELEGRAM_BOT_TOKEN não configurado.")
    garantir_pastas()
    if not verificar_ollama():
        logger.warning("⚠️ Ollama não detectado em %s - extração local pode falhar", OLLAMA_URL)

    print("=" * 60)
    print("🤖 Bot Jurídico Profissional - Kit Inicial (100% LOCAL)")
    print(f"🔗 Ollama: {OLLAMA_URL} | Modelo: {OLLAMA_MODEL}")
    print(f"🔒 Modo Local: {'SIM' if not ALLOW_EXTERNAL_FALLBACK else 'NÃO (fallback ativo)'}")
    print(f"📦 docxtpl: {'INSTALADO' if DOCXTPL_AVAILABLE else 'NÃO INSTALADO'}")
    print(f"📁 BASE_DIR: {BASE_DIR}")
    print("=" * 60)

    request = HTTPXRequest(connect_timeout=60, read_timeout=120, write_timeout=60, pool_timeout=60)
    app = Application.builder().token(TOKEN).request(request).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.PHOTO | filters.Document.ALL, handle_documento)],
        states={
            AGUARDANDO_CORRECAO: [
                CommandHandler("kit", cmd_kit), CommandHandler("dados", cmd_dados),
                CommandHandler("limpar", cmd_limpar), CommandHandler("cancel", cancelar),
                MessageHandler(filters.TEXT & ~filters.COMMAND, processar_correcao),
            ],
            AGUARDANDO_NOVO_VALOR: [
                CommandHandler("kit", cmd_kit), CommandHandler("dados", cmd_dados),
                CommandHandler("limpar", cmd_limpar), CommandHandler("cancel", cancelar),
                MessageHandler(filters.TEXT & ~filters.COMMAND, processar_novo_valor),
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
    """Loop principal com reconexão automática e controle de recursos."""
    app = build_app()
    while True:
        try:
            print("🚀 Executor iniciando polling...")
            await app.initialize()
            await app.start()
            await app.updater.start_polling(drop_pending_updates=True)
            await asyncio.Event().wait()  # Mantém rodando indefinidamente
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
