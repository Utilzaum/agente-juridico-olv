import sqlite3

conn = sqlite3.connect("publicacoes.db")
cursor = conn.cursor()

# Criar tabela processos (se não existir)
cursor.execute("""
CREATE TABLE IF NOT EXISTS processos (
    processo TEXT PRIMARY KEY,
    tribunal TEXT,
    data_ultima_movimentacao TEXT,
    total_movimentacoes INTEGER,
    status TEXT,
    encerrado INTEGER DEFAULT 0
);
""")

# Popular tabela processos
cursor.execute("""
INSERT OR REPLACE INTO processos (processo, tribunal, data_ultima_movimentacao, total_movimentacoes)
SELECT 
    processo,
    MAX(tribunal),
    MAX(data_publicacao),
    COUNT(*)
FROM publicacoes
WHERE processo != 'N/D'
GROUP BY processo;
""")

# Marcar processos encerrados
cursor.execute("""
UPDATE processos
SET encerrado = 1
WHERE processo IN (
    SELECT DISTINCT processo
    FROM publicacoes
    WHERE LOWER(conteudo) LIKE '%arquive-se%'
       OR LOWER(conteudo) LIKE '%dê-se baixa%'
);
""")

conn.commit()
conn.close()

print("✅ Processos organizados com sucesso!")
