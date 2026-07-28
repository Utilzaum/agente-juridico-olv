# infra/rag/bm25_reranker.py
"""
Reranker BM25 para recuperação jurídica.
✅ Tokenização simples (sem dependências pesadas)
✅ Reranking de resultados do Chroma
✅ Fallback quando o Chroma retorna vazio ou irrelevante
"""
import re
import math
from typing import List, Dict, Tuple
from collections import Counter


def _tokenizar(texto: str) -> List[str]:
    """Tokenização simples: minúsculas, remove pontuação, split por espaço."""
    texto = texto.lower()
    texto = re.sub(r"[^\w\sà-ú]", " ", texto)
    return [t for t in texto.split() if len(t) > 1]


def calcular_bm25(
    query: str,
    documentos: List[str],
    k1: float = 1.5,
    b: float = 0.75
) -> List[float]:
    """
    Calcula scores BM25 para uma query contra uma lista de documentos.
    Retorna lista de scores (mesma ordem dos documentos).
    """
    if not documentos:
        return []

    query_tokens = _tokenizar(query)
    if not query_tokens:
        return [0.0] * len(documentos)

    # Tokeniza todos os documentos
    doc_tokens_list = [_tokenizar(doc) for doc in documentos]
    doc_lengths = [len(tokens) for tokens in doc_tokens_list]
    avg_dl = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 1.0
    n_docs = len(documentos)

    # Frequência de documentos (DF)
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
            numerator = term_freq * (k1 + 1)
            denominator = term_freq + k1 * (1 - b + b * dl / avg_dl)
            score += idf * (numerator / denominator)

        scores.append(score)

    return scores


def rerank_bm25(
    query: str,
    documentos: List[Dict],
    texto_key: str = "texto",
    top_k: int = 5
) -> List[Dict]:
    """
    Reordena documentos usando BM25.
    Cada documento deve ser um dict com uma chave de texto.
    Retorna os top_k documentos reordenados.
    """
    if not documentos:
        return []

    textos = [doc.get(texto_key, "") for doc in documentos]
    scores = calcular_bm25(query, textos)

    # Anexa score e ordena
    for doc, score in zip(documentos, scores):
        doc["_bm25_score"] = score

    documentos_ordenados = sorted(
        documentos,
        key=lambda x: x.get("_bm25_score", 0.0),
        reverse=True
    )

    return documentos_ordenados[:top_k]


def buscar_bm25_puro(
    query: str,
    corpus: List[Dict],
    texto_key: str = "texto",
    top_k: int = 5
) -> List[Dict]:
    """
    Busca BM25 pura (sem Chroma).
    Usado como fallback quando o Chroma retorna vazio.
    """
    return rerank_bm25(query, corpus, texto_key, top_k)
