#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Documentarista Previdenciário — bot standalone (segundo kit do motor documental OLV).
NUNCA importa core.bot (lock de PID no import). Reutiliza só módulos seguros."""
import os, sys, asyncio, atexit, re, sqlite3, logging, time
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
load_dotenv()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, ConversationHandler, MessageHandler,
                          CallbackQueryHandler, filters, ContextTypes)
from telegram.request import HTTPXRequest
from telegram.error import NetworkError, TimedOut

from core.ui.cards import card_sucesso, card_erro
from core.ui.keyboards import get_preview_keyboard
from core.previdenciario import engine_prev as eng
from core.previdenciario import kit_prev as kit
from core.previdenciario.ui_prev import (mensagem_boas_vindas_prev, card_cliente_prev,
                                             card_preview_prev, get_correction_keyboard_prev)

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ========================= LOCK PRÓPRIO =========================
LOCK = "/tmp/bot_previdenciario.lock"
def _pid_vivo(pid):
    try: os.kill(pid, 0); return True
    except Exception: return False
if os.path.exists(LOCK):
    try:
        old = int(open(LOCK).read().strip())
        if _pid_vivo(old):
            print(f"⚠️ Previdenciário já rodando (PID {old})."); sys.exit(1)
        os.remove(LOCK)
    except (ValueError, FileNotFoundError): os.remove(LOCK)
open(LOCK, "w").write(str(os.getpid()))
@atexit.register
def _remover_lock():
    try: os.remove(LOCK)
    except Exception: pass

# ========================= CONFIG =========================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_PREVIDENCIARIO", "")

def get_base_dir():
    for p in [ROOT, *ROOT.parents]:
        if p.name in ("agente_juridico", "agente-juridico-olv"): return p
    return ROOT
BASE_DIR = get_base_dir()
DB_PATH = BASE_DIR / "clientes.db"  # mesmo banco do Cível; diferencia por area_juridica

def salvar_cliente_prev(dados):
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS clientes
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, cpf TEXT UNIQUE, nome TEXT,
                      data_nascimento TEXT, endereco TEXT, email TEXT, profissao TEXT,
                      estado_civil TEXT, nacionalidade TEXT, area_juridica TEXT,
                      criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        c.execute('''INSERT OR REPLACE INTO clientes
                     (cpf, nome, data_nascimento, endereco, email, profissao,
                      estado_civil, nacionalidade, area_juridica)
                     VALUES (?,?,?,?,?,?,?,?,?)''',
                  (dados.get('cpf'), dados.get('nome'), dados.get('data_nascimento'),
                   dados.get('endereco'), dados.get('email'), dados.get('profissao'),
                   dados.get('estado_civil'), dados.get('nacionalidade'),
                   'Direito Previdenciário'))
        conn.commit(); conn.close(); return True
    except Exception as e:
        logger.error("Erro ao salvar cliente: %s", e); return False

# ========================= SESSÃO =========================
AGUARDANDO_CORRECAO = 1
_user_sessions: Dict[int, Dict[str, Any]] = {}
def get_user_data(chat_id):
    if chat_id not in _user_sessions:
        _user_sessions[chat_id] = {"dados": dict(eng.CAMPOS_PADRAO), "confidence": None}
    return _user_sessions[chat_id]
def reset_user_data(chat_id):
    _user_sessions[chat_id] = {"dados": dict(eng.CAMPOS_PADRAO), "confidence": None}

# ========================= UI VIVA =========================
async def _atualizar_mensagem_viva(context, chat_id, texto, reply_markup=None, parse_mode="HTML"):
    msg_id = context.user_data.get("correction_msg_id")
    try:
        if msg_id:
            await context.bot.edit_message_text(chat_id=chat_id, message_id=msg_id,
                                                text=texto, reply_markup=reply_markup, parse_mode=parse_mode)
        else: raise ValueError
    except Exception:
        nova = await context.bot.send_message(chat_id=chat_id, text=texto,
                                              reply_markup=reply_markup, parse_mode=parse_mode)
        context.user_data["correction_msg_id"] = nova.message_id

async def _mostrar_cartao(update, context):
    ud = get_user_data(update.effective_chat.id)
    await _atualizar_mensagem_viva(context, update.effective_chat.id,
                                   card_cliente_prev(ud["dados"], ud.get("confidence")),
                                   get_correction_keyboard_prev())

# ========================= HANDLERS =========================
async def start(update, context):
    if update.message: await update.message.reply_html(mensagem_boas_vindas_prev())

async def cmd_dados(update, context):
    if not update.message: return
    ud = get_user_data(update.message.chat_id)
    if not any(ud["dados"].values()):
        await update.message.reply_text("📭 Nenhum dado cadastrado ainda."); return
    await update.message.reply_html(card_cliente_prev(ud["dados"], ud.get("confidence")))

async def cmd_limpar(update, context):
    if not update.message: return
    reset_user_data(update.message.chat_id); context.user_data.clear()
    await update.message.reply_html(card_sucesso("✨ Todos os dados foram apagados!"))

async def cancelar(update, context):
    if update.message:
        msg_id = context.user_data.get("correction_msg_id")
        if msg_id:
            try: await context.bot.delete_message(update.message.chat_id, msg_id)
            except Exception: pass
        context.user_data.clear()
        await update.message.reply_text("❌ Operação cancelada.")
    return ConversationHandler.END

async def handle_documento(update, context):
    message = update.message
    if message is None: return ConversationHandler.END
    chat_id = message.chat_id
    context.user_data.clear()
    if message.document:
        file_obj = message.document
        ext = Path(getattr(file_obj, "file_name", "") or "doc").suffix.lower() or ".bin"
    elif message.photo:
        file_obj = message.photo[-1]; ext = ".jpg"
    else: return ConversationHandler.END

    status = await message.reply_text("🔍 <b>Analisando documento...</b>\n⏳ Processando OCR...", parse_mode="HTML")
    p_orig = p_proc = None
    try:
        kit.garantir_pastas()
        file_id = file_obj.file_id
        p_orig = eng.BASE_TEMP / f"{file_id}_original{ext}"
        p_proc = eng.BASE_TEMP / f"{file_id}_processado{ext}"
        tg = await file_obj.get_file(); await tg.download_to_drive(str(p_orig))
        if not eng.validar_arquivo_entrada(str(p_orig)): raise ValueError("Arquivo inválido")
        await status.edit_text("🔍 <b>Analisando...</b>\n🤖 Extraindo dados com IA...", parse_mode="HTML")
        dados = await eng.processar_documento(str(p_orig), chat_id=chat_id)
        erro_llm = dados.pop("_erro_llm", False)
        if dados:
            ud = get_user_data(chat_id); campos = []
            for campo, valor in dados.items():
                if campo in eng.CAMPOS_PADRAO and valor not in (None, ""):
                    ud["dados"][campo] = str(valor).strip(); campos.append(eng.CAMPOS_EXIBICAO.get(campo, campo))
            await status.delete()
            txt = f"✅ <b>Documento processado!</b>\n📋 <b>{len(campos)} campos extraídos</b>\n"
            if erro_llm: txt += "⚠️ IA local indisponível, usando extração básica.\n"
            txt += "\n📝 <b>Revise os dados abaixo:</b>"
            await message.reply_html(txt)
            ud["confidence"] = 0.85
            sent = await message.reply_html(card_cliente_prev(ud["dados"], ud["confidence"]),
                                            reply_markup=get_correction_keyboard_prev())
            context.user_data["correction_msg_id"] = sent.message_id
            return AGUARDANDO_CORRECAO
        await status.delete()
        await message.reply_text("❌ <b>Não foi possível extrair dados.</b>\n"
                                 "📸 Envie foto mais nítida, PDF digitalizado ou digite os dados.", parse_mode="HTML")
        return ConversationHandler.END
    except Exception as exc:
        logger.exception("Erro ao processar documento")
        try: await status.delete()
        except Exception: pass
        await message.reply_html(card_erro(f"❌ Erro ao processar: {str(exc)[:100]}"))
        return ConversationHandler.END
    finally:
        eng.limpar_temporarios(p_orig, p_proc)

async def handle_callback(update, context):
    query = update.callback_query
    chat_id = query.message.chat_id
    data = query.data
    ud = get_user_data(chat_id)

    if data == "confirm":
        d = ud["dados"]; erros = []
        if not (d.get("nome") or "").strip(): erros.append("👤 <b>Nome</b> é obrigatório.")
        cpf = re.sub(r"\D", "", str(d.get("cpf", "")))
        if len(cpf) != 11: erros.append("🆔 <b>CPF</b> deve ter 11 dígitos.")
        else: d["cpf"] = cpf
        if not (d.get("endereco") or "").strip(): erros.append("📍 <b>Endereço</b> é obrigatório.")
        email = (d.get("email") or "").strip()
        if not re.match(r"^[\w.\-+]+@[\w.\-]+\.\w+$", email): erros.append("📧 <b>E-mail</b> inválido.")
        else: d["email"] = email
        if erros:
            await _atualizar_mensagem_viva(context, chat_id,
                "⚠️ <b>Dados incompletos:</b>\n\n" + "\n".join(erros), get_correction_keyboard_prev()); return
        salvar_cliente_prev(d)
        await query.answer("✅ Dados confirmados!")
        await _atualizar_mensagem_viva(context, chat_id,
            card_preview_prev(d) + "\n✅ <b>Dados prontos!</b> Clique em 'Gerar Kit'.", get_preview_keyboard())
        return

    if data == "generate_kit":
        await query.answer("🚀 Gerando documentos...")
        await _atualizar_mensagem_viva(context, chat_id, "🚀 <b>Gerando kit previdenciário...</b>", None)
        await cmd_kit(update, context); return

    if data == "edit_data":
        await query.answer("📝 Modo de edição")
        await _atualizar_mensagem_viva(context, chat_id,
            "✏️ <b>EDIÇÃO DE DADOS</b>\nSelecione o campo:", get_correction_keyboard_prev()); return

    if data == "cancel":
        await query.answer("Operação cancelada")
        try: await query.message.delete()
        except Exception: pass
        context.user_data.clear(); return

    if data == "cancel_edit":
        await query.answer("Edição cancelada")
        context.user_data.pop("campo_editando", None)
        await _mostrar_cartao(update, context); return

    if data == "regen_missing":
        pend = context.user_data.pop("docs_pendentes", [])
        if not pend:
            await query.answer("✅ Nada pendente."); return
        await query.answer("🔄 Regerando...")
        retry = await asyncio.gather(*[_g(chat_id, p) for p in pend])
        _, ainda = await _enviar_documentos(retry, query.message, context, chat_id)
        if ainda:
            context.user_data["docs_pendentes"] = ainda
            await _atualizar_mensagem_viva(context, chat_id, "❌ Ainda há falhas.",
                InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Tentar novamente", callback_data="regen_missing")]]))
        else:
            await _atualizar_mensagem_viva(context, chat_id, "✅ <b>Todos os documentos entregues!</b>", None)
            reset_user_data(chat_id); context.user_data.clear()
        return

    if data.startswith("edit_"):
        campo = eng.CAMPO_POR_CALLBACK.get(data)
        if campo:
            context.user_data["campo_editando"] = campo
            atual = ud["dados"].get(campo, "")
            await query.answer(f"Editando: {eng.CAMPOS_EXIBICAO[campo]}")
            await _atualizar_mensagem_viva(context, chat_id,
                f"✏️ <b>EDITANDO: {eng.CAMPOS_EXIBICAO[campo]}</b>\n"
                f"\n📌 <b>Valor atual:</b> <code>{atual}</code>" if atual else
                f"✏️ <b>EDITANDO: {eng.CAMPOS_EXIBICAO[campo]}</b>\n📌 <i>Campo vazio</i>",
                InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancelar edição", callback_data="cancel_edit")]]))

async def _g(chat_id, p):  # helper retry
    return await kit._gerar_documento(get_user_data(chat_id)["dados"], p["tipo"], p["template"])

async def processar_correcao(update, context):
    if update.message is None: return AGUARDANDO_CORRECAO
    texto = update.message.text.strip()
    chat_id = update.message.chat_id
    ud = get_user_data(chat_id)
    campo = context.user_data.get("campo_editando")
    if campo:
        ud["dados"][campo] = texto
        context.user_data.pop("campo_editando", None)
        try: await update.message.delete()
        except Exception: pass
        await _atualizar_mensagem_viva(context, chat_id,
            f"✅ <b>{eng.CAMPOS_EXIBICAO[campo]} atualizado!</b>\n<code>{texto}</code>", None)
        await asyncio.sleep(1.5); await _mostrar_cartao(update, context)
        return AGUARDANDO_CORRECAO
    if texto.upper() == "OK":
        try: await update.message.delete()
        except Exception: pass
        await _mostrar_cartao(update, context); return AGUARDANDO_CORRECAO
    if texto.upper() == "LIMPAR":
        reset_user_data(chat_id); context.user_data.clear()
        await update.message.reply_html(card_sucesso("✨ Dados apagados!"))
        return ConversationHandler.END
    if "=" in texto:
        atualizados = []
        for c, v in re.findall(r"(\w+)=([^=]+?)(?=\s+\w+=|$)", texto):
            if c.lower() in eng.CAMPOS_PADRAO:
                ud["dados"][c.lower()] = v.strip(); atualizados.append(c.lower())
        if atualizados:
            try: await update.message.delete()
            except Exception: pass
            await _atualizar_mensagem_viva(context, chat_id,
                "✅ <b>Atualizado:</b> " + ", ".join(eng.CAMPOS_EXIBICAO[c] for c in atualizados), None)
            await asyncio.sleep(1.5); await _mostrar_cartao(update, context)
            return AGUARDANDO_CORRECAO
    await _atualizar_mensagem_viva(context, chat_id,
        "❌ <b>Formato não reconhecido</b>\n💡 Use os botões, ou <i>campo=valor</i>.", get_correction_keyboard_prev())
    return AGUARDANDO_CORRECAO

async def _enviar_documentos(resultados, reply_channel, context, chat_id):
    enviados, pendentes = [], []
    for i, res in enumerate(resultados, 1):
        caminho = res.get("caminho")
        if res.get("ok") and caminho and os.path.exists(caminho):
            pct = int((i / len(resultados)) * 100)
            barras = "▓" * (pct // 5) + "░" * (20 - pct // 5)
            await _atualizar_mensagem_viva(context, chat_id,
                f"🚀 <b>GERANDO KIT PREVIDENCIÁRIO</b>\n📄 {Path(caminho).stem}\n{barras} {pct}%", None)
            with open(caminho, "rb") as f:
                await reply_channel.reply_document(document=f, filename=Path(caminho).name,
                    caption=f"📄 {kit.rotulo_doc(res['tipo'])}")
            try: os.remove(caminho)
            except Exception: pass
            enviados.append(res["tipo"])
        else: pendentes.append(res)
    return enviados, pendentes

async def cmd_kit(update, context):
    reply_channel = update.message or (update.callback_query.message if update.callback_query else None)
    if not reply_channel: return
    chat_id = update.effective_chat.id
    ud = get_user_data(chat_id)
    try:
        resultados = await kit.gerar_kit_prev(ud["dados"])
        enviados, pendentes = await _enviar_documentos(resultados, reply_channel, context, chat_id)
        if pendentes:
            await _atualizar_mensagem_viva(context, chat_id, "🔄 <b>Falha detectada!</b> Regerando...", None)
            retry = await asyncio.gather(*[_g(chat_id, p) for p in pendentes])
            ok2, pendentes = await _enviar_documentos(retry, reply_channel, context, chat_id)
            enviados += ok2
        if not pendentes:
            await _atualizar_mensagem_viva(context, chat_id,
                "✅ <b>KIT PREVIDENCIÁRIO COMPLETO!</b>\n1. Procuração\n2. Hipossuficiência\n"
                "3. Renúncia ao Teto\n4. Contrato de Honorários\n━━━━━━━━━━━━━━━━━━\n"
                "📌 Envie outro documento para novo processo.", None)
            reset_user_data(chat_id); context.user_data.clear()
        else:
            context.user_data["docs_pendentes"] = pendentes
            await _atualizar_mensagem_viva(context, chat_id,
                f"⚠️ <b>Kit parcial:</b> {len(enviados)}/4.\n👇 Regerar:",
                InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Regerar faltantes", callback_data="regen_missing")]]))
    except Exception as exc:
        logger.exception("Erro ao gerar kit")
        await _atualizar_mensagem_viva(context, chat_id, f"❌ Erro: <code>{str(exc)[:100]}</code>", None)

async def erro_global(update, context): logger.exception("Erro global: %s", context.error)

# ========================= MAIN =========================
def build_app():
    if not TOKEN: raise ValueError("TELEGRAM_BOT_TOKEN_PREVIDENCIARIO não configurado no .env")
    kit.garantir_pastas()
    print("=" * 60)
    print("⚖️ Documentarista Previdenciário v0.1 (MVP standalone)")
    print(f"📁 BASE_DIR: {BASE_DIR} | 💾 DB: {DB_PATH}")
    print("=" * 60)
    req = HTTPXRequest(connect_timeout=60, read_timeout=120, write_timeout=60, pool_timeout=60)
    app = Application.builder().token(TOKEN).request(req).build()
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.PHOTO | filters.Document.ALL, handle_documento)],
        states={AGUARDANDO_CORRECAO: [
            CommandHandler("kit", cmd_kit), CommandHandler("dados", cmd_dados),
            CommandHandler("limpar", cmd_limpar), CommandHandler("cancel", cancelar),
            CallbackQueryHandler(handle_callback,
                pattern=r"^(edit_.*|confirm|generate_kit|edit_data|reextract|cancel|cancel_edit|regen_missing)$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, processar_correcao)]},
        fallbacks=[CommandHandler("cancel", cancelar)], allow_reentry=True)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("kit", cmd_kit))
    app.add_handler(CommandHandler("dados", cmd_dados))
    app.add_handler(CommandHandler("limpar", cmd_limpar))
    app.add_handler(CommandHandler("cancel", cancelar))
    app.add_handler(conv)
    app.add_error_handler(erro_global)
    return app

async def run_bot():
    app = build_app()
    while True:
        try:
            await app.initialize(); await app.start()
            await app.updater.start_polling(drop_pending_updates=True)
            await asyncio.Event().wait()
        except (NetworkError, TimedOut) as e:
            print(f"⚠️ Falha de rede: {e} — reconectando em 5s..."); await asyncio.sleep(5)
        except Exception as e:
            print(f"❌ Erro: {e}"); await asyncio.sleep(5)
        finally:
            try: await app.shutdown()
            except Exception: pass

if __name__ == "__main__":
    asyncio.run(run_bot())
