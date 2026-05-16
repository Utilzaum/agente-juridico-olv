# ⚖️ Agente Jurídico Automatizado — Guia para Windows

Este guia descreve como instalar e executar o sistema no ambiente Windows.

---

## 📌 Visão Geral

O sistema permite:

* Receber documentos via Telegram
* Extrair texto com OCR
* Processar dados com IA
* Gerar documentos jurídicos automaticamente

Inclui também:

* Bot de geração de documentos
* Bot de envio de publicações por e-mail

---

## ⚙️ Requisitos

* Windows 10 ou superior
* Python 3.10+
* Git (opcional, recomendado)

---

## 🐍 Instalação do Python

Baixar:
https://www.python.org/downloads/

⚠️ Durante a instalação:

* Marcar **"Add Python to PATH"**

---

## 📦 Clonar ou copiar o projeto

Via Git:

```bash
git clone https://github.com/SEU_USUARIO/agente_juridico.git
cd agente_juridico
```

Ou copiar a pasta manualmente.

---

## 🧪 Criar ambiente virtual

```bash
python -m venv venv
venv\Scripts\activate
```

---

## 📦 Instalar dependências

```bash
pip install -r requirements.txt
```

---

## 🔍 Instalar OCR (OBRIGATÓRIO)

Instalar o Tesseract OCR:

https://github.com/UB-Mannheim/tesseract/wiki

Durante a instalação:

* Selecionar idioma **Português (por)**

---

## ⚠️ Configurar Tesseract

Criar ou editar `.env`:

```bash
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

---

## 📄 Suporte a PDF (Poppler)

Baixar:
https://github.com/oschwartz10612/poppler-windows/releases/

Passos:

1. Extrair o arquivo
2. Copiar o caminho da pasta `bin`
3. Adicionar ao PATH do Windows

Exemplo:

```
C:\poppler\Library\bin
```

---

## 🔐 Configuração (.env)

Criar arquivo `.env` na raiz:

```bash
TELEGRAM_BOT_TOKEN=SEU_TOKEN
DEEPSEEK_API_KEY=SUA_API_KEY
OCR_LANG=por+eng
```

⚠️ Nunca compartilhe este arquivo

---

## ▶️ Execução

### Bot principal (jurídico)

```bash
python -m core.bot
```

---

### Bot de e-mail/publicações

```bash
python bot_email.py
```

---

## 🪟 Criando arquivos de execução (.bat)

### start_main.bat

```bat
@echo off
cd /d C:\caminho\agente_juridico
call venv\Scripts\activate
python -m core.bot
pause
```

---

### start_email.bat

```bat
@echo off
cd /d C:\caminho\agente_juridico
call venv\Scripts\activate
python bot_email.py
pause
```

---

## 🔄 Fluxo de Uso

1. Enviar documento no Telegram
2. Sistema extrai dados
3. Conferir informações
4. Corrigir se necessário
5. Enviar comando `/kit`
6. Documentos são gerados

---

## ⚠️ Problemas Comuns

### OCR não funciona

* Verificar Tesseract instalado
* Conferir caminho no `.env`

---

### Erro com PDF

* Verificar Poppler no PATH

---

### Bot não inicia

* Verificar `.env`
* Conferir token do Telegram

---

### Erro de módulo

```bash
pip install -r requirements.txt
```

---

## 🔐 Segurança

* Nunca subir `.env` para repositórios
* Não armazenar dados sensíveis sem criptografia
* Utilizar backup seguro

---

## 💾 Backup (Recomendado)

1. Compactar o projeto (sem `.env`)
2. Criptografar
3. Armazenar em nuvem (ex: OneDrive)

---

## 📊 Status

* Sistema funcional no Windows
* Requer configuração manual de OCR
* Uso assistido recomendado

---

## 👤 Autor

Raphael Vitor Aragão de Oliveira

---

