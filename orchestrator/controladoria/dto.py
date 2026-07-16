#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DTOs para a Controladoria Jurídica
Separa dados brutos da apresentação
"""
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Optional


class UrgenciaEnum(str, Enum):
    CRITICA = "critica"
    URGENTE = "urgente"
    MEDIA = "media"
    NORMAL = "normal"
    FUTURO = "futuro"


class StatusEnum(str, Enum):
    PENDENTE = "pendente"
    CONCLUIDO = "concluido"
    ADIADO = "adiado"


@dataclass
class PrazoDTO:
    """Data Transfer Object para prazos jurídicos"""
    id: int
    processo: str
    descricao: str
    prazo_final: date
    dias_restantes: int
    tipo_evento: str  # CPC, CPP, CLT
    urgencia: UrgenciaEnum
    status: StatusEnum = StatusEnum.PENDENTE
    
    @property
    def processo_formatado(self) -> str:
        """Formata número de processo no padrão judicial"""
        if len(self.processo) >= 20:
            return f"{self.processo[:7]}-{self.processo[7:9]}.{self.processo[9:13]}.{self.processo[13:15]}.{self.processo[15:17]}.{self.processo[17:20]}"
        return self.processo
    
    @property
    def cor_urgencia(self) -> str:
        cores = {
            UrgenciaEnum.CRITICA: "🔴",
            UrgenciaEnum.URGENTE: "🟠",
            UrgenciaEnum.MEDIA: "🟡",
            UrgenciaEnum.NORMAL: "🟢",
            UrgenciaEnum.FUTURO: "🔵"
        }
        return cores.get(self.urgencia, "⚪")
    
    @property
    def label_urgencia(self) -> str:
        labels = {
            UrgenciaEnum.CRITICA: "Crítico",
            UrgenciaEnum.URGENTE: "Urgente",
            UrgenciaEnum.MEDIA: "Prioridade Média",
            UrgenciaEnum.NORMAL: "Normal",
            UrgenciaEnum.FUTURO: "Futuro"
        }
        return labels.get(self.urgencia, "Desconhecido")


@dataclass
class BotStatusDTO:
    """DTO para status de bots"""
    nome: str
    pid: Optional[int]
    estado: str
    comando: Optional[str] = None
    
    @property
    def icon_estado(self) -> str:
        icons = {
            "rodando": "🟢",
            "parado": "",
            "erro": "️"
        }
        return icons.get(self.estado, "⚪")


@dataclass
class PublicacaoDTO:
    """DTO para publicações do DJEN"""
    id: int
    processo: str
    data_publicacao: date
    texto_completo: str
    resumo_ia: Optional[str] = None
    tipo: Optional[str] = None
    
    @property
    def processo_formatado(self) -> str:
        if len(self.processo) >= 20:
            return f"{self.processo[:7]}-{self.processo[7:9]}.{self.processo[9:13]}.{self.processo[13:15]}.{self.processo[15:17]}.{self.processo[17:20]}"
        return self.processo
