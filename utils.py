# utils.py
"""
Utilitários gerais do DJEN v15.1
"""
from datetime import datetime
import hashlib
import logging

logger = logging.getLogger(__name__)

def normalizar_data_br(data_str: str) -> str:
    """
    Converte data no formato brasileiro DD/MM/YYYY para ISO YYYY-MM-DD.
    ✅ Correção crítica para compatibilidade com SQLite/Excel.
    
    Args:
        data_str: String no formato "DD/MM/YYYY" ou "YYYY-MM-DD"
    
    Returns:
        str: Data normalizada em "YYYY-MM-DD" ou string original se falhar
    """
    if not data_str or not isinstance(data_str, str):
        return data_str
    
    # Já está no formato ISO?
    if len(data_str) == 10 and data_str[4] == "-" and data_str[7] == "-":
        return data_str
    
    try:
        return datetime.strptime(data_str.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        logger.warning(f"⚠️ Falha ao normalizar data: '{data_str}'")
        return data_str

def gerar_hash(texto: str) -> str:
    """Gera hash MD5 para deduplicação."""
    return hashlib.md5(str(texto).encode("utf-8")).hexdigest()

def proximo_dia_util(data: datetime) -> datetime:
    """Calcula próximo dia útil (D+1) conforme CPC Art. 224."""
    data = data + timedelta(days=1)
    while data.weekday() >= 5:  # pula sábado (5) e domingo (6)
        data += timedelta(days=1)
    return data
