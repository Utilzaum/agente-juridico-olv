# ESTADO DO PROJETO — OLV (Oliveira Advocacia)
**Data:** 2026-07-26
**Propósito:** mapa fiel do disco para retomar o trabalho sem "versões fantasma".
**Método de trabalho combinado:** medir → corrigir → medir (nunca consertar no escuro).

---

## 1. O que é o projeto
Sistema jurídico com 4 frentes dentro de um mesmo repositório:
1. **Captura DJEN** — consulta API, paginação, cursor, hash, persistência.
2. **Motor jurídico** — identifica ato, calcula prazo, usa IA (LLM local).
3. **Banco / Controladoria** — publicações, eventos, cursores, auditoria (SQLite).
4. **Bibliotecário RAG** — bot Telegram que responde perguntas jurídicas usando
   ChromaDB (embedding) + dicionário jurídico + LLM local (Ollama).

**Foco atual:** frente 4 (Bibliotecário RAG). As frentes 1–3 estão funcionais,
porém com refatoração de infraestrutura desenhada e **não aplicada** (ver §5).

---

## 2. Arquitetura de pastas (estado atual)
```
agente_juridico/
├── bot_ocr_conversacional.py      # Bibliotecário RAG (bot Telegram)  ← FOCO
├── repositorio.py                 # Controladoria/DJEN (monolito original)
├── script_djen.py                 # Captura DJEN (fora do foco atual)
├── telegram_bot.py                # Bot da Controladoria (fora do foco atual)
├── diagnostico_indexacao.py       # Ferramenta: raio-X do Chroma
├── diagnostico_funil.py           # Ferramenta: mede o funil de recuperação
├── controladoria.db               # SQLite
├── db_vetorial/                   # ChromaDB (artigos + blocos + dicionário)
└── infra/
    ├── llm/
    │   ├── prompts.py             # Engenharia de prompt centralizada
    │   └── ollama_client.py       # Cliente LLM único (MODELS por agente)
    └── rag/
        └── bm25_reranker.py       # BM25 + RRF (ranking puro, sem Chroma)
```

---

## 3. Estado REAL de cada arquivo (segundo o que está no disco)

| Arquivo | Versão no disco | Status |
|---|---|---|
| `bot_ocr_conversacional.py` | Usa `llm_chat` + formato "Documentos Recuperados" + histórico inteligente | ✅ ATIVO. **Mas:** regex com bug (sem `*`), expansão por **substituição**, Chroma 3+2 **sem** threshold, **sem** BM25/RRF, **sem** Camada A |
| `infra/llm/ollama_client.py` | Versão com `_limpar_resposta` robusta (regex `(<\/think>…|$)`), `MODELS` dict, `gerar()`+`chat()` | ✅ ATIVO. ⚠️ **INCONSISTÊNCIA:** `MODELS` ainda aponta `LFM2.5-1.2B-Thinking` (ver §6) |
| `infra/llm/prompts.py` | Existe (é importado pelo bot e pelo client) | ⚠️ Versão com "RESPOSTA PARCIAL" **a confirmar** |
| `infra/rag/bm25_reranker.py` | Versão **genérica** (`top_k=5`, sem boost, sem enriquecimento de metadado) | ⚠️ Existe mas está **ÓRFÃO**: o bot ativo **não o importa** em nenhum lugar (código morto) |
| `repositorio.py` | Monolito original (~420 linhas, funções soltas, sem dataclasses/Transaction) | ✅ Funcional. Sprint 1 de infraestrutura **não aplicada** |
| `qwen_client.py` | Cliente legado (prompt inline, `MODEL` hardcoded) | ❌ LEGADO — não é importado pelo bot ativo; pode ser removido |

> **Nota importante:** em uma conversa anterior, um `diagnostico_funil.py` mostrou
> logs de `📊 BM25` e `📊 RRF`, o que indica que **em algum momento** o bot teve uma
> versão com RRF/Camada A. A KB atual mostra o bot **sem** isso. Há, portanto, uma
> **discrepância de versão** que os comandos do §7 resolvem.

---

## 4. O que JÁ foi validado (com evidência, não palpite)
- ✅ **Indexação Chroma correta:** `art. 12` do CDC encontrado via `get(where={artigo,fonte})`.
  Metadado `artigo` salvo como string pura (`"12"`), `fonte` como `"cdc.html"`.
- ✅ **Busca exata por metadado funciona** (e é rápida).
- ❌ **Embedding MiniLM é fraco para jurídico:** "art. 12 CDC" retorna CLT/CP;
  "responsabilidade civil fornecedor" **não** recupera art. 12/14. Distâncias reais 0.27–0.49.
- ❌ **LFM2.5-1.2B-Thinking não suporta português** (idiomas oficiais: EN/AR/ZH/FR/DE/JA/KO/ES).
  Causa raiz de respostas ruins + vazamento de raciocínio.
- ✅ **Qwen2.5:3b-instruct responde bem em PT** (teste prático do Senior).
- ✅ **O "Não encontrei base documental" vinha do LLM** (prompt restritivo + art. 12 ausente
  do contexto), **não** de contexto vazio — o contexto tinha 6 docs.

---

## 5. O que está DESENHADO mas NÃO aplicado no disco
(itens prontos em conversa, aguardando aplicação)

