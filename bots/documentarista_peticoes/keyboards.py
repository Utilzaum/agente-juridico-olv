"""Teclados inline do bot."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


class Keyboards:
    @staticmethod
    def menu_principal():
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📂 Biblioteca de Petições", callback_data="menu_biblioteca")],
            [InlineKeyboardButton("🔎 Buscar peça", callback_data="menu_buscar")],
            [InlineKeyboardButton("ℹ️ Sobre", callback_data="menu_sobre")],
        ])

    @staticmethod
    def listar_areas(areas):
        kb = [
            [InlineKeyboardButton(f"⚖️ {a.replace('_', ' ').title()}", callback_data=f"area:{a}")]
            for a in areas
        ]
        kb.append([InlineKeyboardButton("🔙 Voltar", callback_data="menu_principal")])
        return InlineKeyboardMarkup(kb)

    @staticmethod
    def listar_pecas(area, pecas):
        kb = [
            [InlineKeyboardButton(f"📄 {p.replace('_', ' ').title()}", callback_data=f"peca:{area}:{p}")]
            for p in pecas
        ]
        kb.append([InlineKeyboardButton("🔙 Voltar", callback_data="menu_biblioteca")])
        return InlineKeyboardMarkup(kb)

    @staticmethod
    def menu_peca(area, peca):
        base = f"{area}:{peca}"
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Esqueleto", callback_data=f"esqueleto:{base}")],
            [InlineKeyboardButton("📋 Checklist", callback_data=f"checklist:{base}")],
            [InlineKeyboardButton("📌 Requisitos", callback_data=f"requisitos:{base}")],
            [InlineKeyboardButton("⚖️ Fundamentos", callback_data=f"fundamentos:{base}")],
            [InlineKeyboardButton("🤖 Instruções IA", callback_data=f"instrucoes:{base}")],
            [InlineKeyboardButton("📦 Kit completo", callback_data=f"kit:{base}")],
            [InlineKeyboardButton("🔙 Voltar", callback_data=f"area:{area}")],
        ])

    @staticmethod
    def voltar(destino):
        return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Voltar", callback_data=destino)]])
