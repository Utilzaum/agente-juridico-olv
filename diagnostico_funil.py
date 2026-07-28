# diagnostico_funil.py
"""
Instrumento de MEDIÇÃO — verifica se Art. 12 e Art. 14 aparecem no contexto final.
Rode: python diagnostico_funil.py
"""
import bot_ocr_conversacional as B

PERGUNTA = ("Disserte sobre a responsabilidade civil considerando o CDC, "
            "principalmente os artigos 14 e 12")
CHAT_ID = 999999
ARTIGOS_ALVO = {"12", "14"}
SEP = "=" * 64


def linha(titulo):
    print("\n" + SEP)
    print(titulo)
    print(SEP)


def main():
    linha("0. SANITY CHECK")
    if B.colecao_artigos is None:
        print("❌ Chroma indisponível. Abortando.")
        return
    print(f"✅ Chroma conectado. Pergunta: {PERGUNTA!r}")

    B.filtros_ativos[CHAT_ID] = "rag_geral"

    linha("1. INTENÇÃO")
    intencao = B.classificar_intencao(PERGUNTA)
    print(f"    intenção = {intencao}")

    linha("2. BUSCA EXATA (regex)")
    art_exato = B.buscar_artigo_exato(PERGUNTA, CHAT_ID)
    print(f"    artigo_exato = {art_exato}")

    linha("3. ARTIGOS NOMEADOS (✅ Correção 1)")
    artigos_mencionados = B.extrair_artigos_mencionados(PERGUNTA)
    print(f"    artigos extraídos = {artigos_mencionados}")
    fonte_meta = "cdc.html"  # detectado pelo filtro
    docs_metadado = B.buscar_artigos_por_metadado(artigos_mencionados, fonte_meta)
    print(f"    docs encontrados por metadado = {len(docs_metadado)}")
    for d in docs_metadado:
        print(f"      → art. {d['artigo']} | fonte={d['fonte']}")

    linha("4. EXPANSÃO DE QUERY (✅ Correção 4)")
    consulta = PERGUNTA
    for termo, expandido in B.SINONIMOS_RAG.items():
        if termo in PERGUNTA.lower():
            consulta = f"{PERGUNTA} {expandido}"
            print(f"    termo casado: {termo!r}")
            print(f"    query concatenada: {consulta[:120]}...")
            break
    preservou = ("12" in consulta) and ("14" in consulta)
    print(f"    ⚠️ artigos 12/14 preservados na query? {preservou}")

    linha("5. DICIONÁRIO")
    verb = B.buscar_no_dicionario(PERGUNTA, n_results=1)
    print(f"    verbete = {verb['titulo'] if verb else None}")

    linha("6. CONTEXTO FINAL (montar_contexto REAL)")
    ctx = B.montar_contexto(PERGUNTA, CHAT_ID, art_exato, verb)
    n_docs = ctx.count("Documento ") if ctx else 0
    print(f"    tamanho: {len(ctx)} chars | blocos: {n_docs}")
    print(f"    está VAZIO? {not ctx or ctx.strip() == ''}")

    # ✅ Verificação explícita: Art. 12 e Art. 14 estão no contexto?
    linha("7. VERIFICAÇÃO DOS ARTIGOS ALVO")
    for art in sorted(ARTIGOS_ALVO):
        # Procura por "Artigo: 12" ou "Artigo: 14" no contexto formatado
        presente = f"Artigo: {art}\n" in ctx or f"Artigo: {art} " in ctx
        status = "✅ PRESENTE" if presente else "❌ AUSENTE"
        print(f"    Art. {art}: {status}")

    linha("8. PREVIEW DO CONTEXTO (600 chars)")
    print((ctx or "(vazio)")[:600])

    linha("9. VEREDITO")
    arts_faltando = [a for a in ARTIGOS_ALVO if f"Artigo: {a}\n" not in ctx and f"Artigo: {a} " not in ctx]
    if not arts_faltando:
        print("    ✅ TODOS os artigos alvo (12 e 14) estão no contexto!")
        print("    ✅ O LLM agora tem base para responder parcialmente.")
    else:
        print(f"    ❌ Artigos AUSENTES do contexto: {arts_faltando}")
        print("    ⚠️ Verificar logs acima para identificar a etapa que falhou.")


if __name__ == "__main__":
    main()
