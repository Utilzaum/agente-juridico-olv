# orchestrator/controladoria/service.py

from pathlib import Path
import sys

# =========================================================
# 📁 GARANTE IMPORT DA RAIZ
# =========================================================
BASE_DIR = Path(__file__).resolve().parents[2]

if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

# =========================================================
# 🏛️ BANCO CENTRALIZADO
# =========================================================
try:
    from infra.db import (
        listar_eventos_pendentes,
        concluir_evento as concluir_evento_db
    )

    CONTROLADORIA_OK = True

except Exception as e:
    print(f"❌ Erro ao importar infra.db: {e}")

    listar_eventos_pendentes = None
    concluir_evento_db = None
    CONTROLADORIA_OK = False


# =========================================================
# 📊 LISTAGEM DE PRAZOS
# =========================================================
def listar_eventos():
    """
    Retorna eventos pendentes do banco centralizado.
    Compatível com telegram_bot.py
    """

    if not CONTROLADORIA_OK:
        return []

    try:
        eventos = listar_eventos_pendentes()

        lista = []

        for e in eventos:

            prazo = e["prazo_final"] if "prazo_final" in e.keys() else "N/D"

            lista.append(
                (
                    e["id"],
                    e["numero_processo"],
                    e["tipo_evento"],
                    prazo,
                    e["urgencia"],
                    e["status"],
                    prazo
                )
            )

        return lista

    except Exception as e:
        print(f"❌ Erro ao listar eventos: {e}")
        return []


# =========================================================
# ✅ CONCLUIR EVENTO
# =========================================================
def concluir_evento(evento_id: int) -> str:
    """
    Marca evento como concluído.
    """

    if not CONTROLADORIA_OK:
        return "❌ Banco indisponível."

    try:

        ok = concluir_evento_db(evento_id)

        if ok:
            return f"✅ Evento {evento_id} concluído."

        return f"⚠️ Evento {evento_id} não encontrado."

    except Exception as e:
        return f"❌ Erro ao concluir evento: {e}"
