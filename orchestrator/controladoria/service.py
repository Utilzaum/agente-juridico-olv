#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Serviço de Controladoria - Fonte Única de Verdade
✅ CAMINHO: controladoria.db (não eventos.db)
✅ SCHEMA: descricao, tipo_contagem, status (schema real)
✅ AUDITORIA: tabela auditoria_prazos com data_hora
✅ COLUNAS: removidas determinacao_judicial, tipo_prazo, data_conclusao
"""
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)

# =========================================================
# 🔧 CORREÇÃO 1: CAMINHO CORRETO DO BANCO
# =========================================================
# __file__ = orchestrator/controladoria/service.py
# parents[0] = orchestrator/controladoria
# parents[1] = orchestrator
# parents[2] = raiz do projeto (agente_juridico)
ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "infra" / "controladoria.db"

def get_conn() -> sqlite3.Connection:
    """Retorna conexão com o banco de dados."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Banco não encontrado: {DB_PATH}")
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def listar_eventos() -> List[Dict]:
    """
    Lista todos os eventos PENDENTES do sistema.
    ✅ Schema corrigido para controladoria.db
    ✅ Usa 'descricao' (não 'determinacao_judicial')
    ✅ Usa 'tipo_contagem' (não 'tipo_prazo')
    """
    conn = get_conn()
    cursor = conn.cursor()
    
    # ✅ CORREÇÃO: Colunas reais do schema atual
    cursor.execute("""
        SELECT
            id,
            numero_processo,
            descricao,
            tipo_evento,
            prazo_final,
            urgencia,
            status,
            resumo,
            tribunal,
            orgao_julgador,
            autor,
            reu,
            data_publicacao,
            inicio_prazo,
            prazo_dias,
            tipo_contagem
        FROM eventos
        WHERE status = 'pendente' OR status IS NULL
        ORDER BY prazo_final ASC, id DESC
    """)
    
    eventos = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return eventos

