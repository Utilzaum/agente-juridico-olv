# bot_ocr_conversacional.py
"""
Bot OCR Conversacional — Bibliotecário Jurídico RAG
✅ Camada A (artigos nomeados -> metadado) + RRF (Embedding + BM25) + BM25 por fonte
✅ Histórico inteligente + contexto estruturado "Documentos Recuperados"
✅ REFATOR: perfil dinâmico via montar_prompt (selecionar_perfil em código)
✅ REFATOR: intent respeita verbo ("disserte sobre o art 147" => LLM, não transcrição)
✅ REFATOR: regex de múltiplos artigos robusta ("arts. 14, e 12" => ['14','12'])
✅ NOVO: sinônimos para injúria, difamação, calúnia, habeas corpus, legítima defesa, estado de necessidade
✅ NOVO: comando /help e /ajuda
"""
import os
import re
import time
import logging
import hashlib
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

# ✅ REFATOR (Patch A): importa só montar_prompt; o handler usa ele (não os aliases)
from infra.llm.prompts import montar_prompt
from infra.llm.ollama_client import chat as llm_chat
from infra.rag.bm25_reranker import rerank_bm25, buscar_bm25_puro, reciprocal_rank_fusion

# =========================================================
# LOGGING
# =========================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# =========================================================
# ⚙️ CONFIGURAÇÕES
# =========================================================
load_dotenv()

DB_PATH = "db_vetorial"
COLECAO_ARTIGOS = "legislacao_artigos"
COLECAO_BLOCOS = "legislacao_blocos"
COLECAO_DICIONARIO = "dicionario_juridico"

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_IA")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")

MAX_DISTANCE_ARTIGOS = float(os.getenv("MAX_DISTANCE_ARTIGOS", "0.55"))
MAX_DISTANCE_BLOCOS = float(os.getenv("MAX_DISTANCE_BLOCOS", "0.60"))
MAX_DISTANCE_DICIONARIO = float(os.getenv("MAX_DISTANCE_DICIONARIO", "0.50"))

CHROMA_TOP_K = 15
BM25_TOP_K = 15
RRF_TOP_K = 8

if not TOKEN:
    raise ValueError("❌ TOKEN não encontrado no .env")

bot = telebot.TeleBot(TOKEN)

historicos = {}
filtros_ativos = {}

_corpus_bm25_cache = {}
_corpus_bm25_timestamp = 0

# =========================================================
# REGEX E MAPEAMENTOS
# =========================================================

# ✅ REFATOR: sufixo com * e separadores com \s* (casa "art. 12", "art 147", "art. 5º")
RE_BUSCA_EXATA = re.compile(
    r"art(?:igo)?\.?\s*(\d+[A-Za-zº.-]*)\s*(?:do|da|de)?\s*(cpc|clt|cdc|cf|cc|cp|cpp|jec|jef)?",
    re.IGNORECASE
)

