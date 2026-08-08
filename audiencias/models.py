"""Modelo de dados da audiência."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional
import hashlib

DURACAO_PADRAO_MIN = 30

@dataclass
class Audiencia:
    titulo: str = ""
    processo: str = ""
    inicio: str = ""                      # ISO "2026-08-04T09:10"
    fim: str = ""
    modalidade: str = ""                  # Telepresencial | Presencial
    link: str = ""
    meeting_id: str = ""
    senha: str = ""
    orgao: str = ""
    tipo: str = ""                        # Conciliação, Instrução...
    sala: str = ""
    situacao: str = "Designada"
    status_revisao: str = "pendente"
    partes: List[str] = field(default_factory=list)
    observacoes: str = ""
    origem: str = ""                      # arquivo/texto de origem
    criado_em: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    alertas_enviados: List[str] = field(default_factory=list)

    @property
    def uid(self) -> str:
        base = f"{self.processo}|{self.inicio}"
        return hashlib.md5(base.encode("utf-8")).hexdigest()[:12]

    @property
    def dt_inicio(self) -> Optional[datetime]:
        return datetime.fromisoformat(self.inicio) if self.inicio else None

    @property
    def dt_fim(self) -> Optional[datetime]:
        if self.fim:
            return datetime.fromisoformat(self.fim)
        i = self.dt_inicio
        return i + timedelta(minutes=DURACAO_PADRAO_MIN) if i else None

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Audiencia":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
