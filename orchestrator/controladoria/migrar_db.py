#!/usr/bin/env python3
"""Script para adicionar colunas de conclusão no banco de dados"""
import sqlite3
from pathlib import Path

DB_PATH = Path("/home/rapha/agente_juridico/infra/eventos.db")

if not DB_PATH.exists():
    print(f"❌ Banco não encontrado em: {DB_PATH}")
    exit(1)

print(f"📂 Banco: {DB_PATH}")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Verifica estrutura atual
print("\n📋 Estrutura ATUAL da tabela eventos:")
cursor.execute("PRAGMA table_info(eventos)")
for row in cursor.fetchall():
    print(f"  {row[1]:25s} {row[2]:10s}")

# Adiciona motivo_conclusao se não existir
try:
    cursor.execute("ALTER TABLE eventos ADD COLUMN motivo_conclusao TEXT")
    print("\n✅ Coluna 'motivo_conclusao' ADICIONADA")
except sqlite3.OperationalError:
    print("\n⚠️ Coluna 'motivo_conclusao' já existe")

# Adiciona data_conclusao se não existir
try:
    cursor.execute("ALTER TABLE eventos ADD COLUMN data_conclusao TEXT")
    print("✅ Coluna 'data_conclusao' ADICIONADA")
except sqlite3.OperationalError:
    print("⚠️ Coluna 'data_conclusao' já existe")

conn.commit()

# Verifica estrutura final
print("\n📋 Estrutura FINAL da tabela eventos:")
cursor.execute("PRAGMA table_info(eventos)")
for row in cursor.fetchall():
    print(f"  {row[1]:25s} {row[2]:10s}")

conn.close()
print("\n✅ Migração concluída! Reinicie o bot agora.")
