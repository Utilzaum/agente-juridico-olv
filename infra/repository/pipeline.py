import sqlite3
from typing import Optional
from .models import PipelineExecucao

class PipelineRepository:
    
    @staticmethod
    def inicializar_schema(conn: sqlite3.Connection):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_execucao (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inicio TEXT NOT NULL,
                fim TEXT,
                status TEXT DEFAULT 'em_execucao',
                publicacoes INTEGER DEFAULT 0,
                duplicatas INTEGER DEFAULT 0,
                eventos INTEGER DEFAULT 0,
                falhas INTEGER DEFAULT 0,
                cursor_final TEXT,
                tempo_ms INTEGER DEFAULT 0
            )
        """)

    @staticmethod
    def iniciar_registro(conn: sqlite3.Connection, data_inicio: str) -> int:
        cursor = conn.execute("INSERT INTO pipeline_execucao (inicio) VALUES (?)", (data_inicio,))
        return cursor.lastrowid

    @staticmethod
    def finalizar_registro(conn: sqlite3.Connection, pipeline_id: int, dados: PipelineExecucao):
        conn.execute("""
            UPDATE pipeline_execucao 
            SET fim = ?, status = ?, publicacoes = ?, duplicatas = ?, 
                eventos = ?, falhas = ?, cursor_final = ?, tempo_ms = ?
            WHERE id = ?
        """, (dados.fim, dados.status, dados.publicacoes, dados.duplicatas, 
              dados.eventos, dados.falhas, dados.cursor_final, dados.tempo_ms, pipeline_id))
