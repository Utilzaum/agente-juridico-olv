import os
import re
import time
import requests
import chromadb
from chromadb.utils import embedding_functions
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

# =========================================================
# ⚙️ CONFIGURAÇÕES
# =========================================================
load_dotenv()
DB_PATH = "db_vetorial"
COLECAO_ARTIGOS = "legislacao_artigos"
COLECAO_BLOCOS = "legislacao_blocos"
COLECAO_DICIONARIO = "dicionario_juridico"  # ✅ NOVA COLEÇÃO
OLLAMA_MODEL = "hf.co/LiquidAI/LFM2.5-1.2B-Thinking-GGUF:Q4_K_M"
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/chat")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_IA")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")

if not TOKEN:
    raise ValueError("❌ TOKEN não encontrado no .env")

bot = telebot.TeleBot(TOKEN)

# Memória volátil
historicos = {}
filtros_ativos = {}

# ✅ CORREÇÃO 1: Regex robusta - captura "335", "335-A", "335º"
RE_BUSCA_EXATA = re.compile(
    r"art(?:igo)?\.?\s*(\d+[A-Za-zº.-]*)\s*(?:do|da|de)?\s*(cpc|clt|cdc|cf|cc|cp|cpp|jec|jef)?",
    re.IGNORECASE
)

ALIAS_PARA_ARQUIVO = {
    "cpc": "cpc.html", "clt": "clt.html", "cdc": "cdc.html",
    "cf": "constituicao.html", "cc": "cc.html", "cp": "cp.html",
    "cpp": "cpp.html", "jec": "JEC_JECRIM.html", "jef": "jef.html",
}

MAPEAMENTO_LEIS = {
    "rag_cpc": {"nome": "Código de Processo Civil", "arquivo": "cpc.html", "aliases": ["cpc", "processo civil"]},
    "rag_clt": {"nome": "CLT", "arquivo": "clt.html", "aliases": ["clt", "trabalhista", "trabalho"]},
    "rag_cdc": {"nome": "Código do Consumidor", "arquivo": "cdc.html", "aliases": ["cdc", "consumidor"]},
    "rag_cf": {"nome": "Constituição Federal", "arquivo": "constituicao.html", "aliases": ["cf", "constituicao", "constituição"]},
    "rag_cc": {"nome": "Código Civil", "arquivo": "cc.html", "aliases": ["cc", "código civil", "civil"]},
    "rag_cp": {"nome": "Código Penal", "arquivo": "cp.html", "aliases": ["cp", "penal"]},
    "rag_cpp": {"nome": "Processo Penal", "arquivo": "cpp.html", "aliases": ["cpp", "processo penal"]},
    "rag_jec": {"nome": "Juizados Especiais", "arquivo": "JEC_JECRIM.html", "aliases": ["jec", "jecrim", "juizado"]},
    "rag_jef": {"nome": "Juizados Federais", "arquivo": "jef.html", "aliases": ["jef"]},
    "rag_geral": {"nome": "Busca Global", "arquivo": None, "aliases": []},
}

# ✅ CORREÇÃO 4: Expansão de Query para melhorar recall
SINONIMOS_RAG = {
    "despacho saneador": "artigo 357 saneamento organização do processo cpc",
    "contestação": "artigo 335 contestação prazo defesa cpc",
    "revelia": "artigo 344 revelia efeitos cpc",
    "tutela de urgência": "artigo 300 tutela de urgência requisitos cpc",
    "agravo de instrumento": "artigo 1015 agravo de instrumento cabimento cpc"
}

