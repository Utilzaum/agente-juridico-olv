#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
infra/db.py — Camada de Acesso ao Banco (SQLite)
✅ Schema completo com todos os campos jurídicos
✅ Migração automática de schema
✅ Verificação robusta de duplicidade
✅ Separação clara entre pendentes/concluídos
✅ Boot automático com inicialização garantida
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

# 📁 CONFIG
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "eventos.db"

# =========================
# 🔌 CONEXÃO
# =========================
@contextmanager
def conectar():
    """
    Context manager seguro para conexões SQLite.
    - Auto-close
    - Rollback automático em erro
    - WAL mode para melhor performance
    """
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# =========================
# ️ CRIAÇÃO DE SCHEMA
# =========================
def criar_tabelas():
    """Cria tabelas se não existirem."""
    with conectar() as conn:
        cursor = conn.cursor()
        
        # Tabela de processos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero TEXT UNIQUE NOT NULL,
                tribunal TEXT,
                data_ultima_movimentacao TEXT,
                ativo INTEGER DEFAULT 1,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_processos_numero ON processos(numero)")
        
        # Tabela de eventos (prazos) - Schema completo
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS eventos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero_processo TEXT NOT NULL,
                descricao TEXT,
                tipo_evento TEXT,
                prazo_dias INTEGER,
                tipo_prazo TEXT,
                
                -- Datas importantes
                data_publicacao TEXT,
                inicio_prazo TEXT,
                prazo_final TEXT,
                
                -- Partes envolvidas
                autor TEXT,
                reu TEXT,
                
                -- Informações do tribunal
                tribunal TEXT,
                orgao_julgador TEXT,
                
                -- Classificação
                urgencia TEXT,
                resumo TEXT,
                
                -- Status
                status TEXT DEFAULT 'pendente',
                concluido INTEGER DEFAULT 0,
                
                -- Conclusão
                motivo_conclusao TEXT,
                data_conclusao TEXT,
                
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Índices para performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_eventos_processo ON eventos(numero_processo)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_eventos_prazo ON eventos(prazo_final)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_eventos_status ON eventos(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_eventos_concluido ON eventos(concluido)")

def atualizar_schema():
    """
    Migração incremental: adiciona colunas novas em bancos existentes.
    Executa apenas se as colunas não existirem.
    """
    colunas_novas = [
        ("motivo_conclusao", "TEXT"),
        ("data_conclusao", "TEXT"),
        ("autor", "TEXT"),
        ("reu", "TEXT"),
        ("tribunal", "TEXT"),
        ("orgao_julgador", "TEXT"),
        ("data_publicacao", "TEXT"),
        ("inicio_prazo", "TEXT"),
    ]
    
    with conectar() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(eventos)")
        colunas_existentes = {row[1] for row in cursor.fetchall()}
        
        for nome_coluna, tipo in colunas_novas:
            if nome_coluna not in colunas_existentes:
                try:
                    cursor.execute(f"ALTER TABLE eventos ADD COLUMN {nome_coluna} {tipo}")
                    logger.info(f"✅ Coluna '{nome_coluna}' adicionada à tabela eventos")
                except sqlite3.OperationalError as e:
                    logger.warning(f"⚠️ Não foi possível adicionar coluna '{nome_coluna}': {e}")

def inicializar_db():
    """Inicializa o banco de dados: cria tabelas e aplica migrações."""
    logger.info("️ Inicializando banco de dados...")
    criar_tabelas()
    atualizar_schema()
    logger.info("✅ Banco de dados inicializado com sucesso")

# =========================
# 🔍 QUERIES AUXILIARES
# =========================
def existe_evento_pendente(numero_processo: str, descricao: str, prazo_final: str) -> bool:
    """
    Verifica se já existe um evento pendente com mesmos dados.
    Evita duplicação quando o DJEN busca no dia seguinte.
    """
    with conectar() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 1 FROM eventos
            WHERE numero_processo = ?
              AND descricao = ?
              AND prazo_final = ?
              AND concluido = 0
            LIMIT 1
        """, (numero_processo, descricao, prazo_final))
        return cursor.fetchone() is not None

# =========================
# ➕ INSERÇÃO DE EVENTOS
# =========================
def inserir_evento(dados: Dict[str, Any]) -> bool:
    """
    Insere um evento no banco com verificação de duplicidade.
    
    Args:
        dados: Dicionário com campos do evento
        
    Returns:
        bool: True se inserido, False se duplicado
    """
    # Padronização de datas para YYYY-MM-DD
    def padronizar_data(data_raw: Any) -> Optional[str]:
        if not data_raw:
            return None
        try:
            # Tenta formato ISO
            return datetime.strptime(str(data_raw).split("T")[0], "%Y-%m-%d").strftime("%Y-%m-%d")
        except Exception:
            try:
                # Tenta formato brasileiro
                return datetime.strptime(str(data_raw)[:10], "%d/%m/%Y").strftime("%Y-%m-%d")
            except Exception:
                return str(data_raw)
    
    prazo_final = padronizar_data(dados.get("prazo_final"))
    data_publicacao = padronizar_data(dados.get("data_publicacao"))
    inicio_prazo = padronizar_data(dados.get("inicio_prazo"))
    
    numero_processo = dados.get("numero_processo")
    descricao = (dados.get("determinacao_judicial") or dados.get("descricao") or "Intimação").strip()
    
    # Verifica duplicidade
    if existe_evento_pendente(numero_processo, descricao, prazo_final):
        logger.info(f"⏭️ Evento duplicado ignorado: {numero_processo} - {descricao}")
        return False
    
    with conectar() as conn:
        cursor = conn.cursor()
        
        # Garante que o processo existe
        cursor.execute(
            "INSERT OR IGNORE INTO processos (numero) VALUES (?)",
            (numero_processo,)
        )
        
        # Insere evento com todos os campos
        cursor.execute("""
            INSERT INTO eventos (
                numero_processo,
                descricao,
                tipo_evento,
                prazo_dias,
                tipo_prazo,
                data_publicacao,
                inicio_prazo,
                prazo_final,
                autor,
                reu,
                tribunal,
                orgao_julgador,
                urgencia,
                resumo
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            numero_processo,
            descricao,
            dados.get("tipo_evento"),
            dados.get("prazo_dias"),
            dados.get("tipo_prazo"),
            data_publicacao,
            inicio_prazo,
            prazo_final,
            dados.get("autor"),
            dados.get("reu"),
            dados.get("tribunal"),
            dados.get("orgao_julgador"),
            dados.get("urgencia"),
            dados.get("resumo"),
        ))
        
        logger.info(f"✅ Evento inserido: {numero_processo} - {descricao}")
        return True

