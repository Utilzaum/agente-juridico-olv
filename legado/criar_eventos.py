import sqlite3

conn = sqlite3.connect("publicacoes.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS eventos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    processo TEXT,
    tipo_evento TEXT,
    data_evento TEXT,
    prazo_final TEXT,
    descricao TEXT,
    concluido INTEGER DEFAULT 0,
    criado_em TEXT
);
""")

conn.commit()
conn.close()

print("✅ Tabela eventos criada!")
