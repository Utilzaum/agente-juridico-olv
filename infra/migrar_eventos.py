import sqlite3
import hashlib
from datetime import datetime

origem = sqlite3.connect("eventos.db")
destino = sqlite3.connect("controladoria.db")

origem.row_factory = sqlite3.Row
cur_origem = origem.cursor()
cur_destino = destino.cursor()

registros = cur_origem.execute("""
SELECT *
FROM eventos
""").fetchall()

print(f"Encontrados {len(registros)} eventos")

for r in registros:

    hash_evento = hashlib.sha256(
        (
            str(r["numero_processo"]) +
            str(r["tipo_evento"]) +
            str(r["prazo_final"])
        ).encode()
    ).hexdigest()

    cur_destino.execute("""
        INSERT OR IGNORE INTO eventos(
            hash_evento,
            numero_processo,
            tipo_evento,
            descricao,
            tribunal,
            orgao_julgador,
            autor,
            reu,
            data_publicacao,
            inicio_prazo,
            prazo_final,
            prazo_dias,
            urgencia,
            status,
            criado_em
        )
        VALUES(
            ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
        )
    """, (

        hash_evento,

        r["numero_processo"],
        r["tipo_evento"],
        r["descricao"],

        r["tribunal"],
        r["orgao_julgador"],

        r["autor"],
        r["reu"],

        r["data_publicacao"],
        r["inicio_prazo"],
        r["prazo_final"],

        r["prazo_dias"],

        r["urgencia"],

        r["status"],

        datetime.now()
    ))

destino.commit()

print("Migração concluída")

origem.close()
destino.close()
