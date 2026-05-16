#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Orquestrador jurídico principal.
Objetivo:
- Voltar a controlar executor, e-mail e DJEN
- Manter a controladoria como extensão pequena
- Aceitar botões de texto e comandos
- Evitar quebrar o que já funciona
"""
from __future__ import annotations
import os
import sys
import time
import signal
import subprocess
from pathlib import Path
from typing import Optional, Dict
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# =========================================================
# 🔐 CONFIG & CONTROLE DE ACESSO
# =========================================================
load_dotenv()
BASE_DIR = Path(__file__).resolve().parent
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_ORQUESTRADOR")
if not TOKEN:
    raise ValueError("❌ TOKEN não encontrado no .env (TELEGRAM_BOT_TOKEN_ORQUESTRADOR)")

# 🔒 ID do administrador autorizado para comandos críticos
ADMIN_ID = 501276610  # 👈 SEU CHAT_ID

# =========================================================
# 🔒 LOCK DE INSTÂNCIA
# =========================================================
LOCK_FILE = Path("/tmp/orquestrador_olv.lock")
def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False

def acquire_lock() -> None:
    if LOCK_FILE.exists():
        try:
            old_pid = int(LOCK_FILE.read_text().strip())
            if _pid_alive(old_pid):
                print(f"⚠️ Orquestrador já está rodando (PID {old_pid}).")
                sys.exit(1)
        except Exception:
            pass
        try: LOCK_FILE.unlink()
        except Exception: pass
    LOCK_FILE.write_text(str(os.getpid()))

def release_lock() -> None:
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except Exception:
        pass

# =========================================================
# 🧠 PROCESSOS GERENCIADOS
# =========================================================
processos: Dict[str, subprocess.Popen] = {}
def _spawn(command: list[str]) -> subprocess.Popen:
    return subprocess.Popen(command, cwd=str(BASE_DIR), start_new_session=True)

def start_processo(nome: str, comando: list[str]) -> str:
    proc = processos.get(nome)
    if proc and proc.poll() is None:
        return f"⚠️ {nome} já está rodando (PID {proc.pid})"
    if proc and proc.poll() is not None:
        processos.pop(nome, None)
    new_proc = _spawn(comando)
    processos[nome] = new_proc
    return f"✅ {nome} iniciado (PID {new_proc.pid})"

def stop_processo(nome: str) -> str:
    proc = processos.get(nome)
    if not proc:
        return f"⚠️ {nome} não está registrado neste orquestrador."
    if proc.poll() is not None:
        processos.pop(nome, None)
        return f"⚠️ {nome} já estava parado."
    try:
        proc.terminate()
        try: proc.wait(timeout=10)
        except subprocess.TimeoutExpired: proc.kill()
    finally:
        processos.pop(nome, None)
    return f"🛑 {nome} parado"

def stop_all_processos() -> str:
    nomes = list(processos.keys())
    for nome in nomes:
        try: stop_processo(nome)
        except Exception: pass
    return "🛑 Todos os processos parados"

def status_processos() -> str:
    if not processos:
        return "📭 Nenhum processo ativo."
    linhas = ["📊 STATUS:"]
    for nome, proc in processos.items():
        estado = "rodando" if proc.poll() is None else "parado"
        linhas.append(f"- {nome}: PID {proc.pid} ({estado})")
    return "\n".join(linhas)

# =========================================================
# 📊 CONTROLADORIA (OPCIONAL)
# =========================================================
try:
    from orchestrator.controladoria.service import listar_eventos, concluir_evento
    CONTROLADORIA_OK = True
except Exception as e:
    print(f"⚠️ Controladoria não carregada: {e}")
    listar_eventos = None
    concluir_evento = None
    CONTROLADORIA_OK = False

# =========================================================
# 🎨 UI & MENU
# =========================================================
def teclado_principal() -> ReplyKeyboardMarkup:
    teclado = [
        ["start executor", "stop executor"],
        ["start email", "stop email"],
        ["start djen", "stop djen"],
        ["status", "stop all"],
        ["prazos", "Menu"],
    ]
    return ReplyKeyboardMarkup(teclado, resize_keyboard=True)

def _help_text() -> str:
    return (
        "🤖 Comandos do Orquestrador\n"
        "Controle remoto:\n"
        "start executor\nstop executor\n"
        "start email\nstop email\n"
        "start djen\nstop djen\n"
        "status\nstop all\n"
        "Controladoria:\nprazos\n/concluir <ID>\n"
    )

# =========================================================
# 📝 HANDLERS
# =========================================================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message: await update.message.reply_text("🤖 Orquestrador ativo", reply_markup=teclado_principal())
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message: await update.message.reply_text(_help_text(), reply_markup=teclado_principal())
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message: await update.message.reply_text(status_processos(), reply_markup=teclado_principal())
async def cmd_stop_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message: await update.message.reply_text(stop_all_processos(), reply_markup=teclado_principal())
async def cmd_start_executor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        msg = start_processo("executor", [sys.executable, "-m", "core.bot_peticoes"])
        await update.message.reply_text(msg, reply_markup=teclado_principal())
async def cmd_stop_executor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(stop_processo("executor"), reply_markup=teclado_principal())
async def cmd_start_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        msg = start_processo("email", [sys.executable, "bot_email.py"])
        await update.message.reply_text(msg, reply_markup=teclado_principal())
async def cmd_stop_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(stop_processo("email"), reply_markup=teclado_principal())
async def cmd_start_djen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        msg = start_processo("djen", [sys.executable, "script_djen.py"])
        await update.message.reply_text(msg, reply_markup=teclado_principal())
async def cmd_stop_djen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(stop_processo("djen"), reply_markup=teclado_principal())
async def cmd_prazos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    if not CONTROLADORIA_OK or listar_eventos is None:
        await update.message.reply_text("⚠️ Controladoria indisponível.", reply_markup=teclado_principal())
        return
    try:
        eventos = listar_eventos()
        if not eventos:
            await update.message.reply_text("📭 Nenhum prazo pendente.", reply_markup=teclado_principal())
            return
        linhas = ["📊 PRAZOS:"]
        for e in eventos:
            try: linhas.append(f"🆔 {e[0]} | {e[1]} | {e[3]} | {e[6]}")
            except Exception: linhas.append(str(e))
        await update.message.reply_text("\n".join(linhas), reply_markup=teclado_principal())
    except Exception as exc:
        await update.message.reply_text(f"❌ Erro ao listar prazos: {exc}", reply_markup=teclado_principal())
async def cmd_concluir(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    if not CONTROLADORIA_OK or concluir_evento is None:
        await update.message.reply_text("⚠️ Controladoria indisponível.", reply_markup=teclado_principal())
        return
    try:
        if not context.args:
            await update.message.reply_text("❌ Uso: /concluir <ID>", reply_markup=teclado_principal())
            return
        evento_id = int(context.args[0])
        resultado = concluir_evento(evento_id)
        await update.message.reply_text(str(resultado), reply_markup=teclado_principal())
    except ValueError:
        await update.message.reply_text("❌ ID deve ser um número inteiro.", reply_markup=teclado_principal())
    except Exception as exc:
        await update.message.reply_text(f"❌ Erro ao concluir: {exc}", reply_markup=teclado_principal())

# 🔥 NOVO: ROTEADOR DE TEXTO COM SHUTDOWN SEGURO
async def route_plain_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text: return
    text = update.message.text.strip().lower()

    if text in {"menu", "help"}: await cmd_help(update, context); return
    if text == "start executor": await cmd_start_executor(update, context); return
    if text == "stop executor": await cmd_stop_executor(update, context); return
    if text == "start email": await cmd_start_email(update, context); return
    if text == "stop email": await cmd_stop_email(update, context); return
    if text == "start djen": await cmd_start_djen(update, context); return
    if text == "stop djen": await cmd_stop_djen(update, context); return
    if text == "status": await cmd_status(update, context); return
    if text == "stop all": await cmd_stop_all(update, context); return
    if text == "prazos": await cmd_prazos(update, context); return

    # 🛑 SAFE SHUTDOWN (RESTRITO AO ADMIN)
    if text == "safe shutdown":
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("❌ Acesso negado. Apenas o administrador pode desligar.")
            return
        context.user_data["confirm_shutdown"] = True
        await update.message.reply_text(
            "⚠️ Isso vai parar todos os serviços e desligar o PC.\n"
            "Para confirmar, digite: `CONFIRMAR`",
            parse_mode="Markdown"
        )
        return

    if text == "confirmar":
        if context.user_data.get("confirm_shutdown"):
            await update.message.reply_text("🛑 Parando todos os serviços...")
            msg = stop_all_processos()
            await update.message.reply_text(msg)

            await update.message.reply_text("⏳ Aguardando finalização segura...")
            time.sleep(3)

            await update.message.reply_text("🔻 Desligando sistema...")
            os.system("shutdown now")
        return

async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(f"⚠️ Erro no bot: {context.error}")

# =========================================================
# 🏗️ APP & MAIN
# =========================================================
def build_app() -> Application:
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("menu", cmd_help))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("stop_all", cmd_stop_all))
    app.add_handler(CommandHandler("start_executor", cmd_start_executor))
    app.add_handler(CommandHandler("stop_executor", cmd_stop_executor))
    app.add_handler(CommandHandler("start_email", cmd_start_email))
    app.add_handler(CommandHandler("stop_email", cmd_stop_email))
    app.add_handler(CommandHandler("start_djen", cmd_start_djen))
    app.add_handler(CommandHandler("stop_djen", cmd_stop_djen))
    app.add_handler(CommandHandler("prazos", cmd_prazos))
    app.add_handler(CommandHandler("concluir", cmd_concluir))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, route_plain_text))
    app.add_error_handler(on_error)
    return app

def main() -> None:
    acquire_lock()
    def _sig_handler(signum, frame):
        release_lock()
        raise SystemExit(0)
    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)
    try:
        print("🚀 Iniciando orquestrador...")
        app = build_app()
        app.run_polling(drop_pending_updates=True)
    finally:
        release_lock()

if __name__ == "__main__":
    main()
