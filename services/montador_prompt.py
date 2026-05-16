# services/montador_prompt.py

def montar_qualificacao(dados: dict) -> str:
    nome = dados.get("nome") or "NOME NÃO IDENTIFICADO"
    cpf = dados.get("cpf") or "CPF NÃO INFORMADO"
    rg = dados.get("rg") or "RG NÃO INFORMADO"
    endereco = dados.get("endereco") or "ENDEREÇO NÃO INFORMADO"
    email = dados.get("email") or "EMAIL NÃO INFORMADO"

    return (
        f"{nome}, brasileiro, estado civil não informado, profissão não informada, "
        f"portador do RG nº {rg}, inscrito no CPF sob o nº {cpf}, "
        f"residente e domiciliado em {endereco}, e-mail {email}"
    )


# ✅ ESSA FUNÇÃO ESTÁ FALTANDO NO SEU SISTEMA
def detectar_tipo_documento(texto_usuario: str) -> str:
    if not texto_usuario:
        return "procuracao"

    t = texto_usuario.lower()

    if "juntada" in t:
        return "juntada"
    if "contrato" in t:
        return "contrato"
    if "hipossuf" in t:
        return "hipossuficiencia"
    if "kit" in t or "inicial" in t:
        return "kit"

    return "procuracao"


def montar_prompt_juridico(dados: dict, tipo: str, contexto_extra: str = "") -> str:
    base = montar_qualificacao(dados)

    if tipo == "procuracao":
        return f"Gerar procuração de {base}"

    if tipo == "contrato":
        return f"Gerar contrato de honorários de {base}"

    if tipo == "hipossuficiencia":
        return f"Gerar declaração de hipossuficiência de {base}"

    if tipo == "kit":
        return f"Gerar documentos iniciais de {base}"

    if tipo == "juntada":
        return f"Gerar petição de juntada em favor de {base}. {contexto_extra}"

    return f"Gerar documento de {base}"
