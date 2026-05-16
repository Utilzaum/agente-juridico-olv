# ⚖️ Agente Jurídico Automatizado

Sistema modular para automação de geração de documentos jurídicos a partir de OCR e interação via Telegram.

---

## 📌 Visão Geral

O projeto permite transformar documentos enviados pelo cliente (PDF ou imagem) em documentos jurídicos estruturados, utilizando:

* OCR (extração de texto)
* IA para interpretação de dados
* Templates jurídicos padronizados

O sistema foi projetado para operação assistida, com validação humana antes da geração final.

---

## 🚀 Funcionalidades

* Recebimento de documentos via Telegram
* Extração de texto (OCR)
* Interpretação de dados com IA (DeepSeek)
* Complementação via regex
* Interface interativa para correção de dados
* Geração automática de:

  * Procuração
  * Declaração de hipossuficiência
  * Contrato de honorários

---

## 🧠 Arquitetura

```
agente_juridico/
│
├── core/                # Lógica principal dos bots
│   ├── bot.py
│   ├── bot_ocr.py
│   ├── bot_conversa.py
│
├── services/            # Serviços auxiliares
│   ├── templates/
│   ├── parser_dados.py
│
├── data/                # (NÃO versionado) dados sensíveis
│   ├── clientes/
│   ├── documentos/
│
├── temp/                # arquivos temporários
├── logs/                # logs de execução
│
├── requirements.txt
├── start_main.sh
├── start_all.sh
└── .env (NÃO versionado)
```

---

## ⚙️ Requisitos

* Python 3.10+
* Tesseract OCR (obrigatório)

### Instalação de dependências

```
pip install -r requirements.txt
```

---

## 🔍 OCR (Dependência Crítica)

### Linux

```
sudo apt install tesseract-ocr
sudo apt install tesseract-ocr-por
```

### Windows

Download:
https://github.com/UB-Mannheim/tesseract/wiki

Configuração opcional no `.env`:

```
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

---

## 🔐 Configuração (.env)

Criar arquivo `.env` na raiz:

```
TELEGRAM_BOT_TOKEN=SEU_TOKEN
DEEPSEEK_API_KEY=SUA_API_KEY
OCR_LANG=por+eng
```

⚠️ Nunca versionar este arquivo.

---

## ▶️ Execução

```
python -m core.bot
```

Ou via script:

```
bash start_main.sh
```

---

## 🔄 Fluxo de Uso

1. Envio de documento (PDF ou imagem)
2. OCR e extração de dados
3. Apresentação para conferência
4. Correção manual (se necessário)
5. Comando `/kit`
6. Geração automática dos documentos

---

## ⚠️ Limitações Conhecidas

Persistência indevida de dados em memória:

* Dados podem ser reutilizados entre execuções
* Campo "nome" pode apresentar inconsistência

### Causa técnica

* Cache por `chat_id`
* Sobrescrita parcial de estados
* Dependência combinada de OCR + IA

---

## 🛠 Soluções Temporárias

* Corrigir manualmente os dados no fluxo
* Utilizar `/limpar` antes de novo atendimento
* Reenviar documento com dados completos

---

## 🔐 Segurança e LGPD

Este sistema pode manipular dados pessoais sensíveis.

Boas práticas obrigatórias:

* Nunca subir `.env` para repositórios
* Não versionar dados reais de clientes
* Utilizar criptografia em backups
* Separar dados e código

Estrutura recomendada:

```
/data        → dados sensíveis (fora do Git)
/core        → código
/services    → lógica auxiliar
```

---

## 💾 Backup e Recuperação

Estratégia recomendada:

1. GitHub (privado) → versionamento do código
2. Backup criptografado → armazenamento em nuvem
3. Backup offline → HD externo

### Exemplo de backup seguro

```
tar -czf backup.tar.gz .
gpg -c backup.tar.gz
```

---

## 🧪 Testes

Testar OCR diretamente:

```
python -m core.bot_ocr arquivo.pdf
```

---

## ❌ Erros Comuns

* OCR não funciona
  → verificar instalação do Tesseract

* Bot não inicia
  → verificar `.env`

* Templates não encontrados
  → conferir pasta `services/templates/`

---

## 📦 Portabilidade

Para mover o sistema:

1. Copiar o projeto (sem `.env`)
2. Recriar `.env` no destino
3. Instalar dependências
4. Instalar Tesseract
5. Executar

---

## 📊 Status do Projeto

* Em desenvolvimento
* Uso assistido recomendado
* Arquitetura em evolução (orquestrador em fase inicial)

---

## 👤 Autor

Raphael Vitor Aragão de Oliveira

---

---

## 📬 Bot de Publicações (DJEN / Email)

O sistema possui um serviço complementar responsável pela captura e envio automatizado de publicações jurídicas.

### Funcionalidades

* Consulta automática de publicações (DJEN)
* Processamento dos dados retornados
* Envio estruturado por e-mail
* Organização de arquivos temporários

### Componentes

```id="2e1r8v"
bot_email.py        # Bot responsável pelo envio
script_djen.py      # Consulta e processamento das publicações
temp_email/         # Armazenamento temporário
```

### Execução

```id="9z7l2x"
python bot_email.py
```

Ou via script:

```id="5y3k1a"
bash start_email.sh
```

### Observações

* Este serviço opera de forma independente do bot principal
* Pode ser integrado ao futuro orquestrador
* Requer configuração de credenciais de e-mail/API

---

