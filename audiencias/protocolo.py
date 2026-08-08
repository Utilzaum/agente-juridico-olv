"""Protocolo de títulos do escritório (padrão dos agendamentos).
Formato: ACIJ - NOME DO CLIENTE - NÚMERO DO PROCESSO."""

PREFIXO_PADRAO = "ACIJ"


def nome_cliente(a):
    if a.partes:
        return a.partes[0]
    t = a.titulo or ""
    if a.processo and a.processo not in t:
        t = ""
    if a.processo and a.processo not in t:
        t = ""
    if " - " in t:
        pedacos = [p.strip() for p in t.split(" - ")]
        if len(pedacos) >= 2:
            return pedacos[1]
    return ""


def montar_titulo(a, prefixo=PREFIXO_PADRAO):
    cliente = nome_cliente(a)
    if prefixo and cliente and a.processo:
        return prefixo + " - " + cliente + " - " + a.processo
    if prefixo and a.processo:
        return prefixo + " - " + a.processo
    return a.titulo or "Audiência"


def montar_corpo(a):
    """Mensagem padrão ao cliente (corpo do evento/.ics)."""
    i = a.dt_inicio
    quando = i.strftime("%d/%m/%Y às %H:%M") if i else "____/____/______ às __:__"
    cliente = nome_cliente(a)
    saud = ("Prezado(a) " + cliente + ", bom dia.") if cliente else "Prezado(a), bom dia."
    return (
        saud + "\n\n"
        "Informo que a audiência foi designada para o dia " + quando + " horas.\n"
        "Solicito comparecimento com antecedência de 30 minutos, para organização "
        "da pauta, bem como leve RG original.\n"
        "Informo que o seu comparecimento é mandatório, pois em caso de ausência "
        "injustificada o Tribunal aplica multa.\n"
        "Recomendo considerar as regras de entrada no fórum, para evitar contratempos.\n\n"
        "Certo de vossa compreensão, informo que estou à disposição para prestar assistência."
    )
