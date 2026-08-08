"""Normalização pós-OCR: tokens quebrados + datas/horas por extenso."""
import re

_MESES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4,
          "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
          "outubro": 10, "novembro": 11, "dezembro": 12}
_NUMS = {"um": 1, "dois": 2, "tres": 3, "três": 3, "quatro": 4, "cinco": 5,
         "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11,
         "doze": 12, "treze": 13, "quatorze": 14, "catorze": 14, "quinze": 15,
         "dezesseis": 16, "dezessete": 17, "dezoito": 18, "dezenove": 19,
         "vinte": 20, "trinta": 30}
for _i, _u in enumerate(["um", "dois", "tres", "três", "quatro",
                         "cinco", "seis", "sete", "oito", "nove"], 1):
    _NUMS["vinte e " + _u] = 20 + _i
    _NUMS["trinta e " + _u] = 30 + _i

_PAL_NUM = "|".join(sorted(_NUMS, key=len, reverse=True))
_PAL_MES = "|".join(sorted(_MESES, key=len, reverse=True))

RE_DATA_EXT = re.compile(
    r"\b(?:dia\s+)?(" + _PAL_NUM + r")\s+de\s+(" + _PAL_MES + r")\s+de\s+(20\d{2})\b",
    re.IGNORECASE)
RE_HORA_EXT = re.compile(r"\b(?:as|às)\s*(" + _PAL_NUM + r")\s+horas\b", re.IGNORECASE)
RE_HORA_DIG = re.compile(r"\b(?:as|às)\s*(\d{1,2})\s+horas\b", re.IGNORECASE)


def _data_ext(m):
    return "%02d/%02d/%s" % (_NUMS[m.group(1).lower()],
                             _MESES[m.group(2).lower()], m.group(3))


def _hora_ext(m):
    return "às %02d:00" % _NUMS[m.group(1).lower()]


def _hora_dig(m):
    return "às %02d:00" % int(m.group(1))


def normalizar(t: str) -> str:
    t = t.replace("\r", "")
    t = re.sub(r"(\d)\n\s*(\d)", r"\1\2", t)
    t = re.sub(r"(\d{1,2}:)\n\s*(\d{2})", r"\1\2", t)
    t = RE_DATA_EXT.sub(_data_ext, t)
    t = RE_HORA_EXT.sub(_hora_ext, t)
    t = RE_HORA_DIG.sub(_hora_dig, t)
    return t
