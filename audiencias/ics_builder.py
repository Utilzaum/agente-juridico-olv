"""Geração de .ics (RFC 5545) c/ lembretes embutidos (24h/1h/15min)."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List
from .models import Audiencia
from . import protocolo
try:
    from . import destinatarios
except Exception:
    destinatarios = None
from .store import DATA_DIR

def _esc(t: str) -> str:
    return (t or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

def _fold(linha: str) -> str:
    if len(linha) <= 74:
        return linha
    partes = []
    while len(linha) > 74:
        partes.append(linha[:74])
        linha = " " + linha[74:]
    partes.append(linha)
    return "\r\n".join(partes)

def gerar_ics(audiencias, nome: str = "Audiências - Agente Jurídico OLV", restrito: bool = True) -> str:
    L = ["BEGIN:VCALENDAR", "VERSION:2.0",
         "PRODID:-//Agente Juridico OLV//Audiencias//PT-BR",
         "CALSCALE:GREGORIAN", "METHOD:PUBLISH", f"X-WR-CALNAME:{_esc(nome)}"]
    agora = datetime.now()
    for a in audiencias:
        i = a.dt_inicio
        if not i:
            continue
        if restrito and (i < agora or "Horário não identificado" in (a.observacoes or "")
                         or a.situacao.lower().startswith(("cancel", "realiz", "n", "convertida"))
                         or a.status_revisao != "confirmada"):
            continue
        f = a.dt_fim or i + timedelta(minutes=30)
        status = "CANCELLED" if a.situacao.lower().startswith("cancel") else "CONFIRMED"
        desc = protocolo.montar_corpo(a) + "\n\n" + "\n".join(x for x in [
            f"Tipo: {a.tipo}" if a.tipo else "",
            f"Modalidade: {a.modalidade}" if a.modalidade else "",
            f"Partes: {' x '.join(a.partes)}" if a.partes else "",
            f"Link: {a.link}" if a.link else "",
            f"ID da reunião: {a.meeting_id}" if a.meeting_id else "",
            f"Senha de acesso: {a.senha}" if a.senha else "",
            f"Situação: {a.situacao}",
            a.observacoes,
        ] if x)
        L += ["BEGIN:VEVENT",
              f"UID:{a.uid}@agente-juridico-olv",
              f"DTSTAMP:{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}",
              f"DTSTART:{i:%Y%m%dT%H%M%S}", f"DTEND:{f:%Y%m%dT%H%M%S}",
              f"STATUS:{status}",
              f"SUMMARY:{_esc(protocolo.montar_titulo(a))}",
              f"DESCRIPTION:{_esc(desc)}",
              f"LOCATION:{_esc(' / '.join(x for x in [a.orgao, a.sala] if x))}",
              "BEGIN:VALARM", "ACTION:DISPLAY",
              "DESCRIPTION:Audiência amanhã", "TRIGGER:-P1D", "END:VALARM",
              "BEGIN:VALARM", "ACTION:DISPLAY",
              "DESCRIPTION:Audiência em 1h", "TRIGGER:-PT1H", "END:VALARM",
              "BEGIN:VALARM", "ACTION:DISPLAY",
              "DESCRIPTION:Audiência em 15min", "TRIGGER:-PT15M", "END:VALARM",
              ]
        if destinatarios:
            L.append("ORGANIZER;CN=Raphael Oliveira:mailto:rvao.adv@outlook.com")
            for _e in destinatarios.para_processo(a.processo):
                L.append("ATTENDEE;RSVP=TRUE:mailto:" + _e)
        L.append("END:VEVENT")
    L.append("END:VCALENDAR")
    return "\r\n".join(_fold(l) for l in L) + "\r\n"

def salvar_agenda(audiencias, caminho: str = "", restrito: bool = True) -> Path:
    out = Path(caminho) if caminho else DATA_DIR / "agenda.ics"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(gerar_ics(audiencias, restrito=restrito), encoding="utf-8-sig")
    return out