def concluir_evento(evento_id: int, motivo: str = "Não informado", usuario: str = "Sistema") -> str:
    """
    Conclui um evento e registra na auditoria.
    ✅ CORREÇÃO: Remove 'data_conclusao' (não existe no schema)
    ✅ CORREÇÃO: Usa 'auditoria_prazos' e 'data_hora'
    """
    conn = get_conn()
    cursor = conn.cursor()
    
    try:
        # Atualiza status do evento
        cursor.execute("""
            UPDATE eventos
            SET status = 'concluido',
                atualizado_em = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (evento_id,))
        
        if cursor.rowcount == 0:
            return f" Evento #{evento_id} não encontrado"
        
        # ✅ CORREÇÃO: Tabela 'auditoria_prazos' + coluna 'data_hora'
        cursor.execute("""
            INSERT INTO auditoria_prazos (
                evento_id,
                acao,
                motivo,
                usuario,
                data_hora
            ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (evento_id, "CONCLUIDO", motivo, usuario))
        
        conn.commit()
        return f"✅ Evento #{evento_id} concluído com sucesso."
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao concluir evento: {e}", exc_info=True)
        raise e
    finally:
        conn.close()

def listar_concluidos(limite: int = 20) -> List[Dict]:
    """
    Lista eventos concluídos com histórico de auditoria.
    ✅ CORREÇÃO: Usa 'auditoria_prazos' e 'data_hora'
    ✅ CORREÇÃO: ORDER BY a.data_hora (não e.data_conclusao)
    """
    conn = get_conn()
    cursor = conn.cursor()
    
    # ✅ CORREÇÃO: JOIN com tabela 'auditoria_prazos' + 'data_hora'
    cursor.execute("""
        SELECT
            e.id,
            e.numero_processo,
            e.tipo_evento,
            e.data_publicacao,
            e.prazo_final,
            e.autor,
            e.tribunal,
            e.orgao_julgador,
            e.descricao,
            a.motivo as motivo_conclusao,
            a.data_hora as data_conclusao,
            a.usuario
        FROM eventos e
        LEFT JOIN auditoria_prazos a ON e.id = a.evento_id AND a.acao = 'CONCLUIDO'
        WHERE e.status = 'concluido'
        ORDER BY a.data_hora DESC
        LIMIT ?
    """, (limite,))
    
    resultados = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return resultados

def atualizar_prazo(evento_id: int, nova_data: date, usuario: str = "Sistema") -> str:
    """
    Atualiza o prazo_final de um evento e registra na auditoria.
    ✅ CORREÇÃO: Remove 'data_conclusao'
    ✅ CORREÇÃO: Usa 'auditoria_prazos' e 'data_hora'
    """
    conn = get_conn()
    cursor = conn.cursor()
    
    try:
        # Busca prazo atual para auditoria
        cursor.execute(
            "SELECT prazo_final FROM eventos WHERE id = ?",
            (evento_id,)
        )
        row = cursor.fetchone()
        
        if not row:
            return f"❌ Evento #{evento_id} não encontrado"
        
        prazo_antigo = row['prazo_final']
        
        # Atualiza prazo
        cursor.execute("""
            UPDATE eventos
            SET prazo_final = ?,
                atualizado_em = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (nova_data.strftime("%Y-%m-%d"), evento_id))
        
        # ✅ CORREÇÃO: Tabela 'auditoria_prazos'
        cursor.execute("""
            INSERT INTO auditoria_prazos (
                evento_id,
                acao,
                motivo,
                usuario,
                data_hora,
                observacao
            ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
        """, (
            evento_id,
            "CORRIGIDO",
            f"Alteração de prazo: {prazo_antigo} → {nova_data.strftime('%Y-%m-%d')}",
            usuario,
            f"Prazo anterior: {prazo_antigo}"
        ))
        
        conn.commit()
        return f"✅ Prazo #{evento_id} atualizado para {nova_data.strftime('%d/%m/%Y')}"
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao atualizar prazo: {e}", exc_info=True)
        raise e
    finally:
        conn.close()

def reabrir_evento(evento_id: int, motivo: str = "Republicação", usuario: str = "Sistema") -> str:
    """
    Reabre um prazo concluído.
    ✅ CORREÇÃO: Remove 'data_conclusao=NULL'
    ✅ CORREÇÃO: Usa 'auditoria_prazos' e 'data_hora'
    """
    conn = get_conn()
    cursor = conn.cursor()
    
    try:
        # Reverte status
        cursor.execute("""
            UPDATE eventos
            SET status = 'pendente',
                atualizado_em = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (evento_id,))
        
        # ✅ CORREÇÃO: Tabela 'auditoria_prazos'
        cursor.execute("""
            INSERT INTO auditoria_prazos (
                evento_id,
                acao,
                motivo,
                usuario,
                data_hora
            ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (evento_id, "REABERTO", motivo, usuario))
        
        conn.commit()
        return f"✅ Evento #{evento_id} reaberto."
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro ao reabrir evento: {e}", exc_info=True)
        raise e
    finally:
        conn.close()

# =========================================================
# ✅ INICIALIZAÇÃO DO SCHEMA (ALINHADO COM SCHEMA REAL)
# =========================================================
def inicializar_schema():
    """
    Garante que o schema esteja correto no controladoria.db
    ✅ ALINHADO COM SCHEMA REAL DO BANCO
    """
    conn = get_conn()
    cursor = conn.cursor()
    
    # Tabela de eventos (schema real)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS eventos (
            id INTEGER PRIMARY KEY,
            publicacao_id INTEGER,
            hash_evento TEXT UNIQUE,
            numero_processo TEXT,
            tipo_evento TEXT,
            descricao TEXT,
            tribunal TEXT,
            orgao_julgador TEXT,
            autor TEXT,
            reu TEXT,
            data_publicacao TEXT,
            inicio_prazo TEXT,
            prazo_final TEXT,
            prazo_dias INTEGER,
            tipo_contagem TEXT,
            urgencia TEXT,
            status TEXT,
            criado_em TIMESTAMP,
            atualizado_em TIMESTAMP,
            hash_publicacao TEXT,
            FOREIGN KEY(publicacao_id) REFERENCES publicacoes_djen(id)
        )
    """)
    
    # ✅ CORREÇÃO: Tabela 'auditoria_prazos' (não 'auditoria')
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS auditoria_prazos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evento_id INTEGER NOT NULL,
            acao TEXT NOT NULL,
            motivo TEXT,
            usuario TEXT DEFAULT 'Sistema',
            data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            observacao TEXT,
            FOREIGN KEY (evento_id) REFERENCES eventos(id)
        )
    """)
    
    # Índices
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_eventos_status ON eventos(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_eventos_prazo ON eventos(prazo_final)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_eventos_processo ON eventos(numero_processo)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_auditoria_evento ON auditoria_prazos(evento_id)")
    
    conn.commit()
    conn.close()
    logger.info("✅ Schema inicializado em controladoria.db")

# Inicializa automaticamente ao importar
try:
    inicializar_schema()
except Exception as e:
    logger.warning(f"⚠️ Não foi possível inicializar schema: {e}")