# =========================================================
# 🧠 CONEXÃO COM CHROMADB (ATUALIZADO COM DICIONÁRIO)
# =========================================================
def obter_conexao_chroma():
    try:
        modelo_embedding = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
        cliente_db = chromadb.PersistentClient(path=DB_PATH)
        colecao_artigos = cliente_db.get_collection(
            name=COLECAO_ARTIGOS,
            embedding_function=modelo_embedding
        )
        colecao_blocos = cliente_db.get_collection(
            name=COLECAO_BLOCOS,
            embedding_function=modelo_embedding
        )
        colecao_dicionario = cliente_db.get_collection(  # ✅ CORREÇÃO 7
            name=COLECAO_DICIONARIO,
            embedding_function=modelo_embedding
        )
        print("✅ Conexão com ChromaDB estabelecida (artigos + blocos + dicionário).")
        return colecao_artigos, colecao_blocos, colecao_dicionario
    except Exception as e:
        print(f"❌ Erro ao conectar ao ChromaDB: {e}")
        print("💡 Execute 'indexar_leis_html.py' e 'indexar_dicionario.py' primeiro.")
        return None, None, None

colecao_artigos, colecao_blocos, colecao_dicionario = obter_conexao_chroma()

# =========================================================
# 🎯 INTENT SERVICE (CORRIGIDO)
# =========================================================
def classificar_intencao(pergunta):
    """
    ✅ CORREÇÃO 2: Prioriza busca exata acima de tudo
    """
    # 1. ARTIGO_EXATO (prioridade máxima)
    if RE_BUSCA_EXATA.search(pergunta):
        return "LOCALIZAR"
    
    pergunta_lower = pergunta.lower()
    
    # 2. CONCEITO
    palavras_conceito = ["o que é", "o que sao", "significa", "conceito", "definição"]
    if any(p in pergunta_lower for p in palavras_conceito):
        return "CONCEITO"
    
    # 3. LOCALIZAR (prazo, texto, mostrar)
    palavras_localizar = ["texto", "mostrar", "transcrever", "diga o que diz", "redação", "prazo"]
    if any(p in pergunta_lower for p in palavras_localizar):
        return "LOCALIZAR"
    
    # 4. INTERPRETAR (default)
    return "INTERPRETAR"

# =========================================================
# 📖 BUSCA NO DICIONÁRIO
# =========================================================
def buscar_no_dicionario(pergunta, n_results=1, threshold=0.6):
    if not colecao_dicionario:
        return None
    try:
        resultados = colecao_dicionario.query(
            query_texts=[pergunta],
            n_results=n_results
        )
        if resultados and resultados['documents'] and resultados['documents'][0]:
            doc = resultados['documents'][0][0]
            meta = resultados['metadatas'][0][0]
            distancia = resultados['distances'][0][0]
            if distancia < threshold:
                return {
                    "titulo": meta['titulo'],
                    "texto": doc,
                    "fonte": meta['fonte'],
                    "distancia": distancia
                }
    except Exception as e:
        print(f"⚠️ Erro na busca do dicionário: {e}")
    return None

# =========================================================
# 🔍 BUSCA EXATA
# =========================================================
def buscar_artigo_exato(pergunta, chat_id):
    match = RE_BUSCA_EXATA.search(pergunta)
    if not match:
        return None
    
    numero_artigo = match.group(1).strip()
    alias_lei = match.group(2)
    fonte = None
    
    if alias_lei:
        fonte = ALIAS_PARA_ARQUIVO.get(alias_lei.lower())
    else:
        filtro_atual = filtros_ativos.get(chat_id, "rag_geral")
        if filtro_atual != "rag_geral":
            fonte = MAPEAMENTO_LEIS[filtro_atual]["arquivo"]
    
    if not fonte:
        return None
    
    try:
        resultados = colecao_artigos.query(
            query_texts=[f"artigo {numero_artigo}"],
            n_results=1,
            where={"$and": [{"artigo": numero_artigo}, {"fonte": fonte}]}
        )
        if resultados and resultados['documents'] and resultados['documents'][0]:
            doc = resultados['documents'][0][0]
            meta = resultados['metadatas'][0][0]
            lei_nome = meta.get('lei', fonte.replace('.html', ''))
            return {
                "tipo": "artigo_principal",
                "lei": lei_nome,
                "artigo": meta['artigo'],
                "texto": doc,
                "fonte": fonte,
                "ano": meta.get('ano', 'N/A')
            }
    except Exception as e:
        print(f"⚠️ Erro na busca exata: {e}")
    return None

