def card_cliente(dados, confidence=None):
    conf_text = ""
    if confidence is not None:
        color = "🟢 " if confidence >= 0.8 else "🟠 " if confidence >= 0.5 else "🔴 "
        conf_text = f"\n📊 <b>Confiabilidade:</b> {color} {int(confidence*100)}%\n"
    
    # Campos obrigatórios para destacar visualmente
    obrigatorios = ["nome", "cpf", "endereco", "email"]
    
    def format_campo(icone, nome, valor, obrigatorio=False):
        if not valor or str(valor).strip() == "":
            if obrigatorio:
                return f"{icone} <b>{nome}:</b> 🔴 <i>NÃO INFORMADO</i>\n"
            return f"{icone} <b>{nome}:</b> <i>Não informado</i>\n"
        return f"{icone} <b>{nome}:</b> {valor}\n"

    return (
        "━━━━━━━━━━━━━━━━━━\n"
        "⚖️ <b>CADASTRO DE CLIENTE</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"{format_campo('👤', 'Nome', dados.get('nome'), True)}"
        f"{format_campo('🆔', 'CPF', dados.get('cpf'), True)}"
        f"{format_campo('🎂', 'Nascimento', dados.get('data_nascimento'))}"
        f"{format_campo('📍', 'Endereço', dados.get('endereco'), True)}"
        f"{format_campo('📧', 'E-mail', dados.get('email'), True)}"
        f"{format_campo('💼', 'Profissão', dados.get('profissao'))}"
        f"{format_campo('💍', 'Estado Civil', dados.get('estado_civil'))}"
        f"{format_campo('🌎', 'Nacionalidade', dados.get('nacionalidade'))}"
        f"{format_campo('⚖️', 'Área de Atuação', dados.get('area_juridica'))}"
        f"{conf_text}"
        "━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>Clique em um botão para editar ou digite dados diretamente</i>"
    )

def card_preview(dados):
    return (
        "━━━━━━━━━━━━━━━━━━\n"
        "📑 <b>KIT INICIAL</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Cliente:</b>\n{dados.get('nome', 'NÃO INFORMADO')}\n\n"
        "<b>Serão gerados:</b>\n"
        "✅ Procuração\n"
        "✅ Hipossuficiência\n"
        "✅ Honorários\n\n"
        "━━━━━━━━━━━━━━━━━━"
    )

def card_sucesso(msg: str) -> str:
    return (
        "━━━━━━━━━━━━━━━━━━\n"
        "✅ <b>SUCESSO</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"{msg}\n\n"
        "━━━━━━━━━━━━━━━━━━"
    )

def card_erro(msg: str) -> str:
    return (
        "━━━━━━━━━━━━━━━━━━\n"
        "❌ <b>ERRO</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"{msg}\n\n"
        "━━━━━━━━━━━━━━━━━━"
    )
