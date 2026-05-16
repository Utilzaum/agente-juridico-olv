#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Envio por E-mail - Oliveira Advocacia
Fluxo:
1) Recebe um ou mais arquivos .docx ou .pdf
2) Valida integridade do arquivo conforme extensão
3) Pergunta o nome do cliente
4) Pergunta o e-mail do destinatário
5) Envia os documentos via SendGrid (COM CÓPIA para rvao.adv@outlook.com)
6) Limpa os arquivos temporários
"""
import os, sys
import uuid
import logging
import zipfile
import asyncio
import base64
import re
import shutil
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Mail, Attachment, FileContent, FileName, FileType, Disposition, Email, Cc
)

# =========================
# SINGLE INSTANCE LOCK (ROBUST)
# =========================
LOCK = "/tmp/bot_email.lock"

if os.path.exists(LOCK):
    with open(LOCK, "r") as f:
        pid = f.read().strip()

    if pid and os.path.exists(f"/proc/{pid}"):
        print(f"Já está rodando (PID {pid})")
        sys.exit()
    else:
        print("Lock antigo encontrado, removendo...")
        os.remove(LOCK)

with open(LOCK, "w") as f:
    f.write(str(os.getpid()))

# =========================
# CONFIG
# =========================
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_EMAIL")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_CC = "rvao.adv@outlook.com"  # ✅ Email em cópia
TEMP_DIR = Path(__file__).resolve().parent / "temp_email"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# =========================
# LOGGING (nível produção)
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s -> %(message)s",
)
logger = logging.getLogger("bot_email")

# =========================
# MEMÓRIA DE USUÁRIO
# =========================
user_data = {}

# =========================
# VALIDAÇÃO & UTILITÁRIOS
# =========================
def validar_docx(path):
    """Verifica se o arquivo é um DOCX válido (ZIP com estrutura Office)"""
    try:
        with zipfile.ZipFile(path, 'r') as z:
            names = z.namelist()
            return "[Content_Types].xml" in names and "word/document.xml" in names
    except Exception:
        return False

def validar_pdf(path):
    """Verifica se o arquivo começa com a assinatura mágica de PDF"""
    try:
        with open(path, "rb") as f:
            header = f.read(4)
        return header == b"%PDF"
    except Exception:
        return False

def validar_email(email):
    """Validação robusta de endereço de email"""
    email = email.strip().lower()
    padrao = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(padrao, email):
        return False
    if '..' in email or email.startswith('.') or email.endswith('.'):
        return False
    if '@' not in email or email.count('@') != 1:
        return False
    
    local, dominio = email.split('@')
    return bool(local and dominio and '.' in dominio)

def gerar_nome_limpo(caminho: str, nome_cliente: str) -> str:
    """Gera nome padronizado para anexos: {Tipo}_{NomeCliente}.{ext}"""
    # Limpa o nome do cliente (remove especiais, troca espaços por _)
    nome_limpo = re.sub(r"[^\w\s]", "", nome_cliente).strip().replace(" ", "_")
    if not nome_limpo:
        nome_limpo = "Cliente"
        
    # Identifica tipo pelo nome original do arquivo
    basename = os.path.basename(caminho).upper()
    if "PROCURACAO" in basename:
        tipo = "Procuracao"
    elif "HIPOSSUFICIENCIA" in basename:
        tipo = "Declaracao_Hipossuficiencia"
    elif "HONORARIOS" in basename:
        tipo = "Contrato_Honorarios"
    else:
        tipo = "Documento"
        
    ext = caminho.split(".")[-1].lower()
    return f"{tipo}_{nome_limpo}.{ext}"

# =========================
# ENVIO EMAIL
# =========================
def montar_corpo(cliente: str) -> str:
    return f"""