# =========================================================
# 🏗️ CONTEXT BUILDER (OTIMIZADO)
# =========================================================
def montar_contexto(pergunta, chat_id, artigo_exato, verbete_dicionario=None):
    blocos_texto = []
    
    # 1. Dicionário (se existir)
    if verbete_dicionario:
        blocos_texto.append(
            f"========================\n"
            f"📖 DEFINIÇÃO JURÍDICA\n"
            f"========================\n"
            f"📌 {verbete_dicionario['titulo']}:\n"
            f"{verbete_dicionario['texto']}\n"
            f"(Fonte: {verbete_dicionario['fonte']})\n"
        )
    
    # 2. Artigo Exato (se existir)
    if artigo_exato:
        blocos_texto.append(
            f"========================\n"
            f"NORMA PRINCIPAL\n"
            f"========================\n"
            f"📦 [{artigo_exato['lei']} - Art. {artigo_exato['artigo']}]:\n"
            f"{artigo_exato['texto']}\n"
        )
    
    # 3. Filtro de fonte
    filtro_atual = filtros_ativos.get(chat_id, "rag_geral")
    filtro_metadado = {}
    if filtro_atual != "rag_geral":
        meta = MAPEAMENTO_LEIS.get(filtro_atual)
        if meta and meta["arquivo"]:
            filtro_metadado["fonte"] = meta["arquivo"]
    else:
        texto_lower = pergunta.lower()
        for id_lei, info in MAPEAMENTO_LEIS.items():
            if id_lei == "rag_geral":
                continue
            for alias in info["aliases"]:
                if alias in texto_lower:
                    filtro_metadado["fonte"] = info["arquivo"]
                    break
            if "fonte" in filtro_metadado:
                break
    
    # ✅ CORREÇÃO 6: Reduzir n_results + Expansão de query
    try:
        # Expansão de sinônimos
        consulta_rag = pergunta
        for termo, expandido in SINONIMOS_RAG.items():
            if termo in pergunta.lower():
                consulta_rag = expandido
                break
        
        query_args = {"query_texts": [consulta_rag], "n_results": 3}  # Apenas 3 artigos
        if "fonte" in filtro_metadado:
            query_args["where"] = {"fonte": filtro_metadado["fonte"]}
        resultados_artigos = colecao_artigos.query(**query_args)
        
        query_args_blocos = {"query_texts": [consulta_rag], "n_results": 2}  # Apenas 2 blocos
        if "fonte" in filtro_metadado:
            query_args_blocos["where"] = {"fonte": filtro_metadado["fonte"]}
        resultados_blocos = colecao_blocos.query(**query_args_blocos)
        
        if resultados_artigos and resultados_artigos['documents'] and resultados_artigos['documents'][0]:
            for i, doc in enumerate(resultados_artigos['documents'][0]):
                meta = resultados_artigos['metadatas'][0][i]
                fonte = meta['fonte'].replace('.html', '').upper()
                if artigo_exato and meta['artigo'] == artigo_exato['artigo'] and meta['fonte'] == artigo_exato['fonte']:
                    continue
                blocos_texto.append(f"📦 [{fonte} - Art. {meta['artigo']}]:\n{doc}")
        
        if resultados_blocos and resultados_blocos['documents'] and resultados_blocos['documents'][0]:
            for i, doc in enumerate(resultados_blocos['documents'][0]):
                meta = resultados_blocos['metadatas'][0][i]
                fonte = meta['fonte'].replace('.html', '').upper()
                blocos_texto.append(f"📚 [{fonte} - Arts. {meta['artigo_inicial']} a {meta['artigo_final']}]:\n{doc}")
    except Exception as e:
        print(f"⚠️ Falha na consulta RAG: {e}")
    
    return "\n\n".join(blocos_texto)

# =========================================================
# 🛡️ FILTRO DE RACIOCÍNIO
# =========================================================
def limpar_raciocinio(texto):
    return re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL).strip()

