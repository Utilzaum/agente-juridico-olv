import re

def extrair_dados(texto: str) -> dict:
    texto = texto.upper()

    dados = {
        "numero_processo": "",
        "autor": "",
        "reu": "",
        "determinacao_judicial": ""
    }

    # =========================
    # PROCESSO (CNJ robusto)
    # =========================
    match = re.search(r'\d{7}-?\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}', texto)
    if match:
        dados["numero_processo"] = match.group(0)

    # =========================
    # AUTORES (várias variações)
    # =========================
    padroes_autor = [
        r'(AUTOR|REQUERENTE|EXEQUENTE|EMBARGANTE)[\s:\-]+([A-ZÀ-Ú\s]+)',
    ]

    for padrao in padroes_autor:
        match = re.search(padrao, texto)
        if match:
            dados["autor"] = match.group(2).strip()
            break

    # =========================
    # RÉUS (várias variações)
    # =========================
    padroes_reu = [
        r'(R[ÉE]U|REQUERIDO|EXECUTADO|EMBARGADO)[\s:\-]+([A-ZÀ-Ú\s]+)',
    ]

    for padrao in padroes_reu:
        match = re.search(padrao, texto)
        if match:
            dados["reu"] = match.group(2).strip()
            break

    # =========================
    # DETERMINAÇÃO (mais inteligente)
    # =========================
    match = re.search(
        r'(INTIME-SE.*|CITE-SE.*|JUNTE-SE.*|MANIFESTE-SE.*|DEFIRO.*)',
        texto
    )
    if match:
        dados["determinacao_judicial"] = match.group(1).strip()

    return dados
