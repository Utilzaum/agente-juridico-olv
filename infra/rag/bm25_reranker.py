# infra/rag/bm25_reranker.py
"""
Hybrid Legal Retriever — BM25 + Reciprocal Rank Fusion (RRF)
============================================================
Evolução do BM25 genérico para RAG jurídico.

O que este módulo FAZ (ranking puro, sem saber de Chroma/DB):
  - BM25 correto (matemática inalterada).
  - Enriquece o texto rankeado com os METADADOS do doc (tipo/fonte/artigo),
    porque no jurídico "art. 12 cdc" é consulta estruturada, não só textual.
  - Boost aditivo para artigos EXPLICITAMENTE citados na query,
    garantindo que eles subam no ranking BM25 e entrem no RRF.
  - top_k ampliado (default 20 no rerank, 8 no RRF).

O que este módulo NÃO faz (por design — separação de responsabilidades):
  - Não acessa o Chroma. A orquestração "metadado PRIMEIRO (get por where),
    BM25 DEPOIS (complemento)" vive no bot, que é quem tem a conexão.
    Este módulo só recebe uma lista de dicts já pronta e a rankeia.
"""
import re
import math
from typing import List, Dict
from collections import Counter

# =========================================================
# CONSTANTES (nada de número mágico espalhado)
# =========================================================
DEFAULT_TOP_K = 20          # ✅ Ponto 1: era 5
RRF_DEFAULT_TOP_K = 8       # ✅ Ponto 1: era 5
METADATA_BOOST = 50.0       # ✅ Ponto 2: vence scores BM25 típicos; RRF lê rank
RRF_K = 60                  # constante clássica do RRF


# =========================================================
# TOKENIZAÇÃO
# =========================================================
def _tokenizar(texto: str) -> List[str]:
    texto = texto.lower()
    texto = re.sub(r"[^\w\sà-ú]", " ", texto)
    return [t for t in texto.split() if len(t) > 1]


# =========================================================
# ✅ PONTO 3: enriquece o texto com metadados antes de rankear
# =========================================================
def _texto_enriquecido(doc: Dict, texto_key: str = "texto") -> str:
    """
    Concatena metadados ao corpo para o BM25 tratá-los como tokens.
    Assim 'artigo 12 cdc' vira texto rankeável, não só o corpo da lei.
    """
    partes = [
        str(doc.get("tipo", "")),
        str(doc.get("fonte", "")),
        "artigo", str(doc.get("artigo", "")),   # 'artigo 12' como bigrama útil
        str(doc.get("lei", "")),
        str(doc.get(texto_key, "")),
    ]
    return " ".join(p for p in partes if p)


# =========================================================
# ✅ PONTO 2: extrai os artigos CITADOS na query
# =========================================================
def _artigos_na_query(query: str) -> set:
    """
    Heurística: pega os números que vêm depois de art/artigo/artigos,
    cobrindo 'art. 12', 'artigos 14 e 12', 'art. 12 e 14 do CDC'.
    Retorna set de strings ('12', '14', '335-A', '5º'...).
    """
    nums = set()
    blocos = re.findall(
        r"art(?:igo)?s?\.?\s*([0-9][0-9A-Za-zº.\-, e]*[0-9A-Za-zº])",
        query, re.IGNORECASE
    )
    for bloco in blocos:
        nums.update(re.findall(r"\d+[A-Za-zº.\-]*", bloco))
    return nums


# =========================================================
# BM25 (matemática inalterada — estava 9,5/10)
# =========================================================
def calcular_bm25(
    query: str,
    documentos: List[str],
    k1: float = 1.5,
    b: float = 0.75,
) -> List[float]:
    if not documentos:
        return []

    query_tokens = _tokenizar(query)
    if not query_tokens:
        return [0.0] * len(documentos)

    doc_tokens_list = [_tokenizar(doc) for doc in documentos]
    doc_lengths = [len(t) for t in doc_tokens_list]
    avg_dl = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 1.0
    n_docs = len(documentos)

    df = Counter()
    for tokens in doc_tokens_list:
        df.update(set(tokens))

    scores = []
    for i, tokens in enumerate(doc_tokens_list):
        tf = Counter(tokens)
        score = 0.0
        dl = doc_lengths[i]
        for term in query_tokens:
            if term not in tf:
                continue
            term_freq = tf[term]
            doc_freq = df.get(term, 0)
            idf = math.log((n_docs - doc_freq + 0.5) / (doc_freq + 0.5) + 1.0)
            num = term_freq * (k1 + 1)
            den = term_freq + k1 * (1 - b + b * dl / avg_dl)
            score += idf * (num / den)
        scores.append(score)
    return scores


# =========================================================
# RERANK (✅ enriquecimento + boost + top_k maior)
# =========================================================
def rerank_bm25(
    query: str,
    documentos: List[Dict],
    texto_key: str = "texto",
    top_k: int = DEFAULT_TOP_K,
) -> List[Dict]:
    if not documentos:
        return []

    # ✅ Ponto 3: BM25 sobre texto ENRIQUECIDO com metadados
    textos = [_texto_enriquecido(d, texto_key) for d in documentos]
    scores = calcular_bm25(query, textos)

    # ✅ Ponto 2: boost para artigo citado na query
    arts_query = _artigos_na_query(query)
    for doc, sc in zip(documentos, scores):
        citado = str(doc.get("artigo", "")) in arts_query
        doc["_bm25_score"] = sc + (METADATA_BOOST if citado else 0.0)

    ordenados = sorted(
        documentos,
        key=lambda x: x.get("_bm25_score", 0.0),
        reverse=True,
    )
    return ordenados[:top_k]


def buscar_bm25_puro(
    query: str,
    corpus: List[Dict],
    texto_key: str = "texto",
    top_k: int = DEFAULT_TOP_K,
) -> List[Dict]:
    """Busca BM25 sobre um corpus inteiro (fallback / co-primary)."""
    return rerank_bm25(query, corpus, texto_key, top_k)


# =========================================================
# RRF (✅ top_k maior; lê RANK, por isso o boost acima funciona)
# =========================================================
def reciprocal_rank_fusion(
    listas: List[List[Dict]],
    k: int = RRF_K,
    top_k: int = RRF_DEFAULT_TOP_K,
    id_key: str = "_doc_id",
) -> List[Dict]:
    """
    Funde rankings por posição: score = soma(1/(k+rank)).
    Como usa RANK, o METADATA_BOOST do BM25 cumpre seu papel:
    empurra o artigo citado pro topo da lista BM25 → ele entra na fusão.
    """
    scores: Dict[str, float] = {}
    docs_map: Dict[str, Dict] = {}
    for lista in listas:
        for rank, doc in enumerate(lista, start=1):
            doc_id = doc.get(id_key)
            if doc_id is None:
                continue
            scores[doc_id] = scores.get(doc_id, 0.0) + (1.0 / (k + rank))
            docs_map[doc_id] = doc

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    resultados = []
    for doc_id, score in ranked[:top_k]:
        doc = docs_map[doc_id]
        doc["_rrf_score"] = score
        resultados.append(doc)
    return resultados
