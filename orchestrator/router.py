#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Router de comandos do Orquestrador
Versão corrigida + robusta
"""

import os
from pathlib import Path

# =========================
# IMPORTS (SAFE)
# =========================
try:
    from .process_manager import (
        start_bot,
        stop_bot,
        stop_all,
        status_bot,
        start_dashboard,
        stop_dashboard
    )
except ImportError:
    from process_manager import (
        start_bot,
        stop_bot,
        stop_all,
        status_bot,
        start_dashboard,
        stop_dashboard
    )

# =========================
# 📁 BASE PATH
# =========================
BASE_DIR = Path(__file__).resolve().parents[1]

# =========================
# 🔧 COMANDOS (CORRIGIDOS)
# =========================
COMMANDS = {
    "executor": "python -m core.bot",
    "email":    "python -m core.email_service",

    # 🔥 CORREÇÃO AQUI
    "djen":     f"python {BASE_DIR / 'script_djen.py'}"
}

VALID_BOTS = list(COMMANDS.keys())

# =========================
# 🧠 HELP DINÂMICO
# =========================
def get_help():
    bots = "\n".join([f"• start {b}\n• stop {b}" for b in VALID_BOTS])
    return (
        "🤖 COMANDOS DISPONÍVEIS:\n\n"
        "📊 SISTEMA:\n"
        f"{bots}\n"
        "• stop all\n"
        "• status\n\n"
        "📊 DASHBOARD:\n"
        "• start dashboard\n"
        "• stop dashboard\n"
    )

# =========================
# 🧭 PROCESSADOR
# =========================
def process_message(text: str, *args) -> str:
    try:
        if not text:
            return "❌ Comando vazio."

        text = text.lower().strip()
        parts = text.split()
        command = parts[0]

        # =========================
        # DASHBOARD
        # =========================
        if text == "start dashboard":
            return start_dashboard()

        if text == "stop dashboard":
            return stop_dashboard()

        # =========================
        # START
        # =========================
        if command == "start":
            if len(parts) < 2:
                return f"❌ Use: start {' | start '.join(VALID_BOTS)}"

            name = parts[1]

            if name not in VALID_BOTS:
                return f"❌ Bot inválido. Use: {', '.join(VALID_BOTS)}"

            return start_bot(name, COMMANDS[name])

        # =========================
        # STOP
        # =========================
        if command == "stop":
            if len(parts) < 2:
                return "❌ Use: stop executor | stop email | stop djen | stop all"

            name = parts[1]

            if name == "all":
                return stop_all()

            if name not in VALID_BOTS:
                return f"❌ Bot inválido. Use: {', '.join(VALID_BOTS)}"

            return stop_bot(name)

        # =========================
        # STATUS
        # =========================
        if text == "status":
            return status_bot()

        # =========================
        # HELP
        # =========================
        if text in ["help", "ajuda", "/start", "/menu"]:
            return get_help()

        # =========================
        # FALLBACK
        # =========================
        return "⚠️ Comando não reconhecido. Digite 'help'."

    except Exception as e:
        return f"❌ Erro interno: {str(e)}"