# ✅ REFATOR (Patch C): separador (,|e) com \s* opcional -> "14, e 12" vira ['14','12']
RE_ARTIGOS_MENCIONADOS = re.compile(
    r"art(?:igo)?s?\.?\s*(\d+[A-Za-zº.-]*(?:(?:\s*(?:,|\be\b)\s*)+\d+[A-Za-zº.-]*)*)",
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

# =========================================================
# 🧠 SINÔNIMOS PARA EXPANSÃO DE CONSULTA (REFATORADO)
# =========================================================
SINONIMOS_RAG = {
    "despacho saneador": "artigo 357 saneamento organização do processo cpc",
    "contestação": "artigo 335 contestação prazo defesa cpc",
    "revelia": "artigo 344 revelia efeitos cpc",
    "tutela de urgência": "artigo 300 tutela de urgência requisitos cpc",
    "agravo de instrumento": "artigo 1015 agravo de instrumento cabimento cpc",
    "responsabilidade civil": "responsabilidade civil fornecedor produto serviço dano indenização",
    "responsabilidade do fornecedor": "responsabilidade fornecedor produto serviço fato vício",
    # NOVOS SINÔNIMOS ADICIONADOS:
    "injúria": "artigo 140 injúria crime contra a honra CP código penal",
    "difamação": "artigo 139 difamação crime contra a honra CP código penal",
    "calúnia": "artigo 138 calúnia crime contra a honra CP código penal",
    "crimes contra a honra": "artigo 138 139 140 calúnia difamação injúria honra CP",
    "habeas corpus": "artigo 5 inciso LXVIII habeas corpus constituição",
    "legítima defesa": "artigo 25 legítima defesa CP código penal",
    "estado de necessidade": "artigo 24 estado de necessidade CP código penal",
    "ameaça": "artigo 147 ameaçar crime de ameaça CP código penal",
    "perseguição": "artigo 147-A stalking perseguição CP código penal",
    "violência doméstica": "artigo 147-B dano emocional mulher CP código penal",
}

# =========================================================
# 🧠 CONEXÃO COM CHROMADB
# =========================================================
def obter_conexao_chroma():
    try:
        import chromadb
        from chromadb.utils import embedding_functions

        modelo_embedding = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
        cliente_db = chromadb.PersistentClient(path=DB_PATH)
        colecao_artigos = cliente_db.get_collection(
            name=COLECAO_ARTIGOS, embedding_function=modelo_embedding
        )
        colecao_blocos = cliente_db.get_collection(
            name=COLECAO_BLOCOS, embedding_function=modelo_embedding
        )
        colecao_dicionario = cliente_db.get_collection(
            name=COLECAO_DICIONARIO, embedding_function=modelo_embedding
        )
        logger.info("✅ Conexão com ChromaDB estabelecida (artigos + blocos + dicionário).")
        return colecao_artigos, colecao_blocos, colecao_dicionario
    except Exception as e:
        logger.error(f"❌ Erro ao conectar ao ChromaDB: {e}")
        return None, None, None


colecao_artigos, colecao_blocos, colecao_dicionario = obter_conexao_chroma()

# =========================================================
# 📦 CORPUS BM25 (filtrado por fonte)
# =========================================================
def _gerar_doc_id(doc: dict) -> str:
    conteudo = f"{doc.get('fonte', '')}:{doc.get('artigo', '')}:{doc.get('texto', '')[:100]}"
    return hashlib.md5(conteudo.encode()).hexdigest()


def _carregar_corpus_bm25(fonte: str = None):
    global _corpus_bm25_cache, _corpus_bm25_timestamp

    chave = fonte or "ALL"
    agora = time.time()
    if chave in _corpus_bm25_cache and (agora - _corpus_bm25_timestamp) < 600:
        return _corpus_bm25_cache[chave]

    logger.info(f"📦 Carregando corpus BM25 (fonte={chave})...")
    corpus = []
    try:
        get_args = {}
        if fonte:
            get_args["where"] = {"fonte": fonte}
        resultado_artigos = colecao_artigos.get(**get_args)
        if resultado_artigos and resultado_artigos['documents']:
            for i, doc in enumerate(resultado_artigos['documents']):
                meta = resultado_artigos['metadatas'][i]
                item = {
                    "tipo": "Artigo Legal",
                    "fonte": meta.get('fonte', 'desconhecida').replace('.html', '').upper(),
                    "artigo": meta.get('artigo', 'N/A'),
                    "texto": doc,
                    "titulo": None
                }
                item["_doc_id"] = _gerar_doc_id(item)
                corpus.append(item)

        get_args_blocos = {}
        if fonte:
            get_args_blocos["where"] = {"fonte": fonte}
        resultado_blocos = colecao_blocos.get(**get_args_blocos)
        if resultado_blocos and resultado_blocos['documents']:
            for i, doc in enumerate(resultado_blocos['documents']):
                meta = resultado_blocos['metadatas'][i]
                item = {
                    "tipo": "Bloco Legislativo",
                    "fonte": meta.get('fonte', 'desconhecida').replace('.html', '').upper(),
                    "artigo": f"{meta.get('artigo_inicial', '?')} a {meta.get('artigo_final', '?')}",
                    "texto": doc,
                    "titulo": None
                }
                item["_doc_id"] = _gerar_doc_id(item)
                corpus.append(item)

        logger.info(f"✅ Corpus BM25 carregado (fonte={chave}): {len(corpus)} documentos")
        _corpus_bm25_cache[chave] = corpus
        _corpus_bm25_timestamp = agora
        return corpus
    except Exception as e:
        logger.error(f"❌ Erro ao carregar corpus BM25: {e}")
        return []

# =========================================================
# 🎯 INTENT SERVICE
# =========================================================
# ✅ REFATOR (Patch B): verbo de interpretação + artigo => INTERPRETAR (não transcrever)
def classificar_intencao(pergunta: str) -> str:
    p = pergunta.lower()
    verbos = ("disserte", "dissertar", "explique", "analise", "analisar", "comente",
              "interprete", "compare", "comparar", "fundamente", "esclareça", "conceitue", "conceituar", "defina", "definir")
    tem_verbo = any(v in p for v in verbos)
    tem_artigo = bool(RE_BUSCA_EXATA.search(pergunta))

    if tem_artigo and tem_verbo:      # "disserte sobre o art 147" => LLM (perfil CONSULTOR)
        return "INTERPRETAR"
    if tem_artigo:                     # "art 147" puro => transcrição direta
        return "LOCALIZAR"
    if any(x in p for x in ("o que é", "o que sao", "significa", "conceito", "definição", "conceitue", "conceituar")):
        return "CONCEITO"
    if any(x in p for x in ("texto", "mostrar", "transcrever", "diga o que diz", "redação")):
        return "LOCALIZAR"
    return "INTERPRETAR"

# =========================================================
# 📖 BUSCA NO DICIONÁRIO
# =========================================================
def buscar_no_dicionario(pergunta: str, n_results: int = 1, threshold: float = MAX_DISTANCE_DICIONARIO):
    if not colecao_dicionario:
        return None
    try:
        resultados = colecao_dicionario.query(query_texts=[pergunta], n_results=n_results)
        if resultados and resultados['documents'] and resultados['documents'][0]:
            doc = resultados['documents'][0][0]
            meta = resultados['metadatas'][0][0]
            distancia = resultados['distances'][0][0]
            logger.info(f"📖 Dicionário | distância={distancia:.4f} | threshold={threshold}")
            if distancia < threshold:
                return {
                    "titulo": meta.get('titulo', 'Verbete'),
                    "texto": doc,
                    "fonte": meta.get('fonte', 'Dicionário Jurídico'),
                    "distancia": distancia
                }
            else:
                logger.info("📖 Dicionário descartado (distância acima do threshold)")
    except Exception as e:
        logger.warning(f"⚠️ Erro na busca do dicionário: {e}")
    return None

# =========================================================
# 🔍 BUSCA EXATA (get por metadado, sem embedding)
# =========================================================
def buscar_artigo_exato(pergunta: str, chat_id: int):
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
        logger.info(f"🔍 Busca exata: fonte não determinada para '{pergunta}'")
        return None

    variacoes = [
        numero_artigo, f"Art. {numero_artigo}", f"art. {numero_artigo}",
        f"Artigo {numero_artigo}", f"{numero_artigo}º", f"{numero_artigo}°",
    ]
    for variacao in variacoes:
        try:
            resultados = colecao_artigos.get(
                where={"$and": [{"artigo": variacao}, {"fonte": fonte}]},
                limit=1
            )
            if resultados and resultados['documents'] and resultados['documents'][0]:
                doc = resultados['documents'][0]
                meta = resultados['metadatas'][0]
                lei_nome = meta.get('lei', fonte.replace('.html', '').upper())
                logger.info(f"✅ Busca exata: artigo='{variacao}' fonte='{fonte}' ENCONTRADO")
                return {
                    "tipo": "Artigo Legal",
                    "lei": lei_nome,
                    "artigo": meta['artigo'],
                    "texto": doc,
                    "fonte": fonte,
                    "ano": meta.get('ano', 'N/A')
                }
        except Exception as e:
            logger.warning(f"⚠️ Erro na busca exata (variação '{variacao}'): {e}")

    logger.info(f"❌ Busca exata: artigo='{numero_artigo}' fonte='{fonte}' NÃO ENCONTRADO")
    return None

# =========================================================
# ✅ CAMADA A: EXTRAÇÃO DE ARTIGOS NOMEADOS + BUSCA POR METADADO
# =========================================================
def extrair_artigos_mencionados(pergunta: str) -> list:
    artigos = []
    for match in RE_ARTIGOS_MENCIONADOS.finditer(pergunta):
        bloco = match.group(1)
        numeros = re.findall(r"(\d+[A-Za-zº.-]*)", bloco)
        artigos.extend(numeros)

    vistos = set()
    unicos = []
    for a in artigos:
        if a not in vistos:
            vistos.add(a)
            unicos.append(a)

    if unicos:
        logger.info(f"🔢 Artigos mencionados na pergunta: {unicos}")
    return unicos


def buscar_artigos_por_metadado(artigos: list, fonte: str = None) -> list:
    resultados = []
    for numero in artigos:
        try:
            if fonte:
                where = {"$and": [{"artigo": numero}, {"fonte": fonte}]}
            else:
                where = {"artigo": numero}
            r = colecao_artigos.get(where=where, limit=1)
            if r and r['documents'] and r['documents'][0]:
                doc = r['documents'][0]
                meta = r['metadatas'][0]
                item = {
                    "tipo": "Artigo Legal",
                    "fonte": meta.get('fonte', 'desconhecida').replace('.html', '').upper(),
                    "artigo": meta.get('artigo', numero),
                    "texto": doc,
                    "titulo": None,
                    "lei": meta.get('lei', meta.get('fonte', '').replace('.html', '').upper())
                }
                item["_doc_id"] = _gerar_doc_id(item)
                resultados.append(item)
                logger.info(f"✅ Artigo nomeado ENCONTRADO: art. {numero} | fonte={meta.get('fonte')}")
            else:
                logger.info(f"❌ Artigo nomeado NÃO encontrado: art. {numero} | fonte={fonte}")
        except Exception as e:
            logger.warning(f"⚠️ Erro na busca por metadado (art. {numero}): {e}")
    return resultados

# =========================================================
# 🏗️ CONTEXT BUILDER
# =========================================================
def montar_contexto(pergunta: str, chat_id: int, artigo_exato: dict, verbete_dicionario: dict = None) -> str:
    documentos_prioritarios = []

    if verbete_dicionario:
        item = {
            "tipo": "Doutrina / Dicionário Jurídico",
            "fonte": verbete_dicionario['fonte'],
            "titulo": verbete_dicionario['titulo'],
            "texto": verbete_dicionario['texto'],
            "artigo": None
        }
        item["_doc_id"] = _gerar_doc_id(item)
        documentos_prioritarios.append(item)

    if artigo_exato:
        item = {
            "tipo": artigo_exato['tipo'],
            "fonte": artigo_exato['lei'],
            "artigo": artigo_exato['artigo'],
            "texto": artigo_exato['texto'],
            "titulo": None
        }
        item["_doc_id"] = _gerar_doc_id(item)
        documentos_prioritarios.append(item)

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

    logger.info(f"🔍 Filtro de fonte: {filtro_metadado or 'nenhum (Busca Global)'}")

    artigos_mencionados = extrair_artigos_mencionados(pergunta)
    if artigos_mencionados:
        fonte_meta = filtro_metadado.get("fonte")
        artigos_nomeados_docs = buscar_artigos_por_metadado(artigos_mencionados, fonte_meta)
        for doc in artigos_nomeados_docs:
            if (artigo_exato
                    and doc.get('artigo') == artigo_exato.get('artigo')
                    and doc.get('fonte') == artigo_exato.get('lei', '').replace('.html', '').upper()):
                logger.info(f"⏭️ Art. {doc['artigo']} já está como artigo_exato, pulando")
                continue
            documentos_prioritarios.append(doc)

    consulta_rag = pergunta
    for termo, expandido in SINONIMOS_RAG.items():
        if termo in pergunta.lower():
            consulta_rag = f"{consulta_rag} {expandido}"
            logger.info(f"🔤 Expansão de query (concatenação): termo='{termo}'")

    # 🧠 CAMADA 2 (fallback): expansão por IA quando o dicionário não casa
    if consulta_rag == pergunta:
        try:
            sugestao = llm_chat(
                mensagens=[{"role": "user", "content":
                    f"Você é um bibliotecário jurídico. O usuário perguntou: '{pergunta}'. "
                    "Cite o artigo e a lei mais específicos sobre o tema e 3 termos-chave "
                    "para busca documental. Responda em uma única linha, sem explicações."}],
                model_key="bibliotecario", timeout=600
            )
            sugestao = limpar_raciocinio(sugestao or "").strip().replace("\n", " ")[:200]
            if sugestao:
                consulta_rag = f"{pergunta} {sugestao}"
                logger.info(f"🧠 Expansão de query por IA (fallback): '{sugestao}'")
        except Exception as e:
            logger.warning(f"⚠️ Expansão por IA falhou (seguindo sem expansão): {e}")

    candidatos_chroma = []
    try:
        query_args = {"query_texts": [consulta_rag], "n_results": CHROMA_TOP_K}
        if "fonte" in filtro_metadado:
            query_args["where"] = {"fonte": filtro_metadado["fonte"]}
        resultados_artigos = colecao_artigos.query(**query_args)
        if resultados_artigos and resultados_artigos['documents'] and resultados_artigos['documents'][0]:
            for i, doc in enumerate(resultados_artigos['documents'][0]):
                distancia = resultados_artigos['distances'][0][i]
                meta = resultados_artigos['metadatas'][0][i]
                logger.info(f"📄 Chroma Artigo [{i}] | dist={distancia:.4f} | art={meta.get('artigo')} | fonte={meta.get('fonte')}")
                if distancia > MAX_DISTANCE_ARTIGOS:
                    logger.info(f"📄 Chroma Artigo [{i}] DESCARTADO (dist > {MAX_DISTANCE_ARTIGOS})")
                    continue
                if (artigo_exato
                        and meta.get('artigo') == artigo_exato.get('artigo')
                        and meta.get('fonte') == artigo_exato.get('fonte')):
                    continue
                item = {
                    "tipo": "Artigo Legal",
                    "fonte": meta['fonte'].replace('.html', '').upper(),
                    "artigo": meta.get('artigo', 'N/A'),
                    "texto": doc,
                    "titulo": None,
                    "_distancia": distancia
                }
                item["_doc_id"] = _gerar_doc_id(item)
                candidatos_chroma.append(item)

        query_args_blocos = {"query_texts": [consulta_rag], "n_results": 10}
        if "fonte" in filtro_metadado:
            query_args_blocos["where"] = {"fonte": filtro_metadado["fonte"]}
        resultados_blocos = colecao_blocos.query(**query_args_blocos)
        if resultados_blocos and resultados_blocos['documents'] and resultados_blocos['documents'][0]:
            for i, doc in enumerate(resultados_blocos['documents'][0]):
                distancia = resultados_blocos['distances'][0][i]
                meta = resultados_blocos['metadatas'][0][i]
                logger.info(f"📚 Chroma Bloco [{i}] | dist={distancia:.4f}")
                if distancia > MAX_DISTANCE_BLOCOS:
                    continue
                item = {
                    "tipo": "Bloco Legislativo",
                    "fonte": meta['fonte'].replace('.html', '').upper(),
                    "artigo": f"{meta.get('artigo_inicial', '?')} a {meta.get('artigo_final', '?')}",
                    "texto": doc,
                    "titulo": None,
                    "_distancia": distancia
                }
                item["_doc_id"] = _gerar_doc_id(item)
                candidatos_chroma.append(item)
    except Exception as e:
        logger.error(f"⚠️ Falha na consulta Chroma: {e}")

    logger.info(f"📊 Chroma | após threshold={len(candidatos_chroma)}")

    candidatos_bm25 = []
    fonte_bm25 = filtro_metadado.get("fonte")
    corpus = _carregar_corpus_bm25(fonte=fonte_bm25)
    if corpus:
        candidatos_bm25 = rerank_bm25(
            query=consulta_rag, documentos=corpus, texto_key="texto", top_k=BM25_TOP_K
        )
        if artigo_exato:
            candidatos_bm25 = [
                d for d in candidatos_bm25
                if not (d.get('artigo') == artigo_exato.get('artigo')
                        and d.get('fonte') == artigo_exato.get('lei', artigo_exato.get('fonte', '')).replace('.html', '').upper())
            ]
        logger.info(f"📊 BM25 | corpus={len(corpus)} | resultados={len(candidatos_bm25)}")
    else:
        logger.warning("⚠️ Corpus BM25 indisponível")

    documentos_fundidos = []
    if candidatos_chroma or candidatos_bm25:
        listas_para_rrf = []
        if candidatos_chroma:
            listas_para_rrf.append(candidatos_chroma)
        if candidatos_bm25:
            listas_para_rrf.append(candidatos_bm25)
        documentos_fundidos = reciprocal_rank_fusion(
            listas=listas_para_rrf, k=60, top_k=RRF_TOP_K, id_key="_doc_id"
        )
        logger.info(f"📊 RRF | chroma={len(candidatos_chroma)} | bm25={len(candidatos_bm25)} | fundidos={len(documentos_fundidos)}")

    if not documentos_fundidos and not documentos_prioritarios:
        logger.info("🔄 RRF vazio → ativando fallback BM25 puro")
        if corpus:
            fallback = buscar_bm25_puro(query=consulta_rag, corpus=corpus, texto_key="texto", top_k=RRF_TOP_K)
            if fallback:
                documentos_fundidos = fallback
                logger.info(f"✅ Fallback BM25 | resultados={len(fallback)}")

    todos_documentos = documentos_prioritarios + documentos_fundidos
    vistos_ids = set()
    documentos_unicos = []
    for doc in todos_documentos:
        doc_id = doc.get("_doc_id") or _gerar_doc_id(doc)
        if doc_id not in vistos_ids:
            vistos_ids.add(doc_id)
            documentos_unicos.append(doc)
    todos_documentos = documentos_unicos

    if not todos_documentos:
        logger.info("❌ Contexto final: VAZIO")
        return ""

    logger.info(f"✅ Contexto final: {len(todos_documentos)} documentos")
    arts_no_contexto = [d.get('artigo') for d in todos_documentos if d.get('artigo')]
    logger.info(f"📋 Artigos no contexto: {arts_no_contexto}")

    blocos_formatados = []
    for idx, doc in enumerate(todos_documentos, start=1):
        bloco = f"Documento {idx}\n"
        bloco += f"Tipo: {doc['tipo']}\n"
        bloco += f"Fonte: {doc['fonte']}\n"
        if doc.get('artigo'):
            bloco += f"Artigo: {doc['artigo']}\n"
        if doc.get('titulo'):
            bloco += f"Título: {doc['titulo']}\n"
        bloco += f"Texto:\n{doc['texto']}"
        blocos_formatados.append(bloco)

    return "\n\n---------------------\n\n".join(blocos_formatados)

# =========================================================
# 🛡️ FILTRO DE RACIOCÍNIO
# =========================================================
def limpar_raciocinio(texto: str) -> str:
    return re.sub(r"<think>.*?(</think>|$)", "", texto, flags=re.DOTALL).strip()

# =========================================================
# GERADOR DE BOTÕES
# =========================================================
def enviar_resposta_segura(message, texto, chat_id):
    """Markdown com fallback automático para texto puro."""
    try:
        bot.reply_to(message, texto, parse_mode="Markdown", reply_markup=gerar_menu_leis(chat_id))
    except Exception as e:
        logger.warning(f"⚠️ Markdown rejeitado; reenviando sem formatação: {e}")
        bot.reply_to(message, texto, reply_markup=gerar_menu_leis(chat_id))


def gerar_menu_leis(chat_id: int) -> InlineKeyboardMarkup:
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
        logger.info(f"ℹ️ Callback antigo ignorado: {e}")
    try:
        bot.edit_message_reply_markup(
            chat_id=chat_id, message_id=call.message.message_id,
            reply_markup=gerar_menu_leis(chat_id)
        )
    except Exception as e:
        logger.warning(f"⚠️ Falha ao atualizar menu: {e}")


@bot.message_handler(commands=['start', 'menu'])
def enviar_painel(message):
    chat_id = message.chat.id
    if chat_id not in filtros_ativos:
        filtros_ativos[chat_id] = "rag_geral"
    bot.reply_to(
        message,
        "⚖️ Painel de Controle RAG - Oliveira Advocacia\n\n"
        "Selecione uma legislação ou use a 'Busca Global'.\n\n"
        "💡 Dica: Pergunte 'art. 147' para ver o texto, "
        "ou 'explique o art. 147' para uma análise jurídica.",
        parse_mode="Markdown",
        reply_markup=gerar_menu_leis(chat_id)
    )


@bot.message_handler(commands=['limpar'])
def comando_limpar(message):
    chat_id = message.chat.id
    historicos[chat_id] = []
    bot.reply_to(message, "🧹 Memória contextual limpa!")


# =========================================================
# NOVO: HANDLER /help E /ajuda
# =========================================================
@bot.message_handler(commands=['help', 'ajuda'])
def comando_help(message):
    chat_id = message.chat.id
    help_text = """
⚖️ *Bibliotecária Jurídica - IA*

*Comandos disponíveis:*
/menu - Painel de seleção de legislação
/limpar - Limpa a memória contextual
/help - Mostra esta mensagem de ajuda

*Como perguntar:*

📜 *Transcrição direta* (texto da lei):
• "art. 147"
• "artigo 335 do CPC"
• "art. 5º da CF"

📖 *Conceitos e definições:*
• "o que é tutela de urgência"
• "o que significa revelia"
• "conceito de legítima defesa"

📝 *Dissertação e análise:*
• "disserte sobre o art. 147"
• "explique o art. 335 do CPC"
• "compare os arts. 12 e 14 do CDC"
• "fale sobre a livre iniciativa"

💡 *Dicas:*
• Use o /menu para filtrar por legislação
• Seja específico: "art. 147 do CP" é melhor que "art. 147"
• O bot responde em português jurídico técnico
    """
    bot.reply_to(
        message,
        help_text,
        parse_mode="Markdown",
        reply_markup=gerar_menu_leis(chat_id)
    )


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
    logger.info(f"📨 Pergunta recebida: '{pergunta}'")

    intencao = classificar_intencao(pergunta)
    logger.info(f"🎯 Intenção classificada: {intencao}")

    artigo_exato = buscar_artigo_exato(pergunta, chat_id)

    if intencao == "LOCALIZAR" and artigo_exato:
        resposta_formatada = (
            f"📜 **{artigo_exato['lei']}**\n"
            f"**Art. {artigo_exato['artigo']}**\n\n"
            f"{artigo_exato['texto']}\n\n"
            f"_(Fonte: {artigo_exato['fonte']} | Ano: {artigo_exato['ano']})_"
        )
        enviar_resposta_segura(message, resposta_formatada, chat_id)
        return

    verbete_dicionario = None
    if colecao_dicionario:
        termo_dic = next((t for t in SINONIMOS_RAG if t in pergunta.lower()), None)
        verbete_dicionario = buscar_no_dicionario(termo_dic or pergunta, n_results=1)

    if verbete_dicionario and intencao == "CONCEITO" and not RE_BUSCA_EXATA.search(pergunta):
        resposta_direta = (
            f"📖 **{verbete_dicionario['titulo']}**\n\n"
            f"{verbete_dicionario['texto']}\n\n"
            f"_Fonte: {verbete_dicionario['fonte']}_\n"
            f"_Similaridade: {(1 - verbete_dicionario['distancia'] / 2):.0%}_"
        )
        enviar_resposta_segura(message, resposta_direta, chat_id)
        return

    status_msg = bot.reply_to(
        message, "🔎 Consultando base híbrida (Embedding + BM25 + RRF)... Aguarde."
    )
    try:
        bot.send_chat_action(chat_id, 'typing')
    except Exception:
        pass

    leis_contexto = montar_contexto(pergunta, chat_id, artigo_exato, verbete_dicionario)

    if not leis_contexto:
        try:
            bot.delete_message(chat_id, status_msg.message_id)
        except Exception:
            pass
        bot.reply_to(
            message,
            "Não encontrei base documental suficiente na base indexada.\n\n"
            "💡 Tente:\n"
            "- Especificar a lei (ex: 'art. 14 do CDC')\n"
            "- Usar o menu para selecionar uma legislação\n"
            "- Reformular a pergunta com termos jurídicos",
            reply_markup=gerar_menu_leis(chat_id)
        )
        return

    # ✅ REFATOR (Patch A completo): perfil dinâmico via montar_prompt.
    # system = identidade+políticas (fixo); user = perfil+contexto+pergunta.
    # Histórico inteligente preservado: trocas limpas no meio, contexto RAG só na última user.
    system_prompt, user_content = montar_prompt(leis_contexto, pergunta)
    mensagens = [{"role": "system", "content": system_prompt}]
    if chat_id not in historicos:
        historicos[chat_id] = []
    mensagens.extend(historicos[chat_id][-4:])
    mensagens.append({"role": "user", "content": user_content})

    try:
        texto_ia = llm_chat(mensagens=mensagens, model_key="bibliotecario", timeout=600)
        texto_ia = limpar_raciocinio(texto_ia)
        if not texto_ia:
            texto_ia = "Não encontrei base documental suficiente na base indexada."

        historicos[chat_id].append({"role": "user", "content": pergunta})
        historicos[chat_id].append({"role": "assistant", "content": texto_ia})
        if len(historicos[chat_id]) > 4:
            historicos[chat_id] = historicos[chat_id][-4:]

        try:
            bot.delete_message(chat_id, status_msg.message_id)
        except Exception:
            pass
        NL = chr(10)
        limite = 4000
        partes = []
        resto = texto_ia
        while len(resto) > limite:
            corte = resto.rfind(NL + NL, 0, limite)
            if corte < 2000:
                corte = resto.rfind(NL, 0, limite)
            if corte < 2000:
                corte = limite
            partes.append(resto[:corte].strip())
            resto = resto[corte:].strip()
        partes.append(resto)
        for i, parte in enumerate(partes):
            bot.reply_to(
                message, parte, parse_mode=None,
                reply_markup=gerar_menu_leis(chat_id) if i == len(partes) - 1 else None
            )
    except Exception as e:
        try:
            bot.delete_message(chat_id, status_msg.message_id)
        except Exception:
            pass
        bot.reply_to(
            message, f"❌ Erro na IA local: {str(e)}",
            reply_markup=gerar_menu_leis(chat_id)
        )

# =========================================================
# 🚀 PONTO DE ENTRADA
# =========================================================
if __name__ == "__main__":
    logger.info("🚀 Bot OCR Conversacional — Bibliotecário Jurídico RAG")
    logger.info("✅ REFATOR: perfil dinâmico (montar_prompt) + intent por verbo + regex multi-artigo")
    logger.info("✅ NOVOS SINÔNIMOS: injúria, difamação, calúnia, habeas corpus, legítima defesa, estado de necessidade")
    logger.info("✅ COMANDO /help adicionado")

    while True:
        try:
            bot.polling(none_stop=True, timeout=60, long_polling_timeout=60)
        except Exception as e:
            logger.warning(f"⚠️ Queda de conexão: {e}")
            logger.info("🔄 Reconectando em 5s...")
            time.sleep(5)