# =========================================================
#  GERADOR DE BOTÕES
# =========================================================
def gerar_menu_leis(chat_id):
    filtro_atual = filtros_ativos.get(chat_id, "rag_geral")
    markup = InlineKeyboardMarkup(row_width=2)
    botoes = []
    for id_callback, info in MAPEAMENTO_LEIS.items():
        prefixo = "📌 " if id_callback == filtro_atual else ""
        botoes.append(InlineKeyboardButton(f"{prefixo}{info['nome']}", callback_data=id_callback))
    markup.add(*botoes[:-1])
    markup.add(botoes[-1])
    return markup

# =========================================================
# 📨 HANDLERS
# =========================================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("rag_"))
def handle_clique_botao(call):
    chat_id = call.message.chat.id
    opcao_selecionada = call.data
    
    if chat_id in filtros_ativos and filtros_ativos[chat_id] != opcao_selecionada:
        historicos[chat_id] = []
    filtros_ativos[chat_id] = opcao_selecionada
    
    nome_lei = MAPEAMENTO_LEIS[opcao_selecionada]["nome"]
    try:
        bot.answer_callback_query(call.id, f"Filtro ativo: {nome_lei}")
    except Exception as e:
        print(f"ℹ️ Callback antigo ignorado: {e}")
    
    try:
        bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=gerar_menu_leis(chat_id)
        )
    except Exception as e:
        print(f"⚠️ Falha ao atualizar menu: {e}")

@bot.message_handler(commands=['start', 'menu'])
def enviar_painel(message):
    chat_id = message.chat.id
    if chat_id not in filtros_ativos:
        filtros_ativos[chat_id] = "rag_geral"
    bot.reply_to(
        message,
        "️ Painel de Controle RAG - Oliveira Advocacia\n\n"
        "Selecione uma legislação ou use a 'Busca Global'.\n\n"
        "💡 Dica: Pergunte 'art. 147' para ver o texto, ou 'explique o art. 147' para uma análise jurídica.",
        parse_mode="Markdown",
        reply_markup=gerar_menu_leis(chat_id)
    )

@bot.message_handler(commands=['limpar'])
def comando_limpar(message):
    chat_id = message.chat.id
    historicos[chat_id] = []
    bot.reply_to(message, " Memória contextual limpa!")

