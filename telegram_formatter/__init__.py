#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Formatter - Camada de apresentação com Rich Text e LGPD
✅ Aplica recursos avançados da Telegram Bot API
✅ Proteção de dados sensíveis com <tg-spoiler>
✅ Separação clara entre lógica e apresentação
"""

from .prazo import formatar_prazo, formatar_lista_prazos
from .dashboard import formatar_dashboard
from .sistema import formatar_status
from .auditoria import formatar_auditoria
from .ajuda import formatar_ajuda
from .briefing import formatar_briefing

__all__ = [
    'formatar_prazo',
    'formatar_lista_prazos',
    'formatar_dashboard',
    'formatar_status',
    'formatar_auditoria',
    'formatar_ajuda',
    'formatar_briefing',
]
