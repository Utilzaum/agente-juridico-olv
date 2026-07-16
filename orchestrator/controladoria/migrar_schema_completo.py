#!/usr/bin/env python3
"""Migração completa do schema - adiciona TODAS as colunas faltantes"""
import sqlite3
from pathlib import Path

DB_PATH = Path("/home/rapha/agente_juridico/orchestrator/controladoria/eventos.db")

if not DB_PATH.exists():
    print(f"❌ Banco não encontrado em: {DB_PATH}")
    exit(1)

print(f"📂 Banco: {DB_PATH}\n")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Lista de TODAS as colunas que devem existir
colunas_necessarias = [
    ("numero_processo", "TEXT"),
    ("prazo_final", "TEXT"),
    ("tipo_evento", "TEXT"),
    ("data_publicacao", "TEXT"),
    ("inicio_prazo", "TEXT"),
    ("autor", "TEXT"),
    ("reu", "TEXT"),
    ("tribunal", "TEXT"),
    ("orgao_julgador", "TEXT"),
    ("urgencia", "TEXT"),
    ("resumo", "TEXT"),
    ("concluido", "INTEGER DEFAULT 0"),
    ("motivo_conclusao", "TEXT"),
    ("data_conclusao", "TEXT"),
]

# Verifica estrutura atual
print("📋 Estrutura ATUAL:")
cursor.execute("PRAGMA table_info(eventos)")
colunas_existentes = {row[1] for row in cursor.fetchall()}
for col in colunas_existentes:
    print(f"  ✅ {col}")

print("\n Adicionando colunas faltantes:\n")

# Adiciona colunas que faltam
for nome_coluna, tipo in colunas_necessarias:
    if nome_coluna not in colunas_existentes:
        try:
            cursor.execute(f"ALTER TABLE eventos ADD COLUMN {nome_coluna} {tipo}")
            print(f"  ✅ Coluna '{nome_coluna}' ADICIONADA")
        except sqlite3.OperationalError as e:
            print(f"  ️ Erro ao adicionar '{nome_coluna}': {e}")
    else:
        print(f"  ⏭️ Coluna '{nome_coluna}' já existe")

conn.commit()

# Verifica estrutura final
print("\n📋 Estrutura FINAL:")
cursor.execute("PRAGMA table_info(eventos)")
for row in cursor.fetchall():
    print(f"  {row[1]:25s} {row[2]:10s}")

conn.close()
print("\n✅ Migração completa concluída! Reinicie o bot agora.")
