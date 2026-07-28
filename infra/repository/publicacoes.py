import json
import hashlib
import sqlite3
import logging
from typing import Tuple, Optional
from .models import Publicacao

logger = logging.getLogger(__name__)

class PublicacoesRepository:
    
    @staticmethod
    def calcular_hash(item_api: dict) -> str:
        conteudo = json.dumps(item_api, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(conteudo.encode()).hexdigest()

    @staticmethod
    def salvar(conn: sqlite3.Connection, item_api: dict) -> Tuple[bool, str, Optional[int]]:
        hash_api = PublicacoesRepository.calcular_hash(item_api)
        try:
            cursor = conn.execute(
                """INSERT INTO publicacoes_djen 
                   (hash_api, numero_processo, tribunal, orgao_julgador, tipo_ato, 
                    data_disponibilizacao, data_publicacao, json_original)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (hash_api, item_api.get("numeroprocessocommascara"), item_api.get("siglaTribunal"),
                 item_api.get("nomeOrgao"), item_api.get("tipoDocumento"),
                 item_api.get("dataDisponibilizacao"), item_api.get("dataPublicacao"),
                 json.dumps(item_api, ensure_ascii=False))
            )
            return True, "ok", cursor.lastrowid
        except sqlite3.IntegrityError:
            return False, "duplicata", None
        except Exception as e:
            logger.error(f"Erro ao salvar publicação: {e}")
            return False, str(e), None

    @staticmethod
    def marcar_processada(conn: sqlite3.Connection, publicacao_id: int):
        conn.execute("UPDATE publicacoes_djen SET processado = 1 WHERE id = ?", (publicacao_id,))

    @staticmethod
    def marcar_falha(conn: sqlite3.Connection, publicacao_id: int):
        # Poderíamos criar uma coluna 'tentativas' ou 'erro', mas mantivemos o schema atual
        conn.execute("UPDATE publicacoes_djen SET processado = -1 WHERE id = ?", (publicacao_id,))

    @staticmethod
    def obter_json_para_replay(conn: sqlite3.Connection, publicacao_id: int) -> Optional[dict]:
        """Tarefa 5: Permite reprocessar sem bater na API."""
        cursor = conn.execute("SELECT json_original FROM publicacoes_djen WHERE id = ?", (publicacao_id,))
        row = cursor.fetchone()
        if row:
            return json.loads(row['json_original'])
        return None
