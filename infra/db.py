#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
infra/db.py — Camada de Acesso ao Banco (SQLite)
✅ Banco único centralizado (eventos.db)
✅ Garantia de processos + duplicidade robusta
✅ Queries separadas (pendentes/concluídos)
✅ Boot automático com inicializar_db()
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime

# 📁 CONFIG
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "eventos.db"

# =========================
# 🔌 CONEXÃO
# =========================
@contextmanager
def conectar():
    """Context manager seguro: auto-close + rollback em erro."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")  # Performance + segurança
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# =========================
# 🧱 CRIAR TABELAS
# =========================
def criar_tabelas():
    with conectar() as conn:
        cursor = conn.cursor()
        
        # TABELA DE PROCESSOS (GARANTE BASE INTEGRAL)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS processos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT UNIQUE,
            tribunal TEXT,
            data_ultima_movimentacao TEXT,
            ativo INTEGER DEFAULT 1,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_processos_numero ON processos(numero)")

        # TABELA DE EVENTOS (PRAZOS)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS eventos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_processo TEXT,
            descricao TEXT,
            tipo_evento TEXT,
            prazo_dias INTEGER,
            tipo_prazo TEXT,
            prazo_final TEXT,  -- ✅ PADRONIZADO ISO 8601 (YYYY-MM-DD)
            urgencia TEXT,
            resumo TEXT,
            status TEXT DEFAULT 'pendente',
            concluido INTEGER DEFAULT 0,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_eventos_processo ON eventos(numero_processo)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_eventos_prazo ON eventos(prazo_final)")
        
        conn.commit()

# =========================
# 🚀 BOOT
# =========================
def inicializar_db():
    """Garante que o banco e tabelas existam antes de qualquer query."""
    criar_tabelas()

# =========================
# ➕ INSERIR EVENTO (COM CONTROLE ROBUSTO)
# =========================
def inserir_evento(dados: dict) -> bool:
    """Insere evento garantindo processo, validando duplicidade e padronizando data."""
    # Padronização de data para YYYY-MM-DD
    prazo_final_raw = dados.get("prazo_final")
    if prazo_final_raw:
        try:
            prazo_final = datetime.strptime(str(prazo_final_raw).split("T")[0], "%Y-%m-%d").strftime("%Y-%m-%d")
        except Exception:
            prazo_final = str(prazo_final_raw)
    else:
        prazo_final = None

    # ✅ CORREÇÃO: usa "numero_processo" em vez de "processo"
    numero_processo = dados.get("numero_processo")
    descricao = (dados.get("determinacao_judicial") or "Intimação").strip()

    with conectar() as conn:
        cursor = conn.cursor()
        
        # GARANTIA DE PROCESSO EXISTENTE
        cursor.execute("INSERT OR IGNORE INTO processos (numero) VALUES (?)", (numero_processo,))

        # DUPLICIDADE ROBUSTA (numero_processo + prazo + contexto)
        cursor.execute("""
            SELECT 1 FROM eventos
            WHERE numero_processo = ? AND prazo_final = ? AND descricao = ?
        """, (numero_processo, prazo_final, descricao))
        
        if cursor.fetchone():
            return False  # Duplicata ignorada com segurança

        # ✅ CORREÇÃO: INSERT com "numero_processo" em vez de "processo"
        cursor.execute("""
        INSERT INTO eventos (
            numero_processo,
            tipo_evento,
            prazo_dias,
            tipo_prazo,
            prazo_final,
            urgencia,
            resumo
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            numero_processo,
            dados.get("tipo_evento"),
            dados.get("prazo_dias"),
            dados.get("tipo_prazo"),
            prazo_final,
            dados.get("urgencia"),
            dados.get("resumo"),
        ))

        conn.commit()
    return True

# =========================
# 📊 LISTAGEM SEPARADA POR STATUS
# =========================
def listar_eventos_pendentes():
    """Retorna APENAS prazos ativos/urgentes."""
    with conectar() as conn:
        return conn.execute("""
            SELECT * FROM eventos
            WHERE status = 'pendente' AND concluido = 0
            ORDER BY prazo_final ASC
        """).fetchall()

def listar_eventos_concluidos():
    """Retorna APENAS prazos finalizados (para histórico/métricas)."""
    with conectar() as conn:
        return conn.execute("""
            SELECT * FROM eventos
            WHERE status = 'concluido' OR concluido = 1
            ORDER BY prazo_final DESC
        """).fetchall()

def listar_processos():
    with conectar() as conn:
        return conn.execute("SELECT * FROM processos ORDER BY data_ultima_movimentacao DESC").fetchall()

# =========================
# 🔄 ATUALIZAÇÕES
# =========================
def atualizar_processo(numero, tribunal=None, data=None):
    """Atualiza ou cria processo com UPSERT (ON CONFLICT)."""
    with conectar() as conn:
        conn.execute("""
            INSERT INTO processos (numero, tribunal, data_ultima_movimentacao)
            VALUES (?, ?, ?)
            ON CONFLICT(numero) DO UPDATE SET
                data_ultima_movimentacao = excluded.data_ultima_movimentacao,
                tribunal = COALESCE(excluded.tribunal, processos.tribunal)
        """, (numero, tribunal, data))
        conn.commit()

def concluir_evento(evento_id: int) -> bool:
    with conectar() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE eventos
            SET concluido = 1, status = 'concluido'
            WHERE id = ?
        """, (evento_id,))
        conn.commit()
        return cursor.rowcount > 0
