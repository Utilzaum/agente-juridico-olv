#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Formatter de Dashboard com Rich Text
✅ Usa <u> para totais
✅ Usa <b> para categorias
✅ Layout compacto e visual
"""
from typing import Dict


def formatar_dashboard(stats: Dict) -> str:
    """
    Formata painel executivo com rich text.
    stats: {pendentes, vencidos, hoje, futuros}
    """
    pendentes = stats.get('pendentes', 0)
    vencidos = stats.get('vencidos', 0)
    hoje = stats.get('hoje', 0)
    futuros = stats.get('futuros', 0)
    
    # Formata cada linha com alinhamento
    linhas = [
        "<b>⚖️ PAINEL JURÍDICO</b>",
        "",
        f"📌 <u><b>Total Pendentes</b></u> ....... <b>{pendentes}</b>",
        "",
        f"🔴 <b>Vencidos</b> ............. <b>{vencidos}</b>",
        f" <b>Vence Hoje</b> ........... <b>{hoje}</b>",
        f"🟢 <b>Futuros</b> .............. <b>{futuros}</b>",
    ]
    
    return "\n".join(linhas)
