"""Extração heurística (local, sem nuvem) de dados de audiência.

Funciona com: print do Outlook/e-mail, pauta do PJe e texto de decisão judicial.
Estratégia: segmenta o texto a cada data+hora encontrada e extrai campos por segmento,
fundindo depois por uid (processo + início) — assim link/senha que aparecem longe
da data no print ainda são aproveitados.
"""
from __future__ import annotations
import re
from dataclasses import fields
from datetime import datetime
from typing import List, Optional
from .models import Audiencia
from .normaliza import normalizar

# ── padrões ────────────────────────────────────────────────
RE_PROCESSO = re.compile(r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b")
_HORA = r"\d{1,2}(?::|h)\d{2}"
RE_DATAHORA = re.compile(
    r"\b(\d{2}/\d{2}/\d{4})\s*(?:[^\d\n]{0,25}?)?(" + _HORA + r")"
    r"(?:\s*(?:[–—-]|até|às|as)\s*(" + _HORA + r"))?"
)
RE_DATA = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")
RE_URL = re.compile(r"https?://[^\s<>\"']+")
RE_MEET_ID = re.compile(r"ID da reuni[ãa]o:\s*([\d][\d\s-]{5,})", re.IGNORECASE)
RE_SENHA = re.compile(r"Senha(?: de acesso)?:\s*(\S+)", re.IGNORECASE)
RE_ORGAO = re.compile(r"\d+\s*[º°ª]?\s*(?:Vara|Juizado|Câmara|Turma)[^\n]{3,90}", re.IGNORECASE)
RE_SALA = re.compile(r"\b(?:SALA?|CEJUSC|VT[0-9])[^\n]{0,60}", re.IGNORECASE)
RE_PARTES = re.compile(
    r"([A-ZÀ-Ú][A-Za-zÀ-Úa-ú.\- ]{2,60}?)\s+X\s+([A-ZÀ-Ú][A-Za-zÀ-Úa-ú.\- ]{2,60}?)"
    r"(?=\s*(?:PROCEDIMENTO|AÇÃO|CONCILIA|INSTRU|UNA|SANEAM|JUSTIFICA|RECLAMA|EMBARGOS))"
)

SITUACOES = [  # ordem importa (mais específicas primeiro)
    ("não-realizada", "Não-Realizada"), ("não realizada", "Não-Realizada"),
    ("convertida em diligência", "Convertida em Diligência"),
    ("redesignada", "Redesignada"), ("cancelada", "Cancelada"),
    ("realizada", "Realizada"), ("designada", "Designada"),
]
TIPOS = [
    ("pauta de julgamento", "Sessão de Julgamento"),
    ("sessão de julgamento", "Sessão de Julgamento"), ("sustentação oral", "Sustentação Oral"),
    ("conciliação", "Conciliação"), ("instrução e julgamento", "Instrução e Julgamento"),
    ("instrução", "Instrução"), ("justificação", "Justificação"),
    ("saneamento", "Saneamento"), ("una", "Una"),
]

def _norm_hora(h: str):
    hh, mm = h.replace("h", ":").split(":")
    return int(hh), int(mm)

def _detect(pares, texto_lower: str) -> str:
    for chave, display in pares:
        if chave in texto_lower:
            return display
    return ""

def _modalidade(t: str) -> str:
    if any(k in t for k in ("telepresencial", "videoconfer", "zoom.us", "teams", "meet.google")):
        return "Telepresencial"
    if "presencial" in t:
        return "Presencial"
    return ""

def _limpa_url(m) -> str:
    return m.group(0).rstrip(".,;:)") if m else ""

def _titulo(regiao: str, partes: List[str]) -> str:
    if partes:
        return " x ".join(partes)
    for linha in regiao.splitlines():
        if RE_PROCESSO.search(linha):
            return linha.strip()[:120]
    linhas = [l.strip() for l in regiao.splitlines() if l.strip()]
    return linhas[0][:120] if linhas else ""

def _limpa_sala(s):
    s = s.strip()[:60]
    for k in ("designada", "cancelada", "realizada", "redesignada", "não-realizada"):
        if s.lower().endswith(k):
            s = s[: -len(k)].rstrip()
    return s

def _limpa_sala(s):
    s = s.strip()[:60]
    for k in ("designada", "cancelada", "realizada", "redesignada", "não-realizada"):
        if s.lower().endswith(k):
            s = s[: -len(k)].rstrip()
    return s

def _montar(texto: str, m, seg: str, prev: str, origem: str) -> Optional[Audiencia]:
    d, me, a = map(int, m.group(1).split("/"))
    hh, mm = _norm_hora(m.group(2))
    inicio = datetime(a, me, d, hh, mm)
    fim = None
    if m.group(3):
        fh, fm = _norm_hora(m.group(3))
        fim = datetime(a, me, d, fh, fm)

    mp = RE_PROCESSO.search(seg) or RE_PROCESSO.search(prev[-400:])
    processo = mp.group(0) if mp else ""
    low = (prev + seg).lower()
    low_seg = seg.lower()
    low_seg = seg.lower()

    # guarda: só cria evento se houver indício de audiência
    if not processo and not any(k in low for k in ("audiên", "pauta", "reunião", "sessão")):
        return None

    mpar = RE_PARTES.search(seg)
    partes = [mpar.group(1).strip(), mpar.group(2).strip()] if mpar else []
    morg = RE_ORGAO.search(seg)
    msal = RE_SALA.search(seg)
    mid = RE_MEET_ID.search(seg)

    return Audiencia(
        titulo=_titulo(seg, partes) or _titulo(prev + seg, partes),
        processo=processo,
        inicio=inicio.isoformat(timespec="minutes"),
        fim=fim.isoformat(timespec="minutes") if fim else "",
        modalidade=_modalidade(low_seg),
        link=_limpa_url(RE_URL.search(seg)),
        meeting_id=re.sub(r"\s+", "", mid.group(1)) if mid else "",
        senha=(RE_SENHA.search(seg) or RE_SENHA.search(prev) or (None, ""))[1] if False else
              (RE_SENHA.search(seg).group(1) if RE_SENHA.search(seg) else
               (RE_SENHA.search(prev).group(1) if RE_SENHA.search(prev) else "")),
        orgao=morg.group(0).strip() if morg else "",
        tipo=_detect(TIPOS, seg.lower()),
        sala=_limpa_sala(msal.group(0)) if msal else "",
        situacao=_detect(SITUACOES, seg.lower()) or "Designada",
        partes=partes,
        origem=origem,
    )

def _merge(a: Optional[Audiencia], b: Optional[Audiencia]) -> Optional[Audiencia]:
    if a is None: return b
    if b is None: return a
    for f in fields(a):
        va, vb = getattr(a, f.name), getattr(b, f.name)
        if not va and vb:
            setattr(a, f.name, vb)
    a.alertas_enviados = sorted(set(a.alertas_enviados) | set(b.alertas_enviados))
    return a

def extrair_audiencias(texto: str, origem: str = "") -> List[Audiencia]:
    texto = normalizar(texto)
    resultado: dict = {}
    matchs = list(RE_DATAHORA.finditer(texto))

    if matchs:
        for i, m in enumerate(matchs):
            _p = texto[max(0, m.start() - 20):m.start()].lower()
            if "até" in _p or "ate:" in _p or "de:" in _p or "distribu" in _p or "autuado" in _p or "disponibiliza" in _p or "publica" in _p or "término" in _p or "adiad" in _p:
                continue
            fim_seg = matchs[i + 1].start() if i + 1 < len(matchs) else len(texto)
            seg = texto[m.start():fim_seg]
            prev = texto[max(0, m.start() - 600):m.start()]
            aud = _montar(texto, m, seg, prev, origem)
            if aud:
                resultado[aud.uid] = _merge(resultado.get(aud.uid), aud)
    else:
        # fallback p/ decisão judicial: data sem horário → padrão 09:00 + aviso
        for m in RE_DATA.finditer(texto):
            _p = texto[max(0, m.start() - 20):m.start()].lower()
            if "até" in _p or "ate:" in _p or "de:" in _p or "distribu" in _p or "autuado" in _p or "disponibiliza" in _p or "publica" in _p or "término" in _p or "adiad" in _p:
                continue
            janela = texto[max(0, m.start() - 300):m.start() + 300].lower()
            if "audiên" not in janela and "pauta" not in janela:
                continue
            d, me, a = map(int, m.group(0).split("/"))
            mp = RE_PROCESSO.search(janela) or RE_PROCESSO.search(texto)
            aud = Audiencia(
                processo=mp.group(0) if mp else "",
                inicio=datetime(a, me, d, 9, 0).isoformat(timespec="minutes"),
                situacao="Designada",
                observacoes="⚠️ Horário não identificado — padrão 09:00 aplicado. Confirmar!",
                origem=origem,
            )
            resultado[aud.uid] = _merge(resultado.get(aud.uid), aud)

    return list(resultado.values())