<p>Prezado(a) <strong>{cliente}</strong>,</p>
<p>
Segue, em anexo, a procuração, a declaração de hipossuficiência e o contrato de honorários,
para apreciação e eventual correção.
</p>
<p>
Solicitamos, por gentileza, a conferência dos documentos e, estando de acordo,
confirme com um "ok".
</p>
<p>
Dr. Oliveira, quando o cliente confirmar os dados, por favor, concluir com o envio do documento em PDF.
</p>
<p>Permanecemos à disposição para quaisquer esclarecimentos.</p>
<br>
<p>Atenciosamente,<br>
<strong>Estagiário Virtual Oliveira Advocacia</strong></p>
"""

def enviar_email(destino, arquivos, nome_cliente):
    try:
        subject = f"OLIVEIRA ADVOCACIA | DOCUMENTOS DE REPRESENTAÇÃO – {nome_cliente.upper()}"
        
        message = Mail(
            from_email=EMAIL_FROM,
            to_emails=destino,
            subject=subject,
            html_content=montar_corpo(nome_cliente)
        )
        
        message.add_cc(Cc(EMAIL_CC))
        
        for caminho in arquivos:
            with open(caminho, "rb") as f:
                data = f.read()
            
            encoded = base64.b64encode(data).decode()
            ext = caminho.lower().split(".")[-1]
            
            mime = "application/pdf" if ext == "pdf" else \
                   "application/vnd.openxmlformats-officedocument.wordprocessingml.document" if ext == "docx" else \
                   "application/octet-stream"
            
            # ✅ CORREÇÃO: Gera nome limpo antes de anexar
            nome_limpo = gerar_nome_limpo(caminho, nome_cliente)
            
            attachment = Attachment(
                FileContent(encoded),
                FileName(nome_limpo),  # ✅ Nome padronizado no lugar de os.path.basename()
                FileType(mime),
                Disposition("attachment")
            )
            message.add_attachment(attachment)
        
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        logger.info(f"Email enviado | status={response.status_code} | CC={EMAIL_CC}")
        return response.status_code
    except Exception as e:
        logger.exception("Falha no envio de email")
        raise

# =========================
# RECEBER DOCUMENTO (COM VALIDAÇÃO)
# =========================
async def receber_documento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        doc = update.message.document
        file = await doc.get_file()
        
        unique_name = f"{uuid.uuid4()}_{doc.file_name}"
        file_path = os.path.join(TEMP_DIR, unique_name)
        await file.download_to_drive(file_path)
        
        if not file_path.lower().endswith((".docx", ".pdf")):
            os.remove(file_path)
            raise Exception("Formato não suportado. Envie apenas .docx ou .pdf")
            
        if os.path.getsize(file_path) == 0:
            os.remove(file_path)
            raise Exception("Arquivo vazio")
            
        if file_path.lower().endswith(".docx"):
            if not validar_docx(file_path):
                os.remove(file_path)
                raise Exception("DOCX inválido ou corrompido")
        elif file_path.lower().endswith(".pdf"):
            if not validar_pdf(file_path):
                os.remove(file_path)
                raise Exception("PDF inválido ou corrompido")
                
        user_id = update.message.chat_id
        
        # ✅ CORREÇÃO 1: user_data completo
        if user_id not in user_data:
            user_data[user_id] = {"files": [], "nome": None, "email": None, "etapa": None}
            
        user_data[user_id]["files"].append(file_path)
        user_data[user_id]["etapa"] = "aguardando_ok"
        
        total = len(user_data[user_id]["files"])
        await update.message.reply_text(
            f"✅ *{doc.file_name}* recebido ({total} arquivo{'s' if total > 1 else ''}).\n"
            "Envie mais arquivos ou digite *OK* para continuar.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.exception("Erro ao receber documento")
        await update.message.reply_text(f"❌ Erro: {e}")

# =========================
# FLUXO TEXTO (MÁQUINA DE ESTADOS)
# =========================
async def fluxo_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    texto = update.message.text.strip()
    
    # ✅ CORREÇÃO 2: user_data completo
    if user_id not in user_data:
        await update.message.reply_text("📎 Envie um documento *.docx* ou *.pdf* primeiro.", parse_mode="Markdown")
        return
        
    sessao = user_data[user_id]
    etapa = sessao.get("etapa")
    
    if etapa == "aguardando_ok":
        if texto.upper() != "OK":
            await update.message.reply_text("Digite *OK* quando terminar de enviar os arquivos.", parse_mode="Markdown")
            return
        user_data[user_id]["etapa"] = "aguardando_cliente"
        await update.message.reply_text("👤 Informe o *nome completo do cliente*:", parse_mode="Markdown")
        return
        
    if etapa == "aguardando_cliente":
        user_data[user_id]["nome"] = texto
        user_data[user_id]["etapa"] = "aguardando_email"
        await update.message.reply_text("📧 Informe o *e-mail do destinatário*:", parse_mode="Markdown")
        return
        
    if etapa == "aguardando_email":
        if not validar_email(texto):
            logger.warning(f"Email inválido recebido: '{texto}'")
            await update.message.reply_text(
                "❌ E-mail inválido. Verifique se digitou corretamente.\n"
                "Exemplo: cliente@exemplo.com",
                parse_mode="Markdown"
            )
            return
            
        destino = texto.strip().lower()
        nome_cliente = user_data[user_id]["nome"]
        arquivos = user_data[user_id]["files"]
        
        logger.info(f"Enviando email para: {destino} | Cliente: {nome_cliente} | Arquivos: {len(arquivos)}")
        
        await update.message.reply_text("📤 Enviando e-mail...")
        try:
            status = await asyncio.to_thread(enviar_email, destino, arquivos, nome_cliente)
            if status in (200, 202):
                await update.message.reply_text(
                    f"✅ E-mail enviado com sucesso para *{destino}*!\n"
                    f"📨 Cópia enviada para: {EMAIL_CC}",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(f"⚠️ SendGrid retornou status: {status}")
        except Exception as e:
            logger.exception("Erro no envio")
            await update.message.reply_text(f"❌ Falha ao enviar: {e}")
        finally:
            limpar_sessao(user_id)
        return
        
    await update.message.reply_text(
        "📎 Envie um arquivo *.docx* ou *.pdf* ou digite *OK* para continuar.",
        parse_mode="Markdown"
    )

# =========================
# LIMPEZA DE SESSÃO
# =========================
def limpar_sessao(user_id: int):
    sessao = user_data.get(user_id, {})
    for f in sessao.get("files", []):
        try:
            if os.path.exists(f):
                os.remove(f)
        except Exception:
            pass
    user_data.pop(user_id, None)
    logger.info(f"Sessão {user_id} limpa")

# =========================
# COMANDOS AUXILIARES
# =========================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📧 *Bot de Envio — Oliveira Advocacia*\n"
        "1️⃣ Envie os arquivos *.docx* ou *.pdf* que deseja enviar\n"
        "2️⃣ Digite *OK* quando terminar\n"
        "3️⃣ Informe o nome do cliente\n"
        "4️⃣ Informe o e-mail do destinatário\n"
        "📨 Todos os e-mails serão enviados com cópia para: rvao.adv@outlook.com\n"
        "Use /cancelar para reiniciar a qualquer momento.",
        parse_mode="Markdown"
    )

async def cmd_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    limpar_sessao(update.message.chat_id)
    await update.message.reply_text("🔄 Sessão reiniciada. Envie um novo documento quando quiser.")

# =========================
# MAIN
# =========================
def main():
    if not all([TELEGRAM_TOKEN, SENDGRID_API_KEY, EMAIL_FROM]):
        logger.error("Variáveis de ambiente não configuradas. Verifique o arquivo .env")
        return
        
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("cancelar", cmd_cancelar))
    app.add_handler(MessageHandler(filters.Document.ALL, receber_documento))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fluxo_texto))
    
    logger.info("📧 Bot de E-mail — Oliveira Advocacia iniciado")
    logger.info(f"TEMP_DIR: {TEMP_DIR} | FROM: {EMAIL_FROM} | CC: {EMAIL_CC}")
    
    print("=" * 60)
    print("📧 Bot de Envio — Oliveira Advocacia")
    print(f"📨 Cópias para: {EMAIL_CC} | 📁 Temp: {TEMP_DIR}")
    print("=" * 60)
    print("Bot rodando... Aguardando mensagens!")
    print("=" * 60)
    
    try:
        app.run_polling(drop_pending_updates=True)
    finally:
        if os.path.exists(LOCK):
            os.remove(LOCK)
            print("🔓 Lock file removido.")

if __name__ == "__main__":
    main()
