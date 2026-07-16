#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Formatter de Prazos - LAYOUT CLÁSSICO RESTAURADO
✅ Visual jurídico completo
✅ LGPD: spoiler em dados sensíveis
✅ Paginação suportada
"""
import html
from typing import Dict, List

def mascarar_spoiler(texto: str) -> str:
    if not texto or texto == "N/D":
        return "N/D"
    return f"<tg-spoiler>{html.escape(str(texto))}</tg-spoiler>"

def mascarar_processo(processo: str) -> str:
    if not processo or processo == "N/D":
        return "N/D"
    processo_limpo = "".join(filter(str.isdigit, str(processo)))
    return f"<tg-spoiler>{processo_limpo}</tg-spoiler>"

def formatar_prazo(evento: Dict) -> str:
    """Layout clássico completo"""
    autor = evento.get("autor") or ""
    tribunal = evento.get("tribunal") or "N/D"
    orgao = evento.get("orgao_julgador") or ""
    tipo = evento.get("tipo_evento") or evento.get("descricao") or "Sem descrição"
    processo = evento.get("numero_processo") or evento.get("processo") or "N/D"
    id_prazo = evento.get("id") or "?"
    
    pub = evento.get("data_publicacao") or "N/D"
    inicio = evento.get("inicio_prazo") or "N/D"
    final = evento.get("prazo_final") or "N/D"
    
    # LGPD
    autor_texto = mascarar_spoiler(autor) if autor else '<tg-spoiler>🔒 SEGREDO DE JUSTIÇA</tg-spoiler>'
    processo_mascarado = mascarar_processo(processo)
    
    # Blockquote para datas
    blockquote = (
        f"<blockquote>"
        f"📰 <b>Publicação:</b> {html.escape(pub)}\n"
        f"🚩 <b>Início:</b> {html.escape(inicio)}\n"
        f"⏰ <b>Final:</b> {html.escape(final)}"
        f"</blockquote>"
    )
    
    tribunal_texto = f"<u>{html.escape(tribunal)}</u>"
    if orgao:
        tribunal_texto += f" — {html.escape(orgao)}"
    
    return (
        f"⚖️ <b>PRAZO PROCESSUAL</b>\n"
        f"\n"
        f"👤 {autor_texto}\n"
        f"\n"
        f"📄 <i>{html.escape(tipo[:80])}</i>\n"
        f"🏛️ {tribunal_texto}\n"
        f"\n"
        f"{blockquote}\n"
        f"\n"
        f"🔎 Processo: {processo_mascarado}\n"
        f"<i>#{id_prazo}</i>"
    )

def formatar_lista_prazos(eventos: list) -> str:
    if not eventos:
        return "📭 <b>Nenhum prazo pendente</b>"
    
    cards = []
    for e in eventos:
        try:
            cards.append(formatar_prazo(e))
        except Exception as ex:
            cards.append(f"❌ Erro: {html.escape(str(ex))}")
    
    header = "<b>📋 PRAZOS PENDENTES</b>\n━━━━━━━━━━━━━━━━━━━━\n"
    return header + "\n━━━━━━━━━━━━━━━━━━━━\n".join(cards)