# =========================
# 📊 LISTAGEM DE EVENTOS
# =========================
def listar_eventos_pendentes() -> List[sqlite3.Row]:
    """Retorna todos os eventos pendentes ordenados por prazo."""
    with conectar() as conn:
        return conn.execute("""
            SELECT * FROM eventos
            WHERE status = 'pendente' AND concluido = 0
            ORDER BY prazo_final ASC, urgencia DESC
        """).fetchall()

def listar_eventos_concluidos(limite: Optional[int] = None) -> List[sqlite3.Row]:
    """
    Retorna eventos concluídos para histórico.
    
    Args:
        limite: Quantidade máxima de registros (None = todos)
    """
    query = """
        SELECT * FROM eventos
        WHERE status = 'concluido' OR concluido = 1
        ORDER BY data_conclusao DESC
    """
    if limite:
        query += f" LIMIT {limite}"
    
    with conectar() as conn:
        return conn.execute(query).fetchall()

def listar_processos() -> List[sqlite3.Row]:
    """Retorna todos os processos ordenados por última movimentação."""
    with conectar() as conn:
        return conn.execute("""
            SELECT * FROM processos
            ORDER BY data_ultima_movimentacao DESC
        """).fetchall()

# =========================
# 🔄 ATUALIZAÇÕES
# =========================
def atualizar_processo(numero: str, tribunal: Optional[str] = None, data: Optional[str] = None):
    """
    Atualiza ou cria processo com UPSERT.
    
    Args:
        numero: Número do processo
        tribunal: Nome do tribunal
        data: Data da última movimentação
    """
    with conectar() as conn:
        conn.execute("""
            INSERT INTO processos (numero, tribunal, data_ultima_movimentacao)
            VALUES (?, ?, ?)
            ON CONFLICT(numero) DO UPDATE SET
                data_ultima_movimentacao = excluded.data_ultima_movimentacao,
                tribunal = COALESCE(excluded.tribunal, processos.tribunal)
        """, (numero, tribunal, data))

def concluir_evento(evento_id: int, motivo: str = "Não informado") -> bool:
    """
    Marca evento como concluído com motivo e data.
    
    Args:
        evento_id: ID do evento
        motivo: Motivo da conclusão
        
    Returns:
        bool: True se atualizado, False se não encontrado
    """
    data_conclusao = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with conectar() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE eventos
            SET concluido = 1,
                status = 'concluido',
                motivo_conclusao = ?,
                data_conclusao = ?
            WHERE id = ? AND concluido = 0
        """, (motivo, data_conclusao, evento_id))
        
        if cursor.rowcount > 0:
            logger.info(f"✅ Evento {evento_id} concluído: {motivo}")
            return True
        else:
            logger.warning(f"⚠️ Evento {evento_id} não encontrado ou já concluído")
            return False

def buscar_evento_por_id(evento_id: int) -> Optional[sqlite3.Row]:
    """Busca um evento específico pelo ID."""
    with conectar() as conn:
        return conn.execute(
            "SELECT * FROM eventos WHERE id = ?",
            (evento_id,)
        ).fetchone()

def contar_prazos_por_urgencia() -> List[sqlite3.Row]:
    """Retorna contagem de prazos pendentes por nível de urgência."""
    with conectar() as conn:
        return conn.execute("""
            SELECT urgencia, COUNT(*) as total
            FROM eventos
            WHERE status = 'pendente' AND concluido = 0
            GROUP BY urgencia
        """).fetchall()

def estatisticas_gerais() -> Dict[str, int]:
    """Retorna estatísticas gerais do sistema."""
    with conectar() as conn:
        cursor = conn.cursor()
        
        # Total de eventos
        cursor.execute("SELECT COUNT(*) FROM eventos")
        total_eventos = cursor.fetchone()[0]
        
        # Pendentes
        cursor.execute("SELECT COUNT(*) FROM eventos WHERE concluido = 0")
        pendentes = cursor.fetchone()[0]
        
        # Concluídos
        cursor.execute("SELECT COUNT(*) FROM eventos WHERE concluido = 1")
        concluidos = cursor.fetchone()[0]
        
        # Vencidos
        cursor.execute("""
            SELECT COUNT(*) FROM eventos
            WHERE concluido = 0 AND prazo_final < date('now')
        """)
        vencidos = cursor.fetchone()[0]
        
        return {
            "total_eventos": total_eventos,
            "pendentes": pendentes,
            "concluidos": concluidos,
            "vencidos": vencidos,
            "total_processos": cursor.execute("SELECT COUNT(*) FROM processos").fetchone()[0]
        }
