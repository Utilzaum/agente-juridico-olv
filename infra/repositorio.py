#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
REPOSITÓRIO CENTRAL - Camada única de acesso ao banco
✅ Schema alinhado com controladoria.db (2026)
✅ Usa 'descricao' (não 'determinacao_judicial')
✅ Usa 'tipo_contagem' (não 'tipo_prazo')
✅ Usa 'status' (não 'concluido')
✅ Remove 'data_conclusao' (não existe no schema)
✅ Paginação SQL via LIMIT/OFFSET
✅ Funções completas para DJEN + Telegram
"""
import sqlite3
import json
import hashlib
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
import logging

logger = logging.getLogger(__name__)

# =========================================================
# CONFIGURAÇÃO
# =========================================================
DB_PATH = Path(__file__).parent / "controladoria.db"

def conectar() -> sqlite3.Connection:
    """Retorna conexão com row_factory habilitado."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def inicializar_db():
    """Cria todas as tabelas se não existirem."""
    conn = conectar()
    cursor = conn.cursor()
    
    # Tabela de publicações cruas da API
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS publicacoes_djen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hash_api TEXT UNIQUE NOT NULL,
            numero_processo TEXT,
            tribunal TEXT,
            orgao_julgador TEXT,
            tipo_ato TEXT,
            data_disponibilizacao TEXT,
            data_publicacao TEXT,
            json_original TEXT,
            processado INTEGER DEFAULT 0,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Tabela de eventos (prazos processados) - Schema real
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS eventos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_processo TEXT NOT NULL,
            tipo_evento TEXT NOT NULL,
            data_publicacao TEXT NOT NULL,
            inicio_prazo TEXT NOT NULL,
            prazo_final TEXT NOT NULL,
            autor TEXT,
            reu TEXT,
            tribunal TEXT,
            orgao_julgador TEXT,
            descricao TEXT,
            prazo_dias INTEGER,
            tipo_contagem TEXT,
            ramo TEXT,
            urgencia TEXT DEFAULT 'normal',
            resumo TEXT,
            audiencia TEXT,
            status TEXT DEFAULT 'pendente',
            hash_publicacao TEXT,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            atualizado_em TIMESTAMP
        )
    """)
    
    # Tabela de auditoria
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
    
    # Tabela de cursores
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cursores (
            chave TEXT PRIMARY KEY,
            valor TEXT,
            atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Tabela de histórico de status
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historico_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evento_id INTEGER NOT NULL,
            status_anterior TEXT,
            status_novo TEXT NOT NULL,
            motivo TEXT,
            usuario TEXT DEFAULT 'Sistema',
            data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (evento_id) REFERENCES eventos(id)
        )
    """)
    
    # Índices
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_eventos_status ON eventos(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_eventos_prazo ON eventos(prazo_final)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_eventos_processo ON eventos(numero_processo)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_publicacoes_hash ON publicacoes_djen(hash_api)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_auditoria_evento ON auditoria_prazos(evento_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_historico_evento ON historico_status(evento_id)")
    
    conn.commit()
    conn.close()
    logger.info("✅ Banco de dados inicializado")

# =========================================================
# HASH DA PUBLICAÇÃO (Deduplicação)
# =========================================================
def calcular_hash_api(item_api: Dict) -> str:
    """Calcula hash SHA256 do item cru da API."""
    conteudo = json.dumps(item_api, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(conteudo.encode()).hexdigest()

# =========================================================
# CURSORES
# =========================================================
def obter_cursor(chave: str = 'ultima_djen') -> Optional[date]:
    """Busca o valor do cursor pelo nome."""
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT valor FROM cursores WHERE chave = ?", (chave,))
    row = cursor.fetchone()
    conn.close()
    
    if row and row['valor']:
        return datetime.strptime(row['valor'], "%Y-%m-%d").date()
    return None

def atualizar_cursor(chave: str, valor: date):
    """Atualiza ou insere o cursor."""
    conn = conectar()
    conn.execute(
        """INSERT OR REPLACE INTO cursores (chave, valor, atualizado_em)
           VALUES (?, ?, CURRENT_TIMESTAMP)""",
        (chave, valor.strftime("%Y-%m-%d"))
    )
    conn.commit()
    conn.close()
    logger.info(f"💾 Cursor '{chave}' atualizado para {valor.strftime('%d/%m/%Y')}")

# =========================================================
# PUBLICAÇÕES DJEN
# =========================================================
def salvar_publicacao(item_api: Dict) -> Tuple[bool, str]:
    """Salva a publicação crua da API."""
    hash_api = calcular_hash_api(item_api)
    conn = conectar()
    try:
        conn.execute(
            """INSERT INTO publicacoes_djen
               (hash_api, numero_processo, tribunal, orgao_julgador,
                tipo_ato, data_disponibilizacao, data_publicacao, json_original)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                hash_api,
                item_api.get("numeroprocessocommascara") or item_api.get("numeroProcesso"),
                item_api.get("siglaTribunal"),
                item_api.get("nomeOrgao"),
                item_api.get("tipoDocumento") or item_api.get("nomeClasse"),
                item_api.get("dataDisponibilizacao"),
                item_api.get("dataPublicacao"),
                json.dumps(item_api, ensure_ascii=False)
            )
        )
        conn.commit()
        return True, "ok"
    except sqlite3.IntegrityError:
        return False, "duplicata"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

# =========================================================
# EVENTOS
# =========================================================
def salvar_evento(dados: Dict) -> Optional[int]:
    """Salva um evento processado no banco."""
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO eventos
               (numero_processo, tipo_evento, data_publicacao, inicio_prazo,
                prazo_final, autor, reu, tribunal, orgao_julgador,
                descricao, prazo_dias, tipo_contagem, ramo,
                urgencia, resumo, audiencia, hash_publicacao, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pendente')""",
            (
                dados.get("numero_processo"),
                dados.get("tipo_evento"),
                dados.get("data_publicacao"),
                dados.get("inicio_prazo"),
                dados.get("prazo_final"),
                dados.get("autor"),
                dados.get("reu"),
                dados.get("tribunal"),
                dados.get("orgao_julgador"),
                dados.get("descricao"),
                dados.get("prazo_dias"),
                dados.get("tipo_contagem"),
                dados.get("ramo"),
                dados.get("urgencia", "normal"),
                dados.get("resumo"),
                dados.get("audiencia"),
                dados.get("hash_publicacao"),
            )
        )
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Erro ao salvar evento: {e}")
        return None
    finally:
        conn.close()

def buscar_eventos_pendentes(limit: int = None, offset: int = None) -> List[Dict]:
    """Lista todos os eventos pendentes ordenados por prazo."""
    conn = conectar()
    cursor = conn.cursor()
    
    query = """
        SELECT id, numero_processo, tipo_evento, descricao, data_publicacao,
               inicio_prazo, prazo_final, autor, reu, tribunal,
               orgao_julgador, urgencia, prazo_dias, tipo_contagem, status
        FROM eventos
        WHERE status = 'pendente' OR status IS NULL
        ORDER BY prazo_final ASC, id DESC
    """
    
    if limit and offset is not None:
        query += f" LIMIT {limit} OFFSET {offset}"
    elif limit:
        query += f" LIMIT {limit}"
    
    cursor.execute(query)
    eventos = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return eventos

def buscar_evento_por_id(evento_id: int) -> Optional[Dict]:
    """Busca um evento específico pelo ID."""
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM eventos WHERE id = ?", (evento_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

# =========================================================
# AÇÕES SOBRE EVENTOS
# =========================================================
def concluir_evento(evento_id: int, motivo: str = "Não informado", usuario: str = "Sistema") -> str:
    """Conclui um evento e registra na auditoria."""
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM eventos WHERE id = ?", (evento_id,))
        row = cursor.fetchone()
        if not row:
            return f"❌ Evento #{evento_id} não encontrado"
        
        status_anterior = row['status']
        
        cursor.execute(
            """UPDATE eventos
               SET status = 'concluido', atualizado_em = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (evento_id,)
        )
        
        cursor.execute(
            """INSERT INTO auditoria_prazos (evento_id, acao, motivo, usuario)
               VALUES (?, 'CONCLUIDO', ?, ?)""",
            (evento_id, motivo, usuario)
        )
        
        cursor.execute(
            """INSERT INTO historico_status (evento_id, status_anterior, status_novo, motivo, usuario)
               VALUES (?, ?, 'CONCLUIDO', ?, ?)""",
            (evento_id, status_anterior, motivo, usuario)
        )
        
        conn.commit()
        return f"✅ Evento #{evento_id} concluído com sucesso."
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def corrigir_prazo(evento_id: int, nova_data: date, motivo: str = "Correção manual", usuario: str = "Sistema") -> str:
    """Corrige o prazo final de um evento."""
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT prazo_final, status FROM eventos WHERE id = ?", (evento_id,))
        row = cursor.fetchone()
        if not row:
            return f"❌ Evento #{evento_id} não encontrado"
        
        prazo_antigo = row['prazo_final']
        
        cursor.execute(
            """UPDATE eventos
               SET prazo_final = ?, atualizado_em = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (nova_data.strftime("%Y-%m-%d"), evento_id)
        )
        
        cursor.execute(
            """INSERT INTO auditoria_prazos (evento_id, acao, motivo, usuario, observacao)
               VALUES (?, 'CORRIGIDO', ?, ?, ?)""",
            (evento_id, f"Prazo alterado de {prazo_antigo} para {nova_data.strftime('%Y-%m-%d')}",
             usuario, f"Prazo anterior: {prazo_antigo}")
        )
        
        cursor.execute(
            """INSERT INTO historico_status (evento_id, status_anterior, status_novo, motivo, usuario)
               VALUES (?, 'CORRIGIDO', 'CORRIGIDO', ?, ?)""",
            (evento_id, motivo, usuario)
        )
        
        conn.commit()
        return f"✅ Prazo #{evento_id} corrigido para {nova_data.strftime('%d/%m/%Y')}"
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def reabrir_evento(evento_id: int, motivo: str = "Reabertura manual", usuario: str = "Sistema") -> str:
    """Reabre um evento concluído."""
    conn = conectar()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM eventos WHERE id = ?", (evento_id,))
        row = cursor.fetchone()
        if not row:
            return f"❌ Evento #{evento_id} não encontrado"
        
        status_anterior = row['status']
        
        cursor.execute(
            """UPDATE eventos
               SET status = 'pendente', atualizado_em = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (evento_id,)
        )
        
        cursor.execute(
            """INSERT INTO auditoria_prazos (evento_id, acao, motivo, usuario)
               VALUES (?, 'REABERTO', ?, ?)""",
            (evento_id, motivo, usuario)
        )
        
        cursor.execute(
            """INSERT INTO historico_status (evento_id, status_anterior, status_novo, motivo, usuario)
               VALUES (?, ?, 'REABERTO', ?, ?)""",
            (evento_id, status_anterior, motivo, usuario)
        )
        
        conn.commit()
        return f"✅ Evento #{evento_id} reaberto."
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# =========================================================
# AUDITORIA
# =========================================================
def listar_auditoria(evento_id: Optional[int] = None, limite: int = 50) -> List[Dict]:
    """Lista registros de auditoria, filtrando por evento se especificado."""
    conn = conectar()
    cursor = conn.cursor()
    
    if evento_id:
        cursor.execute(
            """SELECT a.*, e.numero_processo, e.tipo_evento
               FROM auditoria_prazos a
               LEFT JOIN eventos e ON a.evento_id = e.id
               WHERE a.evento_id = ?
               ORDER BY a.data_hora DESC
               LIMIT ?""",
            (evento_id, limite)
        )
    else:
        cursor.execute(
            """SELECT a.*, e.numero_processo, e.tipo_evento
               FROM auditoria_prazos a
               LEFT JOIN eventos e ON a.evento_id = e.id
               ORDER BY a.data_hora DESC
               LIMIT ?""",
            (limite,)
        )
    
    resultados = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return resultados

def listar_concluidos(limite: int = 20) -> List[Dict]:
    """Lista eventos concluídos com dados de auditoria."""
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT e.*, a.motivo as motivo_conclusao, a.data_hora as data_conclusao
           FROM eventos e
           LEFT JOIN auditoria_prazos a ON e.id = a.evento_id AND a.acao = 'CONCLUIDO'
           WHERE e.status = 'concluido'
           ORDER BY a.data_hora DESC
           LIMIT ?""",
        (limite,)
    )
    resultados = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return resultados

# =========================================================
# INICIALIZAÇÃO AUTOMÁTICA
# =========================================================
try:
    inicializar_db()
except Exception as e:
    logger.warning(f"⚠️ Não foi possível inicializar o banco: {e}")
