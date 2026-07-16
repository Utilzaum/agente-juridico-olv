#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Formatter de Briefing Executivo com Rich Text
✅ Usa <blockquote> para estatísticas
✅ Usa <b> + <i> para hierarquia
✅ LGPD: <tg-spoiler> em nomes de autores
✅ CORREÇÃO: Bug lógico do elif dias == 0 (código morto)
✅ CORREÇÃO: Emoji 🔥 para prazos fatais (HOJE)
"""
import html
from datetime import date, datetime
from typing import Dict, List, Tuple


def formatar_briefing(
    admin_nome: str,
    saudacao: str,
    dia_semana: str,
    stats: Dict,
    urgentes: List[Tuple]
) -> str:
    """
    Formata briefing executivo com rich text.
    
    Args:
        admin_nome: Nome do administrador
        saudacao: Saudação baseada no horário
        dia_semana: Dia da semana por extenso
        stats: Dict com chaves {pendentes, vencidos, hoje, futuros}
        urgentes: Lista de tuplas (dias, autor, descricao, prazo)
    
    Returns:
        String formatada em HTML para Telegram
    """
    hoje = date.today().strftime('%d/%m')
    agora = datetime.now().strftime('%d/%m/%Y %H:%M')
    
    # Header com saudação
    linhas = [
        f"<b>{saudacao}, {html.escape(admin_nome)}</b>.",
        f"<i>Hoje é {html.escape(dia_semana)}, {hoje}</i>",
        "",
    ]
    
    # Se não há prazos
    if stats.get('pendentes', 0) == 0:
        linhas.extend([
            "📭 <b>Nenhum prazo pendente</b>",
            "",
            "<i>O escritório está em dia. Tenha um excelente trabalho!</i>",
        ])
        return "\n".join(linhas)
    
    # Blockquote com estatísticas
    stat_lines = []
    if stats.get('vencidos', 0) > 0:
        stat_lines.append(f"🔴 <b>{stats['vencidos']} prazos vencidos</b>")
    
    # ✅ CORREÇÃO: Emoji 🔥 para prazo fatal (HOJE)
    if stats.get('hoje', 0) > 0:
        stat_lines.append(f"🔥 <b>{stats['hoje']} vencem HOJE</b>")
    
    if stats.get('futuros', 0) > 0:
        stat_lines.append(f" <b>{stats['futuros']} prazos futuros</b>")
        
    linhas.append("<blockquote>")
    linhas.extend(stat_lines)
    linhas.append(f"<b>Total: {stats['pendentes']} prazos ativos</b>")
    linhas.append("</blockquote>")
    
    # Lista de urgentes
    if urgentes:
        linhas.extend([
            "",
            "<b>⚠️ MAIS URGENTES</b>",
        ])
        urgentes.sort(key=lambda x: x[0])
        
        for dias, autor, descricao, prazo in urgentes[:3]:
            # ✅ LGPD: Aplica spoiler no nome do autor
            if autor:
                autor_escaped = html.escape(autor[:40])
                linhas.append(f"👤 <b><tg-spoiler>{autor_escaped}</tg-spoiler></b>")
            
            linhas.append(f"<i>{html.escape(descricao[:50])}</i>")
            
            # ✅ CORREÇÃO: Lógica separada para < 0, == 0 e > 0
            if dias < 0:
                linhas.append(f"<s> Venceu há {abs(dias)} dia(s)</s>")
            elif dias == 0:
                linhas.append(f"🔥 <b>Vence HOJE</b>")
            else:
                linhas.append(f"🟠 Vence em <b>{dias}</b> dia(s)")
                
            linhas.append(f"<i>{prazo.strftime('%d/%m/%Y')}</i>")
            linhas.append("")
            
        if len(urgentes) > 3:
            linhas.append(f"<i>+ {len(urgentes) - 3} outros urgentes</i>")
            
    linhas.append(f"<i>Atualizado: {agora}</i>")
    return "\n".join(linhas)
