def mensagem_boas_vindas_prev():
    return (
        "━━━━━━━━━━━━━━━━━━\n"
        "⚖️ <b>DOCUMENTARISTA PREVIDENCIÁRIO</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🤖 <b>100% Local com IA</b>\n"
        "📸 <b>Envie:</b>\n"
        "• RG/CNH ou documento pessoal\n"
        "• Comprovante de residência\n"
        "• CNIS / Carta de Concessão (opcional)\n"
        "✨ <b>Extração automática + correção fácil</b>\n"
        "📄 <b>Kit gerado:</b>\n"
        "1. Procuração Previdenciária\n"
        "2. Declaração de Hipossuficiência\n"
        "3. Renúncia ao Teto (Juizado)\n"
        "4. Contrato de Honorários\n"
        "━━━━━━━━━━━━━━━━━━")


from telegram import InlineKeyboardButton, InlineKeyboardMarkup
CAMPOS_CARD = [("nome", "👤 Nome"), ("cpf", "🆔 CPF"), ("data_nascimento", "🎂 Nascimento"),
               ("endereco", "📍 Endereço"), ("email", "📧 E-mail"), ("profissao", "💼 Profissão"),
               ("estado_civil", "💍 Estado Civil"), ("nacionalidade", "🌎 Nacionalidade")]

def _fmt(v): return v if v and str(v).strip() else "🔴 NÃO INFORMADO"

def card_cliente_prev(dados, confidence=None):
    txt = "⚖️ <b>CADASTRO DE CLIENTE — PREVIDENCIÁRIO</b>\n━━━━━━━━━━━━━━━━━━\n"
    txt += "\n".join(f"<b>{r}</b>: {_fmt(dados.get(c))}" for c, r in CAMPOS_CARD)
    if confidence is not None: txt += f"\n\n📊 <b>Confiabilidade:</b> 🟢 {int(confidence*100)}%"
    return txt + "\n\n💡 <i>Clique num botão para editar ou digite diretamente</i>"

def card_preview_prev(dados):
    return "📋 <b>PREVIEW — KIT PREVIDENCIÁRIO</b>\n" + "\n".join(
        f"{r}: <code>{dados.get(c, '')}</code>" for c, r in CAMPOS_CARD)

def get_correction_keyboard_prev():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Nome", callback_data="edit_nome"),
         InlineKeyboardButton("🆔 CPF", callback_data="edit_cpf")],
        [InlineKeyboardButton("🎂 Nascimento", callback_data="edit_data_nascimento"),
         InlineKeyboardButton("📍 Endereço", callback_data="edit_endereco")],
        [InlineKeyboardButton("📧 E-mail", callback_data="edit_email"),
         InlineKeyboardButton("💼 Profissão", callback_data="edit_profissao")],
        [InlineKeyboardButton("💍 Estado Civil", callback_data="edit_estado_civil"),
         InlineKeyboardButton("🌎 Nacionalidade", callback_data="edit_nacionalidade")],
        [InlineKeyboardButton("✅ Confirmar Dados", callback_data="confirm")],
        [InlineKeyboardButton("🔄 Reextrair", callback_data="reextract"),
         InlineKeyboardButton("❌ Cancelar", callback_data="cancel")]])
