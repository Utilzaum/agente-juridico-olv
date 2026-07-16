#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Formatter de Auditoria com Rich Text e LGPD
✅ Números de processo e nomes com spoiler
"""
import html
from typing import List, Dict


def mascarar_spoiler(texto: str) -> str:
    """Aplica efeito spoiler do Telegram"""
    if not texto or texto == "N/D":
        return "N/D"
    return f"<tg-spoiler>{html.escape(str(texto))}</tg-spoiler>"


def mascarar_processo(processo: str) -> str:
    """Formata e mascara número de processo"""
    if not processo or processo == "N/D":
        return "N/D"
    processo_limpo = "".join(filter(str.isdigit, str(processo)))
    return f"<tg-spoiler>{processo_limpo}</tg-spoiler>"


def formatar_auditoria(concluidos: List[Dict]) -> str:
    """
    Formata lista de prazos concluídos com proteção LGPD.
    """
    if not concluidos:
        return "📭 <b>Nenhum prazo concluído registrado</b>"
    
    linhas = [
        "<b>✅ AUDITORIA DE PRAZOS CONCLUÍDOS</b>",
        "",
    ]
    
    for e in concluidos[:20]:
        try:
            id_prazo = e.get("id") or "N/D"
            processo = e.get("processo") or e.get("numero_processo") or "N/D"
            descricao = e.get("descricao") or e.get("tipo_evento") or "Sem descrição"
            motivo = e.get("motivo_conclusao") or "Não informado"
            data_conclusao = e.get("data_conclusao") or "N/D"
            autor = e.get("autor") or ""
            
            # ✅ LGPD: Aplica máscara
            processo_mascarado = mascarar_processo(processo)
            autor_texto = mascarar_spoiler(autor) if autor else "N/D"
            
            linhas.extend([
                f"✅ <b>ID <code>{html.escape(str(id_prazo))}</code></b>",
                f"👤 {autor_texto}",
                f"🔎 {processo_mascarado}",
                "",
                f"<blockquote>",
                f"📝 {html.escape(descricao[:100])}",
                f"✔️ <b>Motivo:</b> {html.escape(motivo)}",
                f"📅 <b>Concluído:</b> {html.escape(str(data_conclusao))}",
                f"</blockquote>",
                "",
            ])
        except Exception as ex:
            linhas.append(f"❌ Erro: {html.escape(str(ex))}")
    
    return "\n".join(linhas)