@bot.message_handler(func=lambda message: True)
def processar_mensagem(message):
    texto_puro = message.text.lower().strip()
    if texto_puro == "menu":
        enviar_painel(message)
        return
    elif texto_puro in ["limpar", "clear", "limpar memoria"]:
        comando_limpar(message)
        return
    
    if colecao_artigos is None or colecao_blocos is None or colecao_dicionario is None:
        bot.reply_to(message, "⚠️ Base de dados não disponível. Execute a indexação primeiro.")
        return
    
    chat_id = message.chat.id
    pergunta = message.text
    
    # 1️⃣ INTENT SERVICE
    intencao = classificar_intencao(pergunta)
    
    # 2️⃣ BUSCA EXATA
    artigo_exato = buscar_artigo_exato(pergunta, chat_id)
    
    # 3️⃣ FLUXO DOCUMENTAL (LOCALIZAR)
    if intencao == "LOCALIZAR" and artigo_exato:
        resposta_formatada = (
            f"📜 **{artigo_exato['lei']}**\n"
            f"**Art. {artigo_exato['artigo']}**\n\n"
            f"{artigo_exato['texto']}\n\n"
            f"_(Fonte: {artigo_exato['fonte']} | Ano: {artigo_exato['ano']})_"
        )
        bot.reply_to(message, resposta_formatada, parse_mode="Markdown", reply_markup=gerar_menu_leis(chat_id))
        return
    
    # 4️⃣ BUSCA RÁPIDA NO DICIONÁRIO (Resposta instantânea para conceitos)
    verbete_dicionario = None
    if colecao_dicionario:
        verbete_dicionario = buscar_no_dicionario(pergunta, n_results=1, threshold=0.5)
    
    if verbete_dicionario and intencao == "CONCEITO":
        resposta_direta = (
            f"📖 **{verbete_dicionario['titulo']}**\n\n"
            f"{verbete_dicionario['texto']}\n\n"
            f"_Fonte: {verbete_dicionario['fonte']}_\n"
            f"_Similaridade: {(1 - verbete_dicionario['distancia'] / 2):.0%}_"
        )
        bot.reply_to(message, resposta_direta, parse_mode="Markdown", reply_markup=gerar_menu_leis(chat_id))
        return
    
    # 5️ FLUXO INTERPRETATIVO
    status_msg = bot.reply_to(message, " Consultando base híbrida e analisando intenção... Aguarde.")
    try:
        bot.send_chat_action(chat_id, 'typing')
    except Exception:
        pass
    
    # 🏗️ CONTEXT BUILDER
    leis_contexto = montar_contexto(pergunta, chat_id, artigo_exato, verbete_dicionario)
    
    # ✅ CORREÇÃO 3: Prompt Blindado e Estruturado
    if leis_contexto:
        prompt_final = (
            f"CONTEXTO JURÍDICO:\n=========================\n{leis_contexto}\n=========================\n\n"
            f"INSTRUÇÕES:\n"
            f"1. Utilize SOMENTE o contexto acima.\n"
            f"2. Cite TODOS os artigos utilizados (ex: 'Conforme o Art. 357 do CPC').\n"
            f"3. Nunca omita o número do artigo e nunca invente leis.\n"
            f"4. Se a resposta não estiver no contexto, diga exatamente: 'Não encontrei base documental suficiente no contexto recuperado.'\n\n"
            f"PERGUNTA:\n{pergunta}"
        )
    else:
        prompt_final = (
            f"PERGUNTA:\n{pergunta}\n\n"
            f"INSTRUÇÃO: A base de dados não retornou contexto. Informe que não há informações suficientes no sistema."
        )
    
    #  INTEGRAÇÃO COM IA
    if chat_id not in historicos:
        historicos[chat_id] = []
    
    historicos[chat_id].append({"role": "user", "content": prompt_final})
    
    # Mantém apenas últimas 4 mensagens
    if len(historicos[chat_id]) > 4:
        historicos[chat_id] = historicos[chat_id][-4:]
    
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "messages": historicos[chat_id],
            "stream": False,
            "options": {"temperature": 0.0, "top_p": 0.1}
        }
        resposta = requests.post(OLLAMA_API_URL, json=payload, timeout=120)
        resposta.raise_for_status()
        texto_ia_bruto = resposta.json()['message']['content']
        
        # 🛡️ FILTRO DE RACIOCÍNIO
        texto_ia = limpar_raciocinio(texto_ia_bruto)
        historicos[chat_id].append({"role": "assistant", "content": texto_ia})
        
        try:
            bot.delete_message(chat_id, status_msg.message_id)
        except Exception:
            pass
        
        # ✅ CORREÇÃO 5: parse_mode=None para evitar erro de Markdown
        bot.reply_to(message, texto_ia, parse_mode=None, reply_markup=gerar_menu_leis(chat_id))
    except Exception as e:
        try:
            bot.delete_message(chat_id, status_msg.message_id)
        except Exception:
            pass
        bot.reply_to(message, f"❌ Erro na IA local: {str(e)}", reply_markup=gerar_menu_leis(chat_id))
        if historicos[chat_id] and historicos[chat_id][-1]["role"] == "user":
            historicos[chat_id].pop()

# =========================================================
# 🚀 PONTO DE ENTRADA
# =========================================================
if __name__ == "__main__":
    print("🚀 Bot OCR Conversacional com IntentService + RAG Híbrido + Dicionário Jurídico...")
    while True:
        try:
            bot.polling(none_stop=True, timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"⚠️ Queda de conexão: {e}")
            print("🔄 Reconectando em 5s...")
            time.sleep(5)
