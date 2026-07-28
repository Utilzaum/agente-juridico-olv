#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Repositório Central — Camada Única de Persistência (v2.1)
✅ Tudo que o telegram_bot.py usa  +  tudo que o script_djen.py precisa
✅ Deduplicação por hash (publicacoes_djen + eventos) → fim dos prazos ressuscitados
✅ Schema expandido de forma idempotente (não quebra banco existente)
✅ PATCH v2.1: autor preservado (não sobrescrito ao concluir/corrigir/reabrir)
"""
import json
import hashlib
import sqlite3
from pathlib import Path
from datetime import date, datetime
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple

# =========================================================
# 📍 CONFIG
# =========================================================
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "infra" / "controladoria.db"

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")  # concorre bem com o bot lendo
    return conn

# =========================================================
# 📋 MODELOS
# =========================================================
@dataclass
class Publicacao:
    hash_api: str
    numero_processo: str
    tribunal: str
    orgao_julgador: str
    tipo_ato: str
    data_disponibilizacao: str
    data_publicacao: str
    json_original: str
    id: Optional[int] = None
    processado: int = 0
    criado_em: Optional[str] = None

@dataclass
class Evento:
    numero_processo: str
    tipo_evento: str
    data_publicacao: str
    inicio_prazo: str
    prazo_final: str
    descricao: str
    id: Optional[int] = None
    status: str = "pendente"
    autor: str = ""
    hash_publicacao: Optional[str] = None

@dataclass
class PipelineExecucao:
    inicio: str
    fim: Optional[str] = None
    status: str = "em_execucao"
    publicacoes: int = 0
    duplicatas: int = 0
    eventos: int = 0
    falhas: int = 0
    cursor_final: Optional[str] = None
    tempo_ms: int = 0
    id: Optional[int] = None

# =========================================================
# 🔐 HASH (deduplicação)
# =========================================================
def calcular_hash_api(item: dict) -> str:
    """Hash SHA256 do item cru da API (ordem de chaves normalizada)."""
    conteudo = json.dumps(item, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(conteudo.encode("utf-8")).hexdigest()

# =========================================================
# 💾 ESCRITA — DJEN (camada única)
# =========================================================
def salvar_publicacao(item: dict) -> Tuple[str, Optional[int]]:
    """
    Salva a publicação CRUA antes da IA.
    Retorna (status, id) com status ∈ {'ok', 'duplicata', 'erro'}.
    """
    hash_api = calcular_hash_api(item)
    conn = get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO publicacoes_djen
               (hash_api, numero_processo, tribunal, orgao_julgador, tipo_ato,
                data_disponibilizacao, data_publicacao, json_original)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                hash_api,
                item.get("numeroprocessocommascara") or item.get("numeroProcesso") or "",
                item.get("siglaTribunal") or "",
                item.get("nomeOrgao") or "",
                item.get("tipoDocumento") or "",
                item.get("dataDisponibilizacao") or "",
                item.get("dataPublicacao") or "",
                json.dumps(item, ensure_ascii=False),
            ),
        )
        conn.commit()
        return "ok", cur.lastrowid
    except sqlite3.IntegrityError:
        return "duplicata", None
    except Exception as e:
        conn.rollback()
        return "erro", None
    finally:
        conn.close()

# Colunas ricas da tabela eventos (na ordem do INSERT)
_COLUNAS_EVENTO = [
    "numero_processo", "tipo_evento", "data_publicacao", "inicio_prazo",
    "prazo_final", "descricao", "status", "autor", "hash_publicacao",
    "reu", "tribunal", "orgao_julgador", "prazo_dias", "tipo_contagem",
    "ramo", "urgencia", "resumo", "audiencia",
]

def salvar_evento(registro: dict) -> Tuple[str, Optional[int]]:
    """
    Salva o evento processado. Dedup em 2ª camada por hash_publicacao.
    Retorna (status, id) com status ∈ {'criado', 'duplicata', 'erro'}.
    """
    hash_pub = registro.get("hash_publicacao")
    conn = get_connection()
    try:
        # 2ª camada de dedup: se o evento (mesmo hash) já existe, não recria
        if hash_pub:
            row = conn.execute(
                "SELECT id FROM eventos WHERE hash_publicacao = ?", (hash_pub,)
            ).fetchone()
            if row:
                return "duplicata", row["id"]

        valores = [registro.get(c, "") for c in _COLUNAS_EVENTO]
        # status padrão pendente se não informado
        idx_status = _COLUNAS_EVENTO.index("status")
        if not valores[idx_status]:
            valores[idx_status] = "pendente"

        placeholders = ", ".join(["?"] * len(_COLUNAS_EVENTO))
        cols = ", ".join(_COLUNAS_EVENTO)
        cur = conn.execute(
            f"INSERT INTO eventos ({cols}) VALUES ({placeholders})", valores
        )
        conn.commit()
        return "criado", cur.lastrowid
    except Exception as e:
        conn.rollback()
        return "erro", None
    finally:
        conn.close()

def registrar_execucao(dados: dict) -> None:
    """Registra uma execução do pipeline (auditoria do DJEN)."""
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO pipeline_execucao
               (inicio, fim, status, publicacoes, duplicatas, eventos, falhas, cursor_final, tempo_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                dados.get("inicio"), dados.get("fim"), dados.get("status", "concluido"),
                int(dados.get("publicacoes", 0)), int(dados.get("duplicatas", 0)),
                int(dados.get("eventos", 0)), int(dados.get("falhas", 0)),
                dados.get("cursor_final"), int(dados.get("tempo_ms", 0)),
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()

# =========================================================
# 🔎 CONSULTAS — EVENTOS (usadas pelo bot)
# =========================================================
def _evento_row_to_dict(r) -> Dict[str, Any]:
    return {
        "id": r["id"],
        "numero_processo": r["numero_processo"],
        "tipo_evento": r["tipo_evento"],
        "data_publicacao": r["data_publicacao"],
        "inicio_prazo": r["inicio_prazo"],
        "prazo_final": r["prazo_final"],
        "prazo": r["prazo_final"],
        "descricao": r["descricao"],
        "status": r["status"],
        "autor": r["autor"] or "N/D",
    }

def buscar_eventos_pendentes(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.execute(
            """SELECT id, numero_processo, tipo_evento, data_publicacao,
                      inicio_prazo, prazo_final, descricao, status, autor
               FROM eventos WHERE status = 'pendente'
               ORDER BY prazo_final ASC, id ASC LIMIT ? OFFSET ?""",
            (limit, offset),
        )
        return [_evento_row_to_dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

def buscar_evento_por_id(evento_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.execute(
            """SELECT id, numero_processo, tipo_evento, data_publicacao,
                      inicio_prazo, prazo_final, descricao, status, autor
               FROM eventos WHERE id = ?""",
            (evento_id,),
        )
        r = cur.fetchone()
        return _evento_row_to_dict(r) if r else None
    finally:
        conn.close()

# =========================================================
# ⚡ AÇÕES — EVENTOS (usadas pelo bot)
# =========================================================
def _auditar(conn, evento_id: int, acao: str, motivo: str, usuario: str) -> None:
    conn.execute(
        "INSERT INTO auditoria (evento_id, acao, motivo, usuario, data_hora) VALUES (?,?,?,?,?)",
        (evento_id, acao, motivo, usuario, datetime.now().isoformat()),
    )

def concluir_evento(evento_id: int, motivo: str, usuario: str) -> str:
    """Conclui evento preservando o autor (cliente). O operador vai pra auditoria."""
    conn = get_connection()
    try:
        ev = buscar_evento_por_id(evento_id)
        if not ev:
            return f"❌ Evento #{evento_id} não encontrado"
        # ✅ PATCH: não sobrescreve autor (nome do cliente)
        conn.execute("UPDATE eventos SET status='concluido' WHERE id=?", (evento_id,))
        _auditar(conn, evento_id, "CONCLUIDO", motivo, usuario)
        conn.commit()
        return f"✅ Evento #{evento_id} concluído com sucesso!"
    except Exception as e:
        conn.rollback()
        return f"❌ Erro ao concluir evento: {e}"
    finally:
        conn.close()

def corrigir_prazo(evento_id: int, nova_data: date, motivo: str, usuario: str) -> str:
    """Corrige prazo preservando o autor (cliente). O operador vai pra auditoria."""
    conn = get_connection()
    try:
        ev = buscar_evento_por_id(evento_id)
        if not ev:
            return f"❌ Evento #{evento_id} não encontrado"
        # ✅ PATCH: não sobrescreve autor (nome do cliente)
        conn.execute("UPDATE eventos SET prazo_final=? WHERE id=?",
                     (nova_data.isoformat(), evento_id))
        _auditar(conn, evento_id, "CORRIGIDO", motivo, usuario)
        conn.commit()
        return f"✅ Prazo do evento #{evento_id} corrigido para {nova_data.strftime('%d/%m/%Y')}"
    except Exception as e:
        conn.rollback()
        return f"❌ Erro ao corrigir prazo: {e}"
    finally:
        conn.close()

def reabrir_evento(evento_id: int, motivo: str, usuario: str) -> str:
    """Reabre evento preservando o autor (cliente). O operador vai pra auditoria."""
    conn = get_connection()
    try:
        ev = buscar_evento_por_id(evento_id)
        if not ev:
            return f"❌ Evento #{evento_id} não encontrado"
        if ev["status"] != "concluido":
            return f"⚠️ Evento #{evento_id} já está pendente"
        # ✅ PATCH: não sobrescreve autor (nome do cliente)
        conn.execute("UPDATE eventos SET status='pendente' WHERE id=?", (evento_id,))
        _auditar(conn, evento_id, "REABERTO", motivo, usuario)
        conn.commit()
        return f"✅ Evento #{evento_id} reaberto com sucesso!"
    except Exception as e:
        conn.rollback()
        return f"❌ Erro ao reabrir evento: {e}"
    finally:
        conn.close()

# =========================================================
# 📊 RELATÓRIOS
# =========================================================
def listar_concluidos(data_inicio: Optional[date] = None,
                      data_fim: Optional[date] = None) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        q = "SELECT id, numero_processo, tipo_evento, prazo_final, descricao, autor FROM eventos WHERE status='concluido'"
        p: List[Any] = []
        if data_inicio:
            q += " AND DATE(prazo_final) >= ?"; p.append(data_inicio.isoformat())
        if data_fim:
            q += " AND DATE(prazo_final) <= ?"; p.append(data_fim.isoformat())
        q += " ORDER BY prazo_final DESC"
        return [{
            "id": r["id"], "numero_processo": r["numero_processo"], "tipo_evento": r["tipo_evento"],
            "prazo_final": r["prazo_final"], "descricao": r["descricao"], "autor": r["autor"] or "N/D",
        } for r in conn.execute(q, p).fetchall()]
    finally:
        conn.close()

def listar_auditoria(evento_id: Optional[int] = None, limite: int = 50) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        q = """SELECT a.id, a.evento_id, a.acao, a.motivo, a.usuario, a.data_hora, e.numero_processo
               FROM auditoria a LEFT JOIN eventos e ON a.evento_id = e.id"""
        p: List[Any] = []
        if evento_id:
            q += " WHERE a.evento_id = ?"; p.append(evento_id)
        q += " ORDER BY a.data_hora DESC LIMIT ?"; p.append(limite)
        return [{
            "id": r["id"], "evento_id": r["evento_id"], "acao": r["acao"], "motivo": r["motivo"],
            "usuario": r["usuario"], "data_hora": r["data_hora"],
            "numero_processo": r["numero_processo"] or "N/D",
        } for r in conn.execute(q, p).fetchall()]
    finally:
        conn.close()

# =========================================================
# 📍 CURSORES
# =========================================================
def obter_cursor(nome_cursor: str) -> Optional[date]:
    conn = get_connection()
    try:
        r = conn.execute("SELECT valor FROM cursores WHERE nome=?", (nome_cursor,)).fetchone()
        if r and r["valor"]:
            return date.fromisoformat(str(r["valor"])[:10])
        return None
    finally:
        conn.close()

def atualizar_cursor(nome_cursor: str, valor: date) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO cursores (nome, valor, atualizado_em) VALUES (?, ?, ?)
               ON CONFLICT(nome) DO UPDATE SET valor=excluded.valor, atualizado_em=excluded.atualizado_em""",
            (nome_cursor, valor.isoformat(), datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()

# =========================================================
# 🧹 REINICIAR BASE (botão do menu Sistema)
# =========================================================
def resetar_base(avancar_cursor_para_hoje: bool = True) -> str:
    """Zera eventos + auditoria e (opcional) avança o cursor do DJEN para hoje."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM auditoria")
        conn.execute("DELETE FROM eventos")
        if avancar_cursor_para_hoje:
            hoje = date.today().isoformat()
            conn.execute(
                """INSERT INTO cursores (nome, valor, atualizado_em) VALUES (?, ?, ?)
                   ON CONFLICT(nome) DO UPDATE SET valor=excluded.valor, atualizado_em=excluded.atualizado_em""",
                ("ultima_djen", hoje, datetime.now().isoformat()),
            )
        conn.commit()
        return "✅ Prazos e histórico apagados. Cursor do DJEN → hoje."
    except Exception as e:
        conn.rollback()
        return f"❌ Erro ao reiniciar base: {e}"
    finally:
        conn.close()

# =========================================================
# 🏗️ SCHEMA (idempotente: cria tabelas + adiciona colunas novas)
# =========================================================
def _ensure_column(conn, table: str, column: str, typedef: str) -> None:
    """Adiciona coluna se não existir (SQLite não tem IF NOT EXISTS p/ coluna)."""
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {typedef}")
    except sqlite3.OperationalError:
        pass  # coluna já existe

def inicializar_schema() -> None:
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS eventos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero_processo TEXT NOT NULL,
                tipo_evento TEXT NOT NULL,
                data_publicacao TEXT NOT NULL,
                inicio_prazo TEXT NOT NULL,
                prazo_final TEXT NOT NULL,
                descricao TEXT,
                status TEXT DEFAULT 'pendente',
                autor TEXT,
                hash_publicacao TEXT,
                reu TEXT, tribunal TEXT, orgao_julgador TEXT,
                prazo_dias INTEGER, tipo_contagem TEXT, ramo TEXT,
                urgencia TEXT, resumo TEXT, audiencia TEXT,
                criado_em TEXT DEFAULT (datetime('now')),
                atualizado_em TEXT DEFAULT (datetime('now'))
            )""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS publicacoes_djen (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash_api TEXT UNIQUE NOT NULL,
                numero_processo TEXT, tribunal TEXT, orgao_julgador TEXT,
                tipo_ato TEXT, data_disponibilizacao TEXT, data_publicacao TEXT,
                json_original TEXT, processado INTEGER DEFAULT 0,
                criado_em TEXT DEFAULT (datetime('now'))
            )""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS auditoria (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evento_id INTEGER NOT NULL, acao TEXT NOT NULL, motivo TEXT,
                usuario TEXT, data_hora TEXT NOT NULL,
                FOREIGN KEY (evento_id) REFERENCES eventos(id)
            )""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cursores (
                nome TEXT PRIMARY KEY, valor TEXT,
                atualizado_em TEXT DEFAULT (datetime('now'))
            )""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_execucao (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inicio TEXT NOT NULL, fim TEXT, status TEXT DEFAULT 'em_execucao',
                publicacoes INTEGER DEFAULT 0, duplicatas INTEGER DEFAULT 0,
                eventos INTEGER DEFAULT 0, falhas INTEGER DEFAULT 0,
                cursor_final TEXT, tempo_ms INTEGER DEFAULT 0
            )""")
        # Índices p/ dedup e ordenação
        conn.execute("CREATE INDEX IF NOT EXISTS idx_eventos_hash ON eventos(hash_publicacao)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_eventos_status ON eventos(status, prazo_final)")
        # Migração segura: garante colunas ricas em bancos já existentes
        for col, td in [
            ("reu", "TEXT"), ("tribunal", "TEXT"), ("orgao_julgador", "TEXT"),
            ("prazo_dias", "INTEGER"), ("tipo_contagem", "TEXT"), ("ramo", "TEXT"),
            ("urgencia", "TEXT"), ("resumo", "TEXT"), ("audiencia", "TEXT"),
        ]:
            _ensure_column(conn, "eventos", col, td)
        conn.commit()
    finally:
        conn.close()

inicializar_schema()