**Bibliotecário RAG:**
1. **Camada A** — `extrair_artigos_mencionados()` + `buscar_artigos_por_metadado()`:
   artigos citados na pergunta entram no contexto via `get(where=...)`, garantidos,
   antes do ranking. *(Resolve "peço 2 artigos e só volta 1".)*
2. **Hybrid Legal Retriever** no `bm25_reranker.py` — enriquecimento do texto com
   metadados + `METADATA_BOOST` para artigo citado + `top_k=20` (rerank) / `8` (RRF).
3. **Integração** do `bm25_reranker` ao `montar_contexto` (Chroma top15 + BM25 top15 → RRF top5).
4. **Regex corrigida:** `(\d+[A-Za-zº.-]*)` com `*` + `\s*` opcional.
5. **Expansão por concatenação:** `consulta_rag = f"{pergunta} {expandido}"` (não substituição).
6. **Prompt com RESPOSTA PARCIAL** (responde o que tem + indica lacunas; só nega se não houver nada).
7. **Thresholds** baseados em dados reais (artigos 0.55 / blocos 0.60 / dicionário 0.50).

**Controladoria/DJEN (Sprint 1 — frente separada):**
8. `infra/repository/` com `models.py` (dataclasses), `connection.py` (Transaction),
   `publicacoes.py`, `eventos.py`, `cursores.py`, `auditoria.py`, `pipeline.py`.
   `repositorio.py` viraria facade. **Não iniciado no disco.**

---

## 6. Inconsistências a confirmar (perguntas abertas)
1. Qual `bot_ocr_conversacional.py` está na pasta: o ativo (`llm_chat`) ou o legado (`requests`)?
2. A troca de modelo para **qwen2.5:3b** foi salva em `infra/llm/ollama_client.py`?
   (A KB ainda mostra LFM2.5 no `MODELS`.)
3. O `infra/llm/prompts.py` tem o bloco **RESPOSTA PARCIAL**?
4. O bot ativo chegou a ter RRF/Camada A em algum momento (e foi revertido), ou nunca teve?

---

## 7. Como confirmar o estado real (5 comandos, 10 segundos)
Rode na raiz do projeto. A saída responde todas as perguntas do §6:
```bash
grep -c "llm_chat" bot_ocr_conversacional.py
#  >0 = bot ativo (centralizado) | 0 = bot legado (requests)

grep -cE "reciprocal_rank_fusion|extrair_artigos_mencionados" bot_ocr_conversacional.py
#  >0 = tem RRF/Camada A | 0 = não tem

grep "bibliotecario" infra/llm/ollama_client.py
#  mostra qual modelo está configurado (LFM2.5 ou qwen2.5:3b)

grep -cE "METADATA_BOOST|_texto_enriquecido" infra/rag/bm25_reranker.py
#  >0 = Hybrid aplicado | 0 = genérico (top_k=5)

grep -c "RESPOSTA PARCIAL" infra/llm/prompts.py
#  >0 = resposta parcial aplicada | 0 = não tem
```

---

## 8. Modelos disponíveis no PC (Ollama)
| Modelo | Tam. | PT | Uso recomendado |
|---|---|---|---|
| `qwen2.5:3b-instruct-q4_K_M` | 1.9G | ✅ | **Bibliotecário (atual, validado)** |
| `qwen2.5:7b-instruct-q4_K_M` | 4.7G | ✅ | Upgrade natural / base do Jurema |
| `gemma4:e2b` | 7.2G | ⚠️ (E2B multilíngue fraco) | Testar com cautela |
| `qwen3.5:0.8b` / `qwen2.5:7b` | — | ✅ | Secundários |
| `LFM2.5-1.2B-Thinking` | 730M | ❌ | **Aposentar** do Bibliotecário |

**Próximo modelo a testar:** `Jurema-7B` (fine-tune do Qwen2.5-7B em direito brasileiro,
passou no exame da OAB) — baixar e fazer A/B contra Qwen.

---

## 9. Roadmap (ordem de prioridade)
1. **Confirmar** o estado real via §7 (1 min).
2. **Aplicar** no bot ativo: Camada A + regex corrigida + expansão por concatenação.
3. **Aplicar** o Hybrid no `bm25_reranker.py` **e integrá-lo** ao `montar_contexto`.
4. **Aplicar** prompt com RESPOSTA PARCIAL + thresholds.
5. **Medir** com `diagnostico_funil.py`: confirmar que art. 12 **e** 14 aparecem no contexto.
6. **A/B de modelos** (Qwen3B × Qwen7B × Jurema) com a mesma pergunta jurídica.
7. *(frente separada)* Iniciar Sprint 1 do repositório (Controladoria/DJEN).

---

## 10. Decisões de arquitetura já tomadas (NÃO rediscutir)
- Prompts centralizados em `infra/llm/prompts.py` (nenhum prompt inline em handler).
- Cliente LLM único em `infra/llm/ollama_client.py`, com `MODELS` por agente.
- `bm25_reranker.py` é **puro** (não sabe de Chroma); a orquestração
  "metadado primeiro, BM25 depois" vive no bot.
- Histórico inteligente: contexto RAG apenas na **última** mensagem; histórico anterior limpo.
- Busca de artigo citado é **estruturada** (`get` por metadado), não por embedding.
- Método: **medir → corrigir → medir**. Diagnóstico antes de refatorar.
