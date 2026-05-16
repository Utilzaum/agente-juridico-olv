# ⚖️ Agente Jurídico Automatizado

Plataforma modular de automação jurídica desenvolvida em Python, com IA local via Ollama + Qwen, OCR local e integração via Telegram.

O sistema foi projetado para auxiliar escritórios de advocacia na automação operacional de documentos, triagem de informações, organização de fluxos jurídicos e geração assistida de peças e documentos.

A arquitetura prioriza:

* privacidade de dados
* operação local/offline
* modularização
* produtividade jurídica
* controle interno de informações sensíveis

---

# 📌 Visão Geral

O projeto permite transformar documentos enviados pelo cliente (PDF ou imagem) em documentos jurídicos estruturados, utilizando:

* OCR local
* IA local para interpretação de dados
* templates jurídicos padronizados
* automação de fluxo via Telegram

O sistema foi projetado para operação assistida, mantendo validação humana antes da geração final dos documentos.

---

# 🚀 Funcionalidades

* Recebimento de documentos via Telegram
* OCR local com Tesseract
* Interpretação jurídica via IA local (Qwen/Ollama)
* Complementação e validação via regex
* Interface interativa para conferência de dados
* Geração automatizada de:

  * Procuração
  * Declaração de hipossuficiência
  * Contrato de honorários
  * Documentos personalizados
* Organização modular por agentes
* Sistema preparado para expansão via orquestrador

---

# 🧠 Arquitetura

```text
agente_juridico/
│
├── core/                    # Núcleo principal
│   ├── bot.py
│   ├── bot_ocr.py
│   ├── parser_juridico.py
│   ├── ia_juridica.py
│   └── prazo.py
│
├── orchestrator/            # Orquestração modular
│   ├── dispatcher.py
│   ├── router.py
│   ├── api.py
│   └── process_manager.py
│
├── services/                # Serviços auxiliares
│   ├── templates/
│   └── modelos jurídicos
│
├── infra/                   # Infraestrutura e suporte
├── core_offline/            # Execução offline/local
├── logs/                    # Logs
├── temp/                    # Arquivos temporários
├── exports/                 # Exportações
│
├── telegram_bot.py
├── dashboard.py
├── qwen_client.py
├── utils.py
│
├── start_main.sh
├── start_all.sh
├── start_email.sh
│
└── .env (NÃO versionado)
```

---

# 🧠 IA Local (Arquitetura Principal)

O sistema opera prioritariamente com IA local utilizando:

* Ollama
* Qwen
* Gemma (suporte opcional)

A inferência principal ocorre localmente, sem envio automático de documentos para APIs externas.

Modelo atualmente utilizado:

```env
OLLAMA_MODEL=qwen2.5:7b-instruct-q4_K_M
```

---

# 🔐 Privacidade e LGPD

O sistema foi projetado para operação prioritariamente local/offline.

A arquitetura busca reduzir exposição de documentos sensíveis e aumentar o controle interno de dados jurídicos.

Tecnologias locais utilizadas:

* Ollama
* Qwen
* Tesseract OCR

A integração com APIs externas (como DeepSeek) é opcional e utilizada apenas como fallback contingencial.

Por padrão, a operação principal pode ocorrer integralmente local.

Essa arquitetura prioriza:

* sigilo profissional
* privacidade documental
* controle interno de dados
* redução de transferência externa de informações
* adequação operacional à LGPD

⚠️ O uso adequado do sistema e a conformidade jurídica dependem da configuração e operação realizadas pelo usuário.

---

# ⚙️ Requisitos

* Python 3.10+
* Ollama instalado
* Tesseract OCR
* Linux recomendado

---

# 📦 Instalação

## Dependências Python

```bash
pip install -r requirements.txt
```

---

# 🔍 OCR (Tesseract)

## Linux

```bash
sudo apt install tesseract-ocr
sudo apt install tesseract-ocr-por
```

## Windows

Download:
https://github.com/UB-Mannheim/tesseract/wiki

Configuração opcional:

```env
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

---

# 🧠 Instalação do Ollama

Instalar:
https://ollama.com

Baixar modelo:

```bash
ollama pull qwen2.5:7b-instruct-q4_K_M
```

Executar Ollama:

```bash
ollama serve
```

---

# 🔐 Configuração (.env)

Criar arquivo `.env` na raiz do projeto:

```env
# =========================
# BOT PRINCIPAL
# =========================
TELEGRAM_BOT_TOKEN=SEU_TOKEN

# =========================
# IA LOCAL
# =========================
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b-instruct-q4_K_M
OLLAMA_TIMEOUT=180

# =========================
# OCR
# =========================
OCR_LANG=por+eng

# =========================
# FALLBACK EXTERNO (OPCIONAL)
# =========================
ALLOW_EXTERNAL_FALLBACK=false
DEEPSEEK_API_KEY=SUA_API_KEY
```

⚠️ Nunca versionar este arquivo.

⚠️ Nunca publicar tokens, APIs ou credenciais reais.

---

# ▶️ Execução

## Bot principal

```bash
python -m core.bot
```

Ou:

```bash
bash start_main.sh
```

---

# 📬 Bot de Publicações (DJEN / Email)

O sistema possui um serviço complementar para captura automatizada de publicações jurídicas.

## Funcionalidades

* Consulta automática de publicações
* Processamento estruturado
* Envio automatizado por e-mail
* Organização de arquivos temporários

## Componentes

```text
bot_email.py
script_djen.py
temp_email/
```

## Execução

```bash
python bot_email.py
```

Ou:

```bash
bash start_email.sh
```

---

# 🔄 Fluxo de Uso

1. Cliente envia documento
2. OCR local extrai informações
3. IA interpreta os dados
4. Sistema apresenta conferência
5. Usuário corrige dados (se necessário)
6. Geração automatizada dos documentos

---

# ⚠️ Limitações Conhecidas

* Dependência da qualidade do OCR
* Possibilidade de inconsistência em documentos muito degradados
* Persistência parcial de estados em memória
* Necessidade de validação humana

---

# 🛠 Recomendações Operacionais

* Utilizar `/limpar` antes de novo atendimento
* Validar dados antes da geração final
* Não reutilizar documentos temporários
* Manter backups criptografados
* Separar dados sensíveis do código

---

# 💾 Backup e Recuperação

Estratégia recomendada:

1. GitHub privado → versionamento do código
2. Backup criptografado → nuvem
3. Backup offline → HD externo

## Exemplo

```bash
tar -czf backup.tar.gz .
gpg -c backup.tar.gz
```

---

# 🧪 Testes

## OCR

```bash
python -m core.bot_ocr arquivo.pdf
```

---

# ❌ Erros Comuns

## OCR não funciona

Verificar instalação do Tesseract.

## Ollama não responde

Verificar:

```bash
ollama serve
```

## Modelo não encontrado

Executar:

```bash
ollama pull qwen2.5:7b-instruct-q4_K_M
```

## Bot não inicia

Verificar `.env`.

---

# 📦 Portabilidade

Para mover o sistema:

1. Copiar projeto
2. NÃO copiar `.env`
3. Recriar `.env`
4. Instalar dependências
5. Instalar Ollama
6. Instalar Tesseract
7. Executar

---

# 📊 Status do Projeto

* Em desenvolvimento
* Arquitetura modular em evolução
* Orquestrador em expansão
* Uso assistido recomendado
* Foco em automação jurídica local

---

# 👤 Autor

Raphael Vitor Aragão de Oliveira

