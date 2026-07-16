from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_correction_keyboard():
    """Teclado unificado para edição de dados do cliente"""
    keyboard = [
        [
            InlineKeyboardButton("👤 Nome", callback_data="edit_nome"),
            InlineKeyboardButton("🆔 CPF", callback_data="edit_cpf")
        ],
        [
            InlineKeyboardButton("🎂 Nascimento", callback_data="edit_data_nascimento"),
            InlineKeyboardButton("📍 Endereço", callback_data="edit_endereco")
        ],
        [
            InlineKeyboardButton("📧 E-mail", callback_data="edit_email"),
            InlineKeyboardButton("💼 Profissão", callback_data="edit_profissao")
        ],
        [
            InlineKeyboardButton("💍 Estado Civil", callback_data="edit_estado_civil"),
            InlineKeyboardButton("🌎 Nacionalidade", callback_data="edit_nacionalidade")
        ],
        [
            InlineKeyboardButton("⚖️ Área de Atuação", callback_data="edit_area_juridica")
        ],
        [
            InlineKeyboardButton("✅ Confirmar Dados", callback_data="confirm")
        ],
        [
            InlineKeyboardButton("🔄 Reextrair", callback_data="reextract"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancel")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_preview_keyboard() -> InlineKeyboardMarkup:
    """Retorna o teclado de pré-visualização antes de gerar o kit."""
    keyboard = [
        [InlineKeyboardButton("🚀 Gerar Kit", callback_data="generate_kit")],
        [InlineKeyboardButton("✏️ Editar Dados", callback_data="edit_data")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)
