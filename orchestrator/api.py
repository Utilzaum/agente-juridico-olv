#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API REST do Orquestrador - FastAPI
Endpoints para controle de bots e serviços via HTTP
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ✅ IMPORT ATUALIZADO: get_status_dict no lugar de status_bot
from orchestrator.process_manager import (
    start_bot,
    stop_bot,
    stop_all,
    get_status_dict,  # ← NOVO
    start_dashboard,
    stop_dashboard
)

app = FastAPI(
    title="Orquestrador OLV",
    description="API para gerenciamento de bots jurídicos",
    version="1.0.0"
)

# CORS para permitir acesso do dashboard Streamlit
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# 📊 STATUS (ATUALIZADO)
# =========================
@app.get("/status")
def status():
    """Retorna status estruturado de todos os bots."""
    return {"success": True, "status": get_status_dict()}

# =========================
# ▶️ START
# =========================
@app.post("/start/{bot_name}")
def start(bot_name: str):
    """Inicia um bot ou serviço específico."""
    if bot_name == "dashboard":
        return {"success": True, "msg": start_dashboard()}
    
    # Ajuste conforme sua estrutura de módulos
    comando = f"python -m core.{bot_name}" if bot_name != "djen" else "python script_djen.py"
    return {"success": True, "msg": start_bot(bot_name, comando)}

# =========================
# ⏹️ STOP
# =========================
@app.post("/stop/{bot_name}")
def stop(bot_name: str):
    """Para um bot ou serviço específico."""
    if bot_name == "all":
        return {"success": True, "msg": stop_all()}
    if bot_name == "dashboard":
        return {"success": True, "msg": stop_dashboard()}
    
    return {"success": True, "msg": stop_bot(bot_name)}

# =========================
# 🏥 HEALTH CHECK
# =========================
@app.get("/health")
def health():
    """Endpoint simples para verificar se a API está rodando."""
    return {"status": "ok", "service": "orquestrador-api"}

# =========================
# 📋 ROOT
# =========================
@app.get("/")
def root():
    """Documentação básica da API."""
    return {
        "message": "Orquestrador OLV API",
        "docs": "/docs",
        "endpoints": [
            "GET /status",
            "POST /start/{bot_name}",
            "POST /stop/{bot_name}",
            "GET /health"
        ]
    }
