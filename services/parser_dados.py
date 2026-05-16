import re

def extrair_dados(texto: str) -> dict:
    dados = {}

    texto = texto.upper()

    # =========================
    # NOME
    # =========================
    nome_match = re.search(r'\b([A-Z\s]{10,})\b', texto)
    if nome_match:
        dados["nome"] = nome_match.group(1).strip()

    # =========================
    # CPF
    # =========================
    cpf_match = re.search(r'\d{3}\.\d{3}\.\d{3}-\d{2}', texto)
    if cpf_match:
        dados["cpf"] = cpf_match.group()

    # =========================
    # DATA DE NASCIMENTO
    # =========================
    nasc_match = re.search(r'\d{2}/\d{2}/\d{4}', texto)
    if nasc_match:
        dados["data_nascimento"] = nasc_match.group()

    # =========================
    # NÚMERO DOCUMENTO (CNH)
    # =========================
    cnh_match = re.search(r'\b\d{11}\b', texto)
    if cnh_match:
        dados["numero_documento"] = cnh_match.group()

    # =========================
    # ENDEREÇO (heurística)
    # =========================
    endereco_match = re.search(r'(RUA|AV|EST|ALAMEDA)[A-Z\s\d,.-]+', texto)
    if endereco_match:
        dados["endereco"] = endereco_match.group()

    # =========================
    # CEP
    # =========================
    cep_match = re.search(r'\d{5}-\d{3}', texto)
    if cep_match:
        dados["cep"] = cep_match.group()

    # =========================
    # VALOR (conta)
    # =========================
    valor_match = re.search(r'\d{1,3},\d{2}', texto)
    if valor_match:
        dados["valor"] = valor_match.group()

    return dados
