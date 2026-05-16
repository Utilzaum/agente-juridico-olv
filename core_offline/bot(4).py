#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot Executor Jurídico - Kit Inicial
Fluxo:
1) Recebe foto/PDF do documento do cliente
2) Faz OCR com GLM-OCR (Ollama local)
3) Extrai dados estruturados com Qwen (Ollama local)
4) Complementa com regex
5) Permite correção interativa dos dados
6) Gera apenas o kit inicial:
- Procuração
- Declaração de hipossuficiência
- Contrato de honorários
"""
# 1. Carrega variáveis de ambiente PRIMEIRO
from dotenv import load_dotenv
load_dotenv()

# 2. Imports da biblioteca padrão
import asyncio
import json
import logging
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# 3. Imports de terceiros
import httpx
from telegram import Update
from telegram.ext import (
    Application,
    CallbackContext,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

# 4. Imports opcionais
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

# 5. Imports do projeto
from core.bot_ocr import extrair_texto_do_arquivo

# =========================
# CONFIGURAÇÃO
# =========================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/v1/chat/completions")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:4b")

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

def get_base_dir() -> Path:
    current = Path(__file__).resolve()
    for parent in [current.parent, *current.parents]:
        if parent.name == "agente_juridico":
            return parent
    return current.parent

BASE_DIR = get_base_dir()

# =========================
# DIRETÓRIOS DE TRABALHO
# =========================
BASE_TEMP_DIR = BASE_DIR / "temp"
DIR_ORIGINAL = BASE_TEMP_DIR / "original"
DIR_PROCESSADO = BASE_TEMP_DIR / "processado"

def garantir_pastas() -> None:
    BASE_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    DIR_ORIGINAL.mkdir(parents=True, exist_ok=True)
    DIR_PROCESSADO.mkdir(parents=True, exist_ok=True)

# =========================
# ESTADO DA CONVERSA
# =========================
AGUARDANDO_CORRECAO = 1
AGUARDANDO_NOVO_VALOR = 2

# =========================
# DADOS DO CLIENTE
# =========================
CAMPOS_PADRAO: Dict[str, str] = {
    "nome": "",
    "cpf": "",
    "data_nascimento": "",
    "endereco": "",
    "cep": "",
    "email": "",
    "nacionalidade": "brasileira",
    "estado_civil": "",
    "profissao": "",
    "area_juridica": "",
}

CAMPOS_EXIBICAO: Dict[str, str] = {
    "nome": "👤 Nome",
    "cpf": "🆔 CPF",
    "data_nascimento": "🎂 Data de Nascimento",
    "endereco": "📍 Endereço",
    "cep": "📮 CEP",
    "email": "📧 E-mail",
    "nacionalidade": "🌎 Nacionalidade",
    "estado_civil": "💍 Estado Civil",
    "profissao": "💼 Profissão",
    "area_juridica": "⚖️ Área Jurídica",
}

ORDEM_CAMPOS = [
    "nome", "cpf", "data_nascimento", "endereco", "cep", "email",
    "nacionalidade", "estado_civil", "profissao", "area_juridica"
]

CAMPO_POR_NUMERO = {
    "1": "nome", "2": "cpf", "3": "data_nascimento", "4": "endereco",
    "5": "cep", "6": "email", "7": "nacionalidade", "8": "estado_civil",
    "9": "profissao", "10": "area_juridica",
}

_user_sessions: Dict[int, Dict[str, str]] = {}

def get_user_data(chat_id: int) -> Dict[str, str]:
    if chat_id not in _user_sessions:
        _user_sessions[chat_id] = dict(CAMPOS_PADRAO)
    return _user_sessions[chat_id]

def reset_user_data(chat_id: int) -> None:
    _user_sessions[chat_id] = dict(CAMPOS_PADRAO)

# =========================
# UTILITÁRIOS
# =========================
def limpar_nome(texto: str) -> str:
    if not texto:
        return ""
    texto = re.sub(r"[0-9]", "", texto)
    texto = re.sub(r"[^\w\sÀ-ÿ]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    lixo = {"DOCUMENTO", "AUXILIAR", "NOTA", "FISCAL", "ENERGIA", "ELETRICA", "ELÉTRICA", "LIGHT", "CENTRO", "BRASIL", "REPUBLICA", "REPÚBLICA"}
    palavras = [p for p in texto.split() if p.upper() not in lixo and len(p) > 1]
    if len(palavras) >= 2:
        return " ".join(palavras[:6]).title()
    if len(palavras) == 1:
        return palavras[0].title()
    return ""

def formatar_cpf(cpf: str) -> str:
    cpf = re.sub(r"\D", "", str(cpf))
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}" if len(cpf) == 11 else cpf

def formatar_cep(cep: str) -> str:
    cep = re.sub(r"\D", "", str(cep))
    return f"{cep[:5]}-{cep[5:]}" if len(cep) == 8 else cep

def extrair_json_de_texto(texto: str) -> dict:
    if not texto:
        return {}
    texto = re.sub(r"```json\s*|```", "", texto, flags=re.IGNORECASE)
    match = re.search(r"\{.*\}", texto, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except Exception:
        return {}

def limpar_temporarios(*paths: Optional[Path | str]) -> None:
    for p in paths:
        if not p:
            continue
        try:
            path = Path(p)
            if path.exists():
                path.unlink()
        except Exception:
            pass

def validar_arquivo_entrada(caminho: str) -> bool:
    try:
        path = Path(caminho)
        return path.exists() and path.stat().st_size >= 1000
    except Exception:
        return False

def validar_imagem(caminho: str) -> bool:
    try:
        path = Path(caminho)
        if not path.exists() or path.stat().st_size < 1000:
            return False
        if CV2_AVAILABLE and path.suffix.lower() not in {".pdf", ".doc", ".docx"}:
            img = cv2.imread(str(path))
            return img is not None and getattr(img, "size", 0) != 0
        return True
    except Exception:
        return False

def normalizar_imagem_para_ocr(origem: str, destino: str) -> str:
    try:
        origem_path = Path(origem)
        destino_path = Path(destino)
        if not origem_path.exists():
            return origem
        if CV2_AVAILABLE and origem_path.suffix.lower() not in {".pdf", ".doc", ".docx"}:
            img = cv2.imread(str(origem_path))
            if img is not None:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
                cv2.imwrite(str(destino_path), gray)
                return destino
        shutil.copy2(origem, destino)
        return destino
    except Exception:
        return origem

def localizar_template(*nomes: str) -> str:
    candidatos: List[Path] = []
    for nome in nomes:
        candidatos.extend([
            BASE_DIR / "templates" / nome,
            BASE_DIR / "core" / "templates" / nome,
            BASE_DIR / "services" / "templates" / nome,
            Path.cwd() / "templates" / nome,
        ])
    for cand in candidatos:
        if cand.exists():
            return str(cand)
    for nome in nomes:
        for encontrado in BASE_DIR.rglob(nome):
            if encontrado.is_file():
                return str(encontrado)
    raise FileNotFoundError(f"Template não encontrado. Tentado: {', '.join(nomes)}")

def mostrar_dados_completo(chat_id: int) -> str:
    ud = get_user_data(chat_id)
    linhas = ["DADOS DO CLIENTE:"]
    for campo in ORDEM_CAMPOS:
        valor = ud.get(campo, "")
        if not valor:
            continue
        if campo == "cpf":
            valor = formatar_cpf(valor)
        elif campo == "cep":
            valor = formatar_cep(valor)
        linhas.append(f"{CAMPOS_EXIBICAO[campo]}: {valor}")
    return "\n".join(linhas) if len(linhas) > 1 else "Nenhum dado cadastrado."

def mostrar_menu_correcao() -> str:
    return (
        "Deseja corrigir algum dado?\n"
        "Digite o número do campo:\n"
        "1 - Nome\n2 - CPF\n3 - Data de Nascimento\n4 - Endereço\n5 - CEP\n"
        "6 - E-mail\n7 - Nacionalidade\n8 - Estado Civil\n9 - Profissão\n10 - Área Jurídica\n"
        "Digite OK para continuar.\nDigite limpar para reiniciar todos os dados."
    )

def mensagem_boas_vindas() -> str:
    return (
        "🤖 Bot Jurídico Profissional\n"
        "Envie uma foto ou PDF do documento do cliente.\n"
        "O bot extrairá os dados automaticamente e permitirá correção.\n\n"
        "Comandos:\n/kit - Gerar o kit inicial\n/dados - Ver dados cadastrados\n/limpar - Apagar dados\n/cancel - Cancelar"
    )

# =========================
# EXTRAÇÃO COM OLLAMA (LOCAL) + OCR
# =========================
async def extrair_com_ollama(texto_ocr: str) -> Dict[str, Any]:
    """Extrai dados estruturados usando Qwen via Ollama local."""
    if not OLLAMA_URL:
        return {}
        
    prompt = f"""
