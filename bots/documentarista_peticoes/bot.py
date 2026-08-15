#!/usr/bin/env python3
"""Bot Telegram — Documentarista de Petições OLV (isolado)."""
import logging

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters,
)

from bots.documentarista_peticoes.config import (
    TELEGRAM_BOT_TOKEN, AUTHORIZED_USERS, LOGS_DIR, BOT_NAME,
)
from bots.documentarista_peticoes.handlers import Handlers

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler(LOGS_DIR / "bot.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class DocumentaristaPeticoesBot:
    def __init__(self):
        self.handlers = Handlers()
        self.application = None

    def autorizado(self, user_id):
        if not AUTHORIZED_USERS:
            return True
        return user_id in AUTHORIZED_USERS

    async def cmd_start(self, update: Update, context):
        if not self.autorizado(update.effective_user.id):
            await update.message.reply_text("⛔ Acesso não autorizado.")
            return
        await self.handlers.start(update, context)

    async def on_callback(self, update: Update, context):
        query = update.callback_query
        if not self.autorizado(update.effective_user.id):
            await query.answer("⛔ Não autorizado.", show_alert=True)
            return

        data = query.data
        logger.info("callback=%s user=%s", data, update.effective_user.id)
        parts = data.split(":")

        if data == "menu_principal":
            await query.answer()
            await self.handlers.start(update, context)
        elif data == "menu_biblioteca":
            await query.answer()
            await self.handlers.menu_biblioteca(update, context)
        elif data == "menu_sobre":
            await query.answer()
            await self.handlers.sobre(update, context)
        elif data == "menu_buscar":
            await query.answer("🔎 Busca chega na próxima fase.", show_alert=True)
        elif len(parts) == 2 and parts[0] == "area":
            await query.answer()
            await self.handlers.selecionar_area(update, context, parts[1])
        elif len(parts) == 3 and parts[0] == "peca":
            await query.answer()
            await self.handlers.selecionar_peca(update, context, parts[1], parts[2])
        elif len(parts) == 3:
            await query.answer()
            acao, area, peca = parts
            mapa = {
                "esqueleto": self.handlers.mostrar_esqueleto,
                "checklist": self.handlers.mostrar_checklist,
                "requisitos": self.handlers.mostrar_requisitos,
                "fundamentos": self.handlers.mostrar_fundamentos,
                "instrucoes": self.handlers.mostrar_instrucoes,
                "kit": self.handlers.mostrar_kit,
            }
            fn = mapa.get(acao)
            if fn:
                await fn(update, context, area, peca)
        else:
            await query.answer()

    async def desconhecido(self, update: Update, context):
        await update.message.reply_text("Use /start 🙂")

    def run(self):
        logger.info("Iniciando %s ...", BOT_NAME)
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CallbackQueryHandler(self.on_callback))
        self.application.add_handler(MessageHandler(filters.COMMAND, self.desconhecido))

        self.application.run_polling(allowed_updates=Update.ALL_TYPES)
        logger.info("Bot no ar. CTRL+C para parar.")


def main():
    DocumentaristaPeticoesBot().run()


if __name__ == "__main__":
    main()
