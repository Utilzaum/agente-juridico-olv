from sentence_transformers import CrossEncoder
import os

# =========================================================
# ⚙️ CONFIGURAÇÕES
# =========================================================
CROSS_ENCODER_MODEL = os.getenv(
    "CROSS_ENCODER_MODEL",
    "cross-encoder/ms-marco-MiniLM-L-6-v2"
)

# Cache do modelo (carrega uma vez)
_model_cache = None


# =========================================================
# 🧠 CARREGAMENTO DO MODELO
# =========================================================

def obter_cross_encoder():
    """Carrega modelo CrossEncoder com cache"""
    global _model_cache
    
    if _model_cache is None:
        print(f" Carregando CrossEncoder: {CROSS_ENCODER_MODEL}")
        _model_cache = CrossEncoder(CROSS_ENCODER_MODEL)
        print("✅ CrossEncoder carregado")
    
    return _model_cache


# =========================================================
#  RERANKING
# =========================================================

def rerank(pergunta, candidatos, top_k=5):
    """
    Reranka candidatos usando CrossEncoder
    
    Args:
        pergunta: query do usuário
        candidatos: lista de dicts com chave "texto"
        top_k: número de resultados finais
    
    Returns:
        Lista ordenada de candidatos (top_k)
    """
    if not candidatos:
        return []
    
    # Carrega modelo
    model = obter_cross_encoder()
    
    # Prepara pares (query, documento)
    pares = [(pergunta, cand["texto"]) for cand in candidatos]
    
    # Calcula scores
    scores = model.predict(pares)
    
    # Adiciona scores aos candidatos
    for i, cand in enumerate(candidatos):
        cand["score_cross_encoder"] = float(scores[i])
    
    # Ordena por score (maior primeiro)
    candidatos_ordenados = sorted(
        candidatos,
        key=lambda x: x["score_cross_encoder"],
        reverse=True
    )
    
    # Retorna top_k
    return candidatos_ordenados[:top_k]


# =========================================================
# 🔍 RERANK COM FILTRO DE FONTE
# =========================================================

def rerank_com_filtro(pergunta, candidatos, top_k=5, filtro_fonte=None):
    """
    Reranking com filtro opcional de fonte
    """
    # Aplica filtro se especificado
    if filtro_fonte:
        candidatos_filtrados = [
            c for c in candidatos 
            if c.get("fonte") == filtro_fonte
        ]
    else:
        candidatos_filtrados = candidatos
    
    # Reranka
    return rerank(pergunta, candidatos_filtrados, top_k)


# =========================================================
#  TESTE
# =========================================================

if __name__ == "__main__":
    # Teste rápido
    candidatos_teste = [
        {
            "id": "CC_186",
            "texto": "Art. 186. Aquele que, por ação ou omissão voluntária, negligência ou imprudência, violar direito e causar dano a outrem, ainda que exclusivamente moral, comete ato ilícito.",
            "fonte": "cc.html",
            "score_bm25": 15.2
        },
        {
            "id": "CC_187",
            "texto": "Art. 187. Também comete ato ilícito o titular de um direito que, ao exercê-lo, excede manifestamente os limites impostos pelo seu fim econômico ou social, pela boa-fé ou pelos bons costumes.",
            "fonte": "cc.html",
            "score_bm25": 12.8
        },
        {
            "id": "CC_927",
            "texto": "Art. 927. Aquele que, por ato ilícito (arts. 186 e 187), causar dano a outrem, fica obrigado a repará-lo.",
            "fonte": "cc.html",
            "score_bm25": 10.5
        }
    ]
    
    pergunta = "o que é ato ilícito no código civil"
    
    print(f"🔍 Pergunta: {pergunta}\n")
    print(f"📊 Candidatos antes do reranking: {len(candidatos_teste)}")
    
    melhores = rerank(pergunta, candidatos_teste, top_k=2)
    
    print(f"\n🏆 Top {len(melhores)} após reranking:")
    for i, cand in enumerate(melhores, 1):
        print(f"  {i}. {cand['id']} (score: {cand['score_cross_encoder']:.4f})")
        print(f"     {cand['texto'][:80]}...")
