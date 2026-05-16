# prazo_engine.py
"""
Motor jurídico para cálculo de prazos processuais.
Implementa regras do CPC/2015, CPP e CLT com fallback seguro.
"""
from datetime import datetime, timedelta
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)

def calcular_prazo(data_inicio: datetime, dias: int, unidade: str) -> datetime:
    """
    Calcula prazo processual conforme unidade.
    
    Args:
        data_inicio: Data base para contagem
        dias: Quantidade de dias do prazo
        unidade: "UTEIS" ou "CORRIDOS"
    
    Returns:
        datetime: Data final do prazo
    """
    if not isinstance(dias, int) or dias <= 0:
        return data_inicio
        
    if unidade == "CORRIDOS":
        return data_inicio + timedelta(days=dias)
    
    # UTEIS (CPC padrão - Art. 219)
    data = data_inicio
    cont = 0
    while cont < dias:
        data += timedelta(days=1)
        if data.weekday() < 5:  # seg-sex = dia útil
            cont += 1
    return data

def aplicar_regra_fallback(info_llm: dict) -> Tuple[int, str]:
    """
    Regra de fallback CRÍTICA com validação de entrada.
    
    Prioridade:
    1. Valor explícito do LLM (validado: 1-100 dias)
    2. CPP → 5 dias corridos (Art. 798 CPP)
    3. Default CPC → 5 dias úteis (Art. 231 CPC)
    """
    prazo = info_llm.get("prazo_dias")
    unidade = info_llm.get("unidade")
    ramo = info_llm.get("ramo") or "CPC"  # ✅ Fallback explícito para ramo

    # 1️⃣ LLM extraiu valor válido e dentro da faixa segura?
    if isinstance(prazo, int) and 1 <= prazo <= 100:
        unidade_final = unidade if unidade in ("UTEIS", "CORRIDOS") else "UTEIS"
        logger.debug(f"✅ Prazo do LLM: {prazo} dias {unidade_final} ({ramo})")
        return prazo, unidade_final
    
    # 2️⃣ Ramo penal identificado?
    if ramo == "CPP":
        logger.debug("🔒 Fallback CPP: 5 dias corridos (Art. 798)")
        return 5, "CORRIDOS"
    
    # 3️⃣ Default civil seguro
    logger.debug("🔒 Fallback CPC: 5 dias úteis (Art. 231)")
    return 5, "UTEIS"

def calcular_inicio_prazo(data_pub: datetime, ramo: Optional[str] = None) -> datetime:
    """
    Calcula marco inicial do prazo conforme CPC Art. 224.
    
    Regra: prazo começa do PRÓXIMO dia útil à publicação.
    Exceção: CPP pode ter contagem imediata em casos específicos.
    """
    # ✅ Validação de ramo com fallback
    if ramo not in ("CPC", "CPP", "CLT"):
        ramo = "CPC"
    
    if ramo == "CPP":
        return data_pub  # Penal: contagem pode ser imediata
    
    # Civil/Trabalhista: próximo dia útil
    return proximo_dia_util(data_pub)

def proximo_dia_util(data: datetime) -> datetime:
    """Calcula próximo dia útil (D+1)."""
    data = data + timedelta(days=1)
    while data.weekday() >= 5:
        data += timedelta(days=1)
    return data
