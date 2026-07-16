#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Formatter de Status do Sistema com Rich Text
✅ Usa <code> para PID
✅ Usa <s> para bots parados
✅ Usa <b> para nomes
"""
import html
from typing import Dict


def formatar_status(status: Dict) -> str:
    """
    Formata status dos bots com rich text.
    status: {nome_bot: "🟢 rodando (PID 1234)" ou "🔴 parado"}
    """
    linhas = ["<b>️ STATUS DOS BOTS</b>", ""]
    
    # Mapeamento de ícones e nomes amigáveis
    botoes_map = {
        'djen': ('🤖', 'DJEN'),
        'executor': ('⚙️', 'Executor'),
        'ia': ('', 'IA/OCR'),
    }
    
    for nome_bot, (icone, nome_amigavel) in botoes_map.items():
        status_texto = status.get(nome_bot)
        
        if status_texto:
            # Extrai informações do status
            if 'rodando' in status_texto:
                # Bot ativo - mostra PID em <code>
                if 'PID' in status_texto:
                    pid = status_texto.split('PID')[-1].strip().strip('()')
                    linhas.append(f"{icone} <b>{nome_amigavel}</b>")
                    linhas.append(f"    <b>rodando</b> • PID <code>{html.escape(pid)}</code>")
                else:
                    linhas.append(f"{icone} <b>{nome_amigavel}</b>: 🟢 <b>rodando</b>")
            else:
                # Bot parado - usa <s> para indicar "morto"
                linhas.append(f"{icone} <b>{nome_amigavel}</b>")
                linhas.append(f"   <s>🔴 parado</s>")
        else:
            # Bot não registrado
            linhas.append(f"{icone} <b>{nome_amigavel}</b>: <i>não registrado</i>")
        
        linhas.append("")
    
    if len(linhas) == 2:  # Só o header
        linhas.append("📭 <i>Nenhum bot ativo</i>")
    
    return "\n".join(linhas).strip()
