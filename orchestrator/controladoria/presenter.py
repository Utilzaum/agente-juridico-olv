#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Presenter para Controladoria Jurídica
Transforma DTOs em texto formatado para Telegram
"""
from datetime import date
from typing import List, Optional
from .dto import PrazoDTO, BotStatusDTO, UrgenciaEnum


class PrazoPresenter:
    """Apresenta prazos em formato Telegram Rich Text"""
    
    @staticmethod
    def render_card(prazo: PrazoDTO) -> str:
        """Renderiza um único prazo como card visual"""
        dias_texto = f"{prazo.dias_restantes} dias" if prazo.dias_restantes > 1 else f"{prazo.dias_restantes} dia"
        if prazo.dias_restantes == 0:
            dias_texto = "HOJE"
        elif prazo.dias_restantes < 0:
            dias_texto = f"{abs(prazo.dias_restantes)} dias ATRASADO"
        
        return (
            f"{prazo.cor_urgencia} <b>{prazo.label_urgencia}</b>\n\n"
            f"<b>📂 Processo:</b>\n"
            f"<code>{prazo.processo_formatado}</code>\n\n"
            f"<b>⚖️ Evento:</b>\n"
            f"{prazo.descricao}\n\n"
            f"<b>📅 Prazo Final:</b>\n"
            f"{prazo.prazo_final.strftime('%d/%m/%Y')}\n\n"
            f"<b>⏳ Restam:</b>\n"
            f"<b>{dias_texto}</b>\n\n"
            f"<i>ID: {prazo.id} | Tipo: {prazo.tipo_evento}</i>"
        )
    
    @staticmethod
    def render_lista(prazos: List[PrazoDTO]) -> str:
        """Renderiza lista de prazos"""
        if not prazos:
            return "📭 Nenhum prazo pendente."
        
        linhas = ["<h2>📋 Prazos Pendentes</h2>\n"]
        
        # Agrupa por urgência
        criticos = [p for p in prazos if p.urgencia == UrgenciaEnum.CRITICA]
        urgentes = [p for p in prazos if p.urgencia == UrgenciaEnum.URGENTE]
        outros = [p for p in prazos if p.urgencia not in (UrgenciaEnum.CRITICA, UrgenciaEnum.URGENTE)]
        
        if criticos:
            linhas.append("<b> CRÍTICOS</b>\n")
            for prazo in criticos:
                linhas.append(PrazoPresenter.render_card(prazo))
                linhas.append("\n━━━━━━━━━━━━━━━━━━━━\n")
        
        if urgentes:
            linhas.append("<b>🟠 URGENTES</b>\n")
            for prazo in urgentes:
                linhas.append(PrazoPresenter.render_card(prazo))
                linhas.append("\n━━━━━━━━━━━━━━━━━━━━\n")
        
        if outros:
            linhas.append("<b>🟡 OUTROS</b>\n")
            for prazo in outros:
                linhas.append(PrazoPresenter.render_card(prazo))
                linhas.append("\n━━━━━━━━━━━━━━━━━━━━\n")
        
        return "\n".join(linhas).strip()


class BotStatusPresenter:
    """Apresenta status de bots em formato tabela"""
    
    @staticmethod
    def render_tabela(bots: List[BotStatusDTO]) -> str:
        """Renderiza status dos bots como tabela visual"""
        if not bots:
            return "📭 Nenhum bot ativo."
        
        linhas = [
            "<h2> Status do Sistema</h2>\n",
            "<b>Serviço</b>          <b>Estado</b>     <b>PID</b>",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ]
        
        for bot in bots:
            pid_texto = str(bot.pid) if bot.pid else "—"
            linhas.append(f"{bot.icon_estado} {bot.nome:<15} {bot.estado:<10} {pid_texto}")
        
        return "\n".join(linhas)
    
    @staticmethod
    def render_card(bot: BotStatusDTO) -> str:
        """Renderiza status de um único bot"""
        return (
            f"<b>{bot.icon_estado} {bot.nome}</b>\n\n"
            f"<b>Estado:</b> {bot.estado}\n"
            f"<b>PID:</b> {bot.pid if bot.pid else '—'}\n"
            f"<b>Comando:</b> <code>{bot.comando}</code>" if bot.comando else ""
        )
