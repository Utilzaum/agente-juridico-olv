#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Exporta processos ativos (encerrado = 0) do SQLite para Excel.

Requisitos:
- pandas
- openpyxl (para .xlsx)

Uso:
    python exportar_ativos.py
"""

import sqlite3
import pandas as pd
from datetime import datetime
from pathlib import Path
import sys

DB_PATH = "publicacoes.db"
OUTPUT_DIR = Path("./exports")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def conectar_db():
    return sqlite3.connect(DB_PATH)


def validar_tabela(conn):
    """Verifica se a tabela 'processos' existe."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='processos';
    """)
    row = cursor.fetchone()
    if not row:
        print("❌ Tabela 'processos' não encontrada no banco.")
        print("👉 Execute primeiro o script que cria/popula a tabela de processos.")
        sys.exit(1)


def carregar_dados(conn):
    """Carrega processos ativos com ordenação útil."""
    query = """
    SELECT
        processo,
        tribunal,
        data_ultima_movimentacao,
        total_movimentacoes,
        status
    FROM processos
    WHERE encerrado = 0
    ORDER BY
        -- tenta ordenar corretamente mesmo sendo texto DD/MM/AAAA
        CASE
            WHEN length(data_ultima_movimentacao) = 10
            THEN substr(data_ultima_movimentacao, 7, 4) || '-' ||
                 substr(data_ultima_movimentacao, 4, 2) || '-' ||
                 substr(data_ultima_movimentacao, 1, 2)
            ELSE data_ultima_movimentacao
        END DESC;
    """
    return pd.read_sql_query(query, conn)


def salvar_excel(df):
    """Salva em Excel (.xlsx)."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"processos_ativos_{timestamp}.xlsx"

    try:
        df.to_excel(path, index=False, engine="openpyxl")
        print(f"✅ Excel gerado: {path}")
        return path
    except Exception as e:
        print(f"⚠️ Falha ao gerar .xlsx ({e}). Gerando CSV como fallback...")
        return salvar_csv(df)


def salvar_csv(df):
    """Fallback para CSV."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"processos_ativos_{timestamp}.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"✅ CSV gerado: {path}")
    return path


def main():
    print("📊 Exportando processos ativos...")

    conn = conectar_db()
    validar_tabela(conn)

    df = carregar_dados(conn)
    conn.close()

    if df.empty:
        print("⚠️ Nenhum processo ativo encontrado.")
        return

    print(f"📈 Total de processos ativos: {len(df)}")

    salvar_excel(df)


if __name__ == "__main__":
    main()
