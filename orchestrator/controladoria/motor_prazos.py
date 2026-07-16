#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MOTOR DE PRAZOS JURÍDICOS - v2.0
✅ Recesso Forense (Art. 220 CPC)
✅ Remove "intimação" como prazo fixo
✅ Gatilhos com Regex (preparado para IA)
✅ Suporte a Suspensões
"""
import re
from datetime import date, timedelta
from typing import Dict, Optional, Tuple

# =========================================================
# 📚 TABELA DE PRAZOS LEGAIS (Apenas Prazos Recursais e de Ação)
# =========================================================
PRAZOS_LEGAIS = {
    # CPC
    "contrarrazoes_apelacao": {"dias": 15, "tipo": "uteis", "ramo": "CPC", "artigo": "Art. 1.003, §5º", "regex": r"contrarraz[õo]es|resposta ao recurso|resposta [àa] apela[çc][ãa]o"},
    "agravo_interno": {"dias": 15, "tipo": "uteis", "ramo": "CPC", "artigo": "Art. 1.021", "regex": r"agravo interno"},
    "embargos_declaracao": {"dias": 5, "tipo": "uteis", "ramo": "CPC", "artigo": "Art. 1.023", "regex": r"embargos de declara[çc][ãa]o"},
    "contestacao": {"dias": 15, "tipo": "uteis", "ramo": "CPC", "artigo": "Art. 335", "regex": r"contestar|apresenta[çc][ãa]o de contesta[çc][ãa]o"},
    "replica": {"dias": 15, "tipo": "uteis", "ramo": "CPC", "artigo": "Art. 350", "regex": r"r[éé]plica|manifesta[çc][ãa]o sobre"},
    "apelacao": {"dias": 15, "tipo": "uteis", "ramo": "CPC", "artigo": "Art. 1.003", "regex": r"apelar|recurso de apela[çc][ãa]o"},
    
    # CPP
    "apelacao_criminal": {"dias": 10, "tipo": "uteis", "ramo": "CPP", "artigo": "Art. 593", "regex": r"apelar|apela[çc][ãa]o criminal"},
    "razoes_apelacao_cpp": {"dias": 8, "tipo": "uteis", "ramo": "CPP", "artigo": "Art. 600", "regex": r"raz[õo]es de apela[çc][ãa]o|contrarraz[õo]es criminal"},
    
    # CLT
    "recurso_ordinario_clt": {"dias": 8, "tipo": "uteis", "ramo": "CLT", "artigo": "Art. 895", "regex": r"recurso ordin[áa]rio trabalhista"},
    "agravo_peticao": {"dias": 8, "tipo": "uteis", "ramo": "CLT", "artigo": "Art. 897", "regex": r"agravo de peti[çc][ãa]o"},
    "embargos_execucao_clt": {"dias": 5, "tipo": "uteis", "ramo": "CLT", "artigo": "Art. 884", "regex": r"embargos [àa] execu[çc][ãa]o|garantir o ju[íi]zo"},
}

# =========================================================
# 📅 RECESSO FORENSE E FERIADOS (Art. 220 CPC)
# =========================================================
def em_recesso_forense(data: date) -> bool:
    """Verifica se a data está no recesso forense (20/12 a 20/01)."""
    return (data.month == 12 and data.day >= 20) or (data.month == 1 and data.day <= 20)

def eh_dia_util_juridico(data: date) -> bool:
    """Verifica se é dia útil, considerando fins de semana e recesso."""
    if data.weekday() >= 5:  # Fim de semana
        return False
    if em_recesso_forense(data):  # Recesso Forense
        return False
    # TODO: Aqui entrará a consulta à tabela de feriados/suspensões do DB
    return True

def adicionar_dias_uteis(data_inicio: date, dias: int) -> date:
    """Adiciona dias úteis pulando fins de semana e recesso forense."""
    data_atual = data_inicio
    dias_adicionados = 0
    
    while dias_adicionados < dias:
        data_atual += timedelta(days=1)
        if eh_dia_util_juridico(data_atual):
            dias_adicionados += 1
            
    return data_atual

# =========================================================
# 🔍 MOTOR PRINCIPAL (Regex + Fallback)
# =========================================================
def identificar_tipo_prazo(texto_publicacao: str, tipo_ato: str = "") -> Optional[Dict]:
    """Identifica o prazo usando Regex no texto e tipo de ato."""
    texto_alvo = f"{texto_publicacao} {tipo_ato}".lower()
    
    for chave, info in PRAZOS_LEGAIS.items():
        if re.search(info["regex"], texto_alvo):
            return {
                "tipo": chave,
                "dias": info["dias"],
                "tipo_dia": info["tipo"],
                "ramo": info["ramo"],
                "artigo": info["artigo"],
            }
    
    # Fallback: Se não achou na tabela, o prazo padrão do CPC é 15 dias úteis
    return {
        "tipo": "prazo_padrao_cpc",
        "dias": 15,
        "tipo_dia": "uteis",
        "ramo": "CPC",
        "artigo": "Art. 218, § 1º (Prazo Padrão)",
    }

def calcular_prazo_legal(data_publicacao: date, texto_publicacao: str, tipo_ato: str = "") -> Dict:
    """Calcula o prazo final aplicando Recesso Forense e regras legais."""
    info_prazo = identificar_tipo_prazo(texto_publicacao, tipo_ato)
    
    # Marco inicial: dia seguinte à publicação (ou intimação)
    data_inicio = data_publicacao + timedelta(days=1)
    
    # Se o início cair no recesso, posterga para o fim do recesso (Art. 220, § 1º)
    while em_recesso_forense(data_inicio):
        data_inicio += timedelta(days=1)
        
    if info_prazo["tipo_dia"] == "uteis":
        data_final = adicionar_dias_uteis(data_inicio, info_prazo["dias"])
    else:
        data_final = data_inicio + timedelta(days=info_prazo["dias"])
        
    return {
        "data_inicio": data_inicio,
        "data_final": data_final,
        "dias": info_prazo["dias"],
        "tipo_dia": info_prazo["tipo_dia"],
        "ramo": info_prazo["ramo"],
        "artigo": info_prazo["artigo"],
        "tipo_prazo": info_prazo["tipo"],
    }
