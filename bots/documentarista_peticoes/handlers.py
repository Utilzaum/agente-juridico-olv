"""Handlers do Bot Documentarista de Petições."""
from telegram.error import BadRequest

from core.peticionamento.loader import BibliotecaLoader
from core.peticionamento.formatter import FormatterPeticoes
from bots.documentarista_peticoes.keyboards import Keyboards
from bots.documentarista_peticoes.config import BIBLIOTECA_DIR, BOT_NAME, BOT_VERSION


class Handlers:
    def __init__(self):
        self.loader = BibliotecaLoader(BIBLIOTECA_DIR)
        self.formatter = FormatterPeticoes()

    def _nome(self, codigo):
        return codigo.replace("_", " ").title()

    async def _texto(self, update, texto, markup=None):
        query = update.callback_query
        if query is None:
            await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=markup)
            return
        try:
            await query.edit_message_text(texto, parse_mode="Markdown", reply_markup=markup)
        except BadRequest:
            await query.message.reply_text(texto, parse_mode="Markdown", reply_markup=markup)

    async def _doc(self, update, texto, filename, caption):
        await update.callback_query.message.reply_document(
            document=texto.encode("utf-8"), filename=filename, caption=caption
        )

    def _voltar_peca(self, area, peca):
        return Keyboards.voltar(f"peca:{area}:{peca}")

    async def start(self, update, context):
        texto = (
            f"📚 *{BOT_NAME}* (v{BOT_VERSION})\n\n"
            "Biblioteca jurídica estruturada do escritório.\n"
            "O conhecimento vive nos JSON/MD; aqui é só o mensageiro. 📬\n\n"
            "Escolha uma opção:"
        )
        await self._texto(update, texto, Keyboards.menu_principal())

    async def menu_biblioteca(self, update, context):
        areas = self.loader.listar_areas()
        if not areas:
            await self._texto(update, "🗂 Nenhuma área na biblioteca.", Keyboards.voltar("menu_principal"))
            return
        await self._texto(update, "📂 *BIBLIOTECA DE PETIÇÕES*\n\nEscolha a área:", Keyboards.listar_areas(areas))

    async def selecionar_area(self, update, context, area):
        pecas = self.loader.listar_pecas(area)
        if not pecas:
            await self._texto(update, f"⚠️ Nenhuma peça em {self._nome(area)}.", Keyboards.voltar("menu_biblioteca"))
            return
        await self._texto(update, f"⚖️ *{self._nome(area).upper()}*\n\nEscolha a peça:", Keyboards.listar_pecas(area, pecas))

    async def selecionar_peca(self, update, context, area, peca):
        await self._texto(update, f"📄 *{self._nome(peca).upper()}*\n\nO que deseja obter?", Keyboards.menu_peca(area, peca))

    async def mostrar_esqueleto(self, update, context, area, peca):
        conteudo = self.loader.carregar_esqueleto(area, peca)
        if not conteudo:
            await self._texto(update, "⚠️ Esqueleto não encontrado.", self._voltar_peca(area, peca))
            return
        await self._doc(update, conteudo, f"esqueleto_{peca}.md", f"📝 Esqueleto — {self._nome(peca)}")
        await self._texto(update, f"📝 Esqueleto de {self._nome(peca)} enviado.", self._voltar_peca(area, peca))

    async def mostrar_checklist(self, update, context, area, peca):
        dados = self.loader.carregar_checklist(area, peca)
        if not dados:
            await self._texto(update, "⚠️ Checklist não encontrado.", self._voltar_peca(area, peca))
            return
        await self._doc(update, self.formatter.formatar_checklist(dados), f"checklist_{peca}.txt", f"📋 Checklist — {self._nome(peca)}")
        await self._texto(update, f"📋 Checklist de {self._nome(peca)} enviado.", self._voltar_peca(area, peca))

    async def mostrar_requisitos(self, update, context, area, peca):
        dados = self.loader.carregar_requisitos(area, peca)
        if not dados:
            await self._texto(update, "⚠️ Requisitos não encontrados.", self._voltar_peca(area, peca))
            return
        await self._doc(update, self.formatter.formatar_requisitos(dados), f"requisitos_{peca}.txt", f"📌 Requisitos — {self._nome(peca)}")
        await self._texto(update, f"📌 Requisitos de {self._nome(peca)} enviados.", self._voltar_peca(area, peca))

    async def mostrar_fundamentos(self, update, context, area, peca):
        dados = self.loader.carregar_fundamentos(area, peca)
        if not dados:
            await self._texto(update, "⚠️ Fundamentos não encontrados.", self._voltar_peca(area, peca))
            return
        await self._doc(update, self.formatter.formatar_fundamentos(dados), f"fundamentos_{peca}.txt", f"⚖️ Fundamentos — {self._nome(peca)}")
        await self._texto(update, f"⚖️ Fundamentos de {self._nome(peca)} enviados.", self._voltar_peca(area, peca))

    async def mostrar_instrucoes(self, update, context, area, peca):
        conteudo = self.loader.carregar_instrucoes_ia(area, peca)
        if not conteudo:
            await self._texto(update, "⚠️ Instruções IA não encontradas.", self._voltar_peca(area, peca))
            return
        await self._doc(update, conteudo, f"instrucoes_ia_{peca}.md", f"🤖 Instruções IA — {self._nome(peca)}")
        await self._texto(update, f"🤖 Instruções de {self._nome(peca)} enviadas.", self._voltar_peca(area, peca))

    async def mostrar_kit(self, update, context, area, peca):
        estrutura = self.loader.carregar_estrutura(area, peca)
        requisitos = self.loader.carregar_requisitos(area, peca)
        fundamentos = self.loader.carregar_fundamentos(area, peca)
        checklist = self.loader.carregar_checklist(area, peca)
        texto = self.formatter.formatar_kit(area, peca, estrutura, requisitos, fundamentos, checklist)
        await self._texto(update, texto, self._voltar_peca(area, peca))

    async def sobre(self, update, context):
        texto = (
            f"📚 *{BOT_NAME}* (v{BOT_VERSION})\n\n"
            "Conhecimento jurídico em JSON/MD.\n"
            "Código = apenas mecanismo.\n\n"
            "Projeto: github.com/Utilzaum/agente-juridico-olv"
        )
        await self._texto(update, texto, Keyboards.voltar("menu_principal"))
