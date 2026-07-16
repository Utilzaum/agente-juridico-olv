#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SISTEMA DE MONITORAMENTO E OBSERVABILIDADE - v2.0
✅ Aponta para controladoria.db (Fonte Única de Verdade)
✅ Correlação jurídica (evento_id, processo, hash)
✅ Rastreabilidade do DJEN (djen_execucao)
"""
import sqlite3
import json
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Any
from functools import wraps

# =========================================================
# 📋 CONFIGURAÇÃO (Passo 2 do Roadmap)
# =========================================================
ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "infra" / "controladoria.db"
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "sistema.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# =========================================================
# 🗄️ INICIALIZAÇÃO DO BANCO (Centralizado)
# =========================================================
def inicializar_monitoramento():
    """Cria tabelas de observabilidade no controladoria.db."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # ✅ Métricas com correlação jurídica
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metricas_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evento_id INTEGER,
            numero_processo TEXT,
            hash_publicacao TEXT,
            operacao TEXT NOT NULL,
            tempo_execucao REAL,
            registros_processados INTEGER,
            sucesso BOOLEAN,
            erro TEXT,
            data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # ✅ Logs estruturados
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs_sistema (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nivel TEXT NOT NULL,
            modulo TEXT,
            mensagem TEXT,
            contexto TEXT,
            data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # ✅ Rastreabilidade do Robô (Auditoria de Duplicidade)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS djen_execucao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inicio TIMESTAMP,
            fim TIMESTAMP,
            cursor_anterior TEXT,
            publicacoes_lidas_api INTEGER,
            publicacoes_novas INTEGER,
            eventos_criados INTEGER,
            duplicatas_ignoradas INTEGER,
            erros INTEGER,
            status TEXT
        )
    """)
    
    conn.commit()
    conn.close()
    logger.info("✅ Observabilidade inicializada em controladoria.db")

# =========================================================
# ⏱️ DECORADOR DE PERFORMANCE (Com contexto jurídico)
# =========================================================
def medir_performance(operacao: str, evento_id: int = None, processo: str = None, hash_pub: str = None):
    """Decorador para medir tempo e correlacionar com o evento."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            inicio = datetime.now()
            sucesso = True
            erro = None
            registros = 0
            try:
                resultado = func(*args, **kwargs)
                if isinstance(resultado, (list, dict)):
                    registros = len(resultado) if isinstance(resultado, list) else 1
                return resultado
            except Exception as e:
                sucesso = False
                erro = str(e)
                raise
            finally:
                fim = datetime.now()
                tempo = (fim - inicio).total_seconds()
                salvar_metrica(
                    operacao=operacao,
                    tempo_execucao=tempo,
                    registros_processados=registros,
                    sucesso=sucesso,
                    erro=erro,
                    evento_id=evento_id,
                    numero_processo=processo,
                    hash_publicacao=hash_pub
                )
        return wrapper
    return decorator

def salvar_metrica(operacao: str, tempo_execucao: float, registros_processados: int = 0,
                   sucesso: bool = True, erro: Optional[str] = None,
                   evento_id: int = None, numero_processo: str = None, hash_publicacao: str = None):
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        """INSERT INTO metricas_performance 
           (evento_id, numero_processo, hash_publicacao, operacao, tempo_execucao, registros_processados, sucesso, erro)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (evento_id, numero_processo, hash_publicacao, operacao, tempo_execucao, registros_processados, sucesso, erro)
    )
    conn.commit()
    conn.close()

# =========================================================
# 🤖 SESSÕES DO DJEN (Rastreabilidade do Robô)
# =========================================================
def iniciar_sessao_djen(cursor_anterior: str) -> int:
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO djen_execucao (inicio, cursor_anterior, status) VALUES (?, ?, 'executando')",
        (datetime.now(), cursor_anterior)
    )
    sessao_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return sessao_id

def finalizar_sessao_djen(sessao_id: int, lidas: int, novas: int, criadas: int, duplicatas: int, erros: int, status: str):
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        """UPDATE djen_execucao 
           SET fim = ?, publicacoes_lidas_api = ?, publicacoes_novas = ?, 
               eventos_criados = ?, duplicatas_ignoradas = ?, erros = ?, status = ?
           WHERE id = ?""",
        (datetime.now(), lidas, novas, criadas, duplicatas, erros, status, sessao_id)
    )
    conn.commit()
    conn.close()
    logger.info(f"🤖 DJEN Sessão #{sessao_id} finalizada: {criadas} criadas, {duplicatas} duplicatas")

inicializar_monitoramento()