Analise o texto OCR de um documento brasileiro e extraia os dados do TITULAR do documento.
Texto OCR:
{texto_ocr[:2500]}
Retorne apenas JSON com os campos:
- nome: nome completo do titular
- cpf: CPF do titular, apenas números
- data_nascimento: data de nascimento no formato DD/MM/AAAA
- endereco: endereço completo do titular
- cep: CEP do titular, apenas números
- email: e-mail do titular, se houver
- nacionalidade: nacionalidade, se houver
- estado_civil: estado civil, se houver
- profissao: profissão, se houver
Regras:
1. data_nascimento deve ser de nascimento, nunca vencimento, emissão, validade ou pagamento.
2. Se um campo não existir, retorne null.
3. Responda apenas com JSON válido.
""".strip()

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": "Você é especialista em extração de dados jurídicos. Responda apenas com JSON válido."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 500,
    }

    try:
        timeout = httpx.Timeout(120.0, connect=15.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                OLLAMA_URL,
                headers={"Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            dados = extrair_json_de_texto(content)
            
            # Limpeza e formatação
            if dados.get("nome"):
                dados["nome"] = limpar_nome(str(dados["nome"]))
            if dados.get("cpf"):
                dados["cpf"] = re.sub(r"\D", "", str(dados["cpf"]))
            if dados.get("cep"):
                dados["cep"] = re.sub(r"\D", "", str(dados["cep"]))
            if dados.get("email"):
                dados["email"] = str(dados["email"]).strip()
            if dados.get("nacionalidade"):
                dados["nacionalidade"] = str(dados["nacionalidade"]).strip().lower()
            if dados.get("estado_civil"):
                dados["estado_civil"] = str(dados["estado_civil"]).strip().lower()
            if dados.get("profissao"):
                dados["profissao"] = str(dados["profissao"]).strip().lower()
            return dados
    except Exception as exc:
        logger.error("Ollama falhou: %s", exc)
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
        
    cep_match = re.search(r"\b\d{5}-?\d{3}\b", texto_ocr)
    if cep_match:
        dados["cep"] = re.sub(r"\D", "", cep_match.group(0))
        
    email_match = re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", texto_ocr)
    if email_match:
        dados["email"] = email_match.group(0).strip()
    return dados

async def processar_documento(caminho_arquivo: str) -> Dict[str, Any]:
    if not os.path.exists(caminho_arquivo):
        return {}
    texto_raw = await asyncio.to_thread(extrair_texto_do_arquivo, caminho_arquivo)
    if not texto_raw:
        return {}
        
    # 1. Tenta extrair com Ollama local
    dados = await extrair_com_ollama(texto_raw)
    
    # 2. Complementa com regex se algo faltou
    regex_dados = await extrair_com_regex(texto_raw)
    for chave, valor in regex_dados.items():
        if valor and not dados.get(chave):
            dados[chave] = valor
            
    # 3. Normalizações finais de segurança
    if dados.get("nome"):
        dados["nome"] = limpar_nome(str(dados["nome"]))
    if dados.get("cpf"):
        dados["cpf"] = re.sub(r"\D", "", str(dados["cpf"]))
    if dados.get("cep"):
        dados["cep"] = re.sub(r"\D", "", str(dados["cep"]))
    return dados

# =========================
# GERAÇÃO DOS DOCUMENTOS
# =========================
def contexto_kit(chat_id: int) -> Dict[str, str]:
    ud = get_user_data(chat_id)
    return {
        "nome": ud.get("nome", ""),
        "cpf": formatar_cpf(ud.get("cpf", "")),
        "endereco": ud.get("endereco", ""),
        "nacionalidade": ud.get("nacionalidade", "brasileira"),
        "estado_civil": ud.get("estado_civil", ""),
        "profissao": ud.get("profissao", ""),
        "email": ud.get("email", ""),
        "area_juridica": ud.get("area_juridica", "Direito Civil"),
        "data": datetime.now().strftime("%d/%m/%Y"),
    }

async def gerar_procuracao(chat_id: int) -> str:
    if not DOCXTPL_AVAILABLE:
        raise RuntimeError("docxtpl não está instalado")
    template_path = localizar_template("modelo_procuracao.docx")
    doc = DocxTemplate(template_path)
    doc.render(contexto_kit(chat_id))
    caminho_saida = BASE_TEMP_DIR / f"procuracao_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    doc.save(str(caminho_saida))
    return str(caminho_saida)

async def gerar_hipossuficiencia(chat_id: int) -> str:
    if not DOCXTPL_AVAILABLE:
        raise RuntimeError("docxtpl não está instalado")
    template_path = localizar_template("modelo_hipossuficiencia.docx")
    doc = DocxTemplate(template_path)
    doc.render(contexto_kit(chat_id))
    caminho_saida = BASE_TEMP_DIR / f"hipossuficiencia_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    doc.save(str(caminho_saida))
    return str(caminho_saida)

async def gerar_contrato(chat_id: int) -> str:
    if not DOCXTPL_AVAILABLE:
        raise RuntimeError("docxtpl não está instalado")
    template_path = localizar_template("modelo_honorarios.docx")
    doc = DocxTemplate(template_path)
    doc.render(contexto_kit(chat_id))
    caminho_saida = BASE_TEMP_DIR / f"contrato_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    doc.save(str(caminho_saida))
    return str(caminho_saida)

async def gerar_kit_inicial(chat_id: int) -> List[str]:
    resultados = await asyncio.gather(
        gerar_procuracao(chat_id),
        gerar_hipossuficiencia(chat_id),
        gerar_contrato(chat_id),
    )
    return [r for r in resultados if r]

# =========================
# HANDLERS TELEGRAM
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(mensagem_boas_vindas())

async def cmd_dados(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(mostrar_dados_completo(update.message.chat_id))

async def cmd_limpar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        reset_user_data(update.message.chat_id)
        context.user_data.pop("campo_editando", None)
        await update.message.reply_text("✅ Todos os dados foram apagados.")

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message:
        context.user_data.pop("campo_editando", None)
        await update.message.reply_text("⛔ Operação cancelada.")
    return ConversationHandler.END

async def handle_documento(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.message
    if message is None:
        return ConversationHandler.END
        
    if message.document:
        file_obj = message.document
        file_name = getattr(file_obj, "file_name", "") or "documento"
        ext = Path(file_name).suffix.lower() or ".bin"
    elif message.photo:
        file_obj = message.photo[-1]
        ext = ".jpg"
    else:
        return ConversationHandler.END

    status = await message.reply_text("🔍 Processando documento...")
    chat_id = message.chat_id
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
            raise ValueError("Arquivo inválido ou corrompido")
            
        caminho_para_ocr = str(path_original)
        if ext not in {".pdf", ".doc", ".docx"}:
            caminho_para_ocr = normalizar_imagem_para_ocr(str(path_original), str(path_processado))
            
        texto_raw = await asyncio.to_thread(extrair_texto_do_arquivo, caminho_para_ocr)
        if not texto_raw:
            await status.delete()
            await message.reply_text("❌ Não consegui extrair texto do documento.")
            return ConversationHandler.END
            
        dados = await processar_documento(str(path_original))
        if dados:
            ud = get_user_data(chat_id)
            for campo, valor in dados.items():
                if campo in CAMPOS_PADRAO and valor not in (None, ""):
                    ud[campo] = str(valor).strip()
            await status.delete()
            await message.reply_text(mostrar_dados_completo(chat_id))
            await message.reply_text(mostrar_menu_correcao())
            return AGUARDANDO_CORRECAO
        else:
            await status.delete()
            await message.reply_text("⚠️ Documento processado, mas nenhum dado pôde ser extraído. Tente outro ou insira manualmente.")
            return ConversationHandler.END
            
    except Exception as exc:
        logger.exception("Erro ao processar documento")
        try:
            await status.delete()
        except Exception:
            pass
        await message.reply_text(f"❌ Erro: {exc}")
        return ConversationHandler.END
    finally:
        limpar_temporarios(path_original, path_processado)

async def processar_correcao(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return AGUARDANDO_CORRECAO
    texto = update.message.text.strip()
    chat_id = update.message.chat_id
    ud = get_user_data(chat_id)
    texto_upper = texto.upper()
    
    if texto_upper == "OK":
        await update.message.reply_text("✅ Dados salvos. Use /kit para gerar a procuração, declaração de hipossuficiência e contrato.")
        return ConversationHandler.END
    if texto_upper == "LIMPAR":
        reset_user_data(chat_id)
        context.user_data.pop("campo_editando", None)
        await update.message.reply_text("🗑️ Todos os dados foram apagados.")
        return ConversationHandler.END
    if texto in CAMPO_POR_NUMERO:
        campo = CAMPO_POR_NUMERO[texto]
        context.user_data["campo_editando"] = campo
        await update.message.reply_text(f"✏️ Informe o novo valor para {CAMPOS_EXIBICAO[campo]}:")
        return AGUARDANDO_NOVO_VALOR
        
    if "=" in texto:
        matches = re.findall(r"(\w+)=([^=]+?)(?=\s+\w+=|$)", texto)
        atualizados = []
        for campo, valor in matches:
            chave = campo.lower().strip()
            if chave in CAMPOS_PADRAO:
                ud[chave] = valor.strip()
                atualizados.append(CAMPOS_EXIBICAO.get(chave, chave))
        if atualizados:
            await update.message.reply_text(f"✅ Atualizado: {', '.join(atualizados)}")
            await update.message.reply_text(mostrar_dados_completo(chat_id))
            await update.message.reply_text(mostrar_menu_correcao())
        return AGUARDANDO_CORRECAO
        
    await update.message.reply_text("⚠️ Opção inválida. Digite um número de 1 a 10, use campo=valor, ou digite OK para continuar.")
    return AGUARDANDO_CORRECAO

async def processar_novo_valor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return AGUARDANDO_CORRECAO
    texto = update.message.text.strip()
    chat_id = update.message.chat_id
    campo = context.user_data.get("campo_editando")
    if not campo:
        return AGUARDANDO_CORRECAO
        
    ud = get_user_data(chat_id)
    ud[campo] = texto
    context.user_data.pop("campo_editando", None)
    await update.message.reply_text(f"✅ {CAMPOS_EXIBICAO[campo]} atualizado para: {texto}")
    await update.message.reply_text(mostrar_dados_completo(chat_id))
    await update.message.reply_text(mostrar_menu_correcao())
    return AGUARDANDO_CORRECAO

async def cmd_kit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    chat_id = update.message.chat_id
    ud = get_user_data(chat_id)
    obrigatorios = ["nome", "cpf", "endereco", "email"]
    faltando = [campo for campo in obrigatorios if not ud.get(campo)]
    if faltando:
        nomes = ", ".join(CAMPOS_EXIBICAO[c] for c in faltando)
        await update.message.reply_text(f"⚠️ Dados incompletos.\nFaltam: {nomes}\nEnvie um documento ou corrija pelo menu.")
        return
    if not DOCXTPL_AVAILABLE:
        await update.message.reply_text("❌ docxtpl não está instalado.")
        return
        
    await update.message.reply_text("📄 Gerando kit inicial...\nProcuração, declaração de hipossuficiência e contrato.")
    try:
        caminhos = await gerar_kit_inicial(chat_id)
        for caminho in caminhos:
            if caminho and os.path.exists(caminho):
                with open(caminho, "rb") as f:
                    await update.message.reply_document(document=f, filename=Path(caminho).name, caption="📎 Documento gerado")
                try:
                    os.remove(caminho)
                except Exception:
                    pass
        await update.message.reply_text("✅ Kit inicial completo!")
    except Exception as exc:
        logger.exception("Erro ao gerar kit")
        await update.message.reply_text(f"❌ Erro ao gerar documentos: {exc}")

# =========================
# ERROS / MAIN
# =========================
async def erro_global(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Erro global: %s", context.error)

def main() -> None:
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN não configurado.")
    garantir_pastas()
    
    print("=" * 50)
    print("🤖 Bot Jurídico Profissional - 100% LOCAL")
    print(f"🧠 OCR: GLM-OCR (Ollama)")
    print(f"📝 Extração: {OLLAMA_MODEL} (Ollama)")
    print(f"📂 BASE_DIR: {BASE_DIR}")
    print("=" * 50)
    print("✅ Bot rodando... Aguardando mensagens!")
    
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
    
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
