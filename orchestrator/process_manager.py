#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import shlex
import os
from typing import Dict

# =========================
# 📁 BASE DIR (ESSENCIAL)
# =========================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

processos: Dict[str, subprocess.Popen] = {}

# =========================
# 🚀 START BOT
# =========================
def start_bot(nome: str, comando: str) -> str:
    if nome in processos:
        proc = processos[nome]
        if proc.poll() is None:
            return f"⚠️ {nome} já está rodando (PID {proc.pid})"
        else:
            del processos[nome]

    try:
        proc = subprocess.Popen(
            shlex.split(comando),
            start_new_session=True,
            cwd=BASE_DIR
        )
        processos[nome] = proc
        return f"✅ {nome} iniciado (PID {proc.pid})"
    except Exception as e:
        return f"❌ Falha ao iniciar {nome}: {str(e)}"

# =========================
# 🛑 STOP BOT
# =========================
def stop_bot(nome: str) -> str:
    if nome not in processos:
        return f"⚠️ {nome} não está rodando"

    proc = processos[nome]

    try:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    except Exception:
        pass

    del processos[nome]
    return f"🛑 {nome} parado"

# =========================
# 📊 STATUS (STRING - compatível Telegram)
# =========================
def status_bot(nome: str = None) -> str:
    if nome:
        if nome not in processos:
            return f"🔴 {nome} parado"

        proc = processos[nome]

        if proc.poll() is not None:
            del processos[nome]
            return f"🔴 {nome} caiu"

        return f"🟢 {nome} rodando (PID {proc.pid})"

    if not processos:
        return "📭 Nenhum serviço em execução."

    return "\n".join([status_bot(n) for n in list(processos.keys())])

# =========================
# 📊 STATUS (DICT - dashboard/API)
# =========================
def get_status_dict():
    status = {}

    for nome, proc in list(processos.items()):
        rodando = proc.poll() is None

        if not rodando:
            del processos[nome]
            continue

        status[nome] = {
            "pid": proc.pid,
            "running": True
        }

    return status

# =========================
# 🛑 STOP ALL
# =========================
def stop_all() -> str:
    if not processos:
        return "⚠️ Nenhum processo rodando"

    respostas = []

    for nome, proc in list(processos.items()):
        try:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        except Exception:
            pass

        respostas.append(f"🛑 {nome} parado")

    processos.clear()
    return "\n".join(respostas)

# =========================
# 📊 DASHBOARD
# =========================
def start_dashboard() -> str:
    if "dashboard" in processos:
        proc = processos["dashboard"]
        if proc.poll() is None:
            return f"⚠️ Dashboard já está rodando (PID {proc.pid})"
        else:
            del processos["dashboard"]

    dashboard_path = os.path.join(BASE_DIR, "dashboard.py")

    try:
        proc = subprocess.Popen(
            [
                "streamlit",
                "run",
                dashboard_path,
                "--server.headless", "true",
                "--server.port", "8501"
            ],
            cwd=BASE_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        processos["dashboard"] = proc

        return f"📊 Dashboard iniciado (PID {proc.pid})\n🌐 http://localhost:8501"

    except FileNotFoundError:
        return "❌ Streamlit não encontrado. Execute: pip install streamlit"

    except Exception as e:
        return f"❌ Erro ao iniciar dashboard: {e}"

# =========================
# 🛑 STOP DASHBOARD
# =========================
def stop_dashboard() -> str:
    return stop_bot("dashboard")
