# ⚖️ Agente Jurídico OLV

> **Status do Projeto**
>
> 🟢 Desenvolvimento ativo
>
> O Agente Jurídico OLV encontra-se em desenvolvimento contínuo. A arquitetura atual está consolidada e novos agentes especializados estão sendo incorporados progressivamente, preservando a compatibilidade com o núcleo da plataforma.

> Plataforma modular de Inteligência Artificial para automação da advocacia.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Status](https://img.shields.io/badge/status-em%20desenvolvimento-success)
![SQLite](https://img.shields.io/badge/database-SQLite-blue)
![Ollama](https://img.shields.io/badge/LLM-Ollama-orange)
![Telegram](https://img.shields.io/badge/interface-Telegram-26A5E4)

---

# 📖 Visão Geral

O **Agente Jurídico OLV** é uma plataforma de automação jurídica desenvolvida para auxiliar escritórios de advocacia na execução de atividades repetitivas, utilizando Inteligência Artificial Local, OCR, recuperação semântica de conhecimento jurídico (RAG), monitoramento de publicações e geração automatizada de documentos.

Ao contrário de soluções dependentes de serviços em nuvem, o projeto foi concebido para operar prioritariamente em ambiente local, preservando a confidencialidade das informações processuais e reduzindo custos operacionais.

O sistema foi projetado seguindo uma arquitetura modular, permitindo a expansão para novos agentes especializados sem necessidade de reestruturação do núcleo da aplicação.

---

# 🚀 Principais Funcionalidades

## 🧠 Orquestrador Jurídico

Responsável pelo gerenciamento dos agentes do sistema.

- Controle dos serviços
- Gerenciamento dos processos
- Interface administrativa
- Comunicação com Telegram
- Controle operacional

---

## 📄 Documentarista Cível

Responsável pela geração automatizada de documentos jurídicos.

Fluxo de processamento:

Documento

⬇

OCR

⬇

Extração de Dados

⬇

Parser Jurídico

⬇

LLM Local

⬇

Template DOCX

⬇

Documento Final

Atualmente gera automaticamente:

- Procuração
- Contrato de Honorários
- Declaração de Hipossuficiência
- Petições
- Juntadas

---

## ⚖️ Controladoria Jurídica

Sistema responsável pela gestão operacional dos processos.

Recursos:

- Controle de prazos
- Histórico de eventos
- Auditoria
- Alertas automáticos
- Monitoramento
- Gestão das publicações

---

## 📰 DJEN

Captura automática de publicações do Diário da Justiça Eletrônico Nacional.

Permite:

- Processamento das publicações
- Identificação de processos
- Alimentação automática da Controladoria
- Cálculo de prazos

---

## 🤖 Inteligência Artificial Local

Integração com modelos locais através do Ollama.

Compatível com:

- Qwen
- Phi
- Outros modelos suportados pelo Ollama

Todo o processamento ocorre localmente.

---

## 📚 Biblioteca Jurídica

Base legislativa própria contendo:

- Constituição Federal
- Código Civil
- Código de Processo Civil
- Código Penal
- Código de Processo Penal
- CLT
- Código de Defesa do Consumidor
- Lei dos Juizados Especiais

Utilizada como fonte de conhecimento para consultas futuras.

---

## 🔎 Banco Vetorial

Infraestrutura preparada para recuperação semântica utilizando ChromaDB.

Recursos:

- Pesquisa vetorial
- BM25
- RAG Jurídico
- Recuperação híbrida

---

## 📱 Interface Telegram

Toda a operação diária do sistema é realizada diretamente pelo Telegram.

O usuário pode:

- acompanhar prazos;
- gerar documentos;
- controlar os agentes;
- consultar processos;
- receber notificações.

---

# 🏗 Arquitetura

```
                         Telegram
                              │
                       Orquestrador
                              │
         ┌────────────┬───────────────┬─────────────┐
         │            │               │             │
         │            │               │             │
 Documentarista   Controladoria      DJEN      IA Local
      │               │               │             │
      └───────────────┼───────────────┘             │
                      │                             │
             Banco Vetorial (RAG)                   │
                      │                             │
              Biblioteca Jurídica                   │
                      └──────────────┬──────────────┘
                                     │
                                  SQLite
```

---

# 📂 Estrutura do Projeto

```
core/
│
├── Documentarista Cível
├── OCR
├── Parser Jurídico
├── IA
└── Interface

orchestrator/
│
├── Router
├── Process Manager
├── Dispatcher
└── Controladoria

infra/
│
├── Banco de Dados
├── Repositórios
├── Cliente LLM
├── RAG
└── Persistência

services/
│
├── OCR
├── Conversor PDF
├── Parser
├── Prompt Builder
└── Templates

telegram_formatter/

dicionario/

leis_html/

db_vetorial/

legado/
```

---

# ⚙ Tecnologias

- Python
- SQLite
- Ollama
- ChromaDB
- Telegram Bot API
- Tesseract OCR
- LibreOffice
- python-docx
- Pillow
- OpenCV

---

# 🎯 Filosofia do Projeto

O Agente Jurídico OLV foi concebido com três princípios fundamentais:

### Privacidade

Todo o processamento ocorre localmente, reduzindo a dependência de serviços externos e preservando o sigilo profissional.

### Modularidade

Cada componente possui responsabilidades bem definidas, permitindo manutenção simplificada e expansão da plataforma.

### Produtividade

Automatizar tarefas repetitivas para que o profissional concentre seus esforços na atividade intelectual e estratégica.

---

# 📈 Roadmap

## Implementado

- Orquestrador Jurídico
- Documentarista Cível
- OCR Jurídico
- Controladoria
- DJEN
- Banco Vetorial
- Biblioteca Jurídica
- Templates DOCX
- Telegram

## Em desenvolvimento

- Documentarista Previdenciário
- Bibliotecária IA
- Pesquisa Jurisprudencial
- Agenda Inteligente
- CRM Jurídico
- Dashboard Administrativo
- API Pública

---

# 🤝 Contribuições

O projeto encontra-se em constante evolução.

Sugestões e discussões técnicas são bem-vindas.

---

# 📜 Direitos Autorais

© 2026 Raphael Oliveira – Oliveira Advocacia.

Este repositório é disponibilizado para fins de demonstração técnica, documentação da arquitetura do projeto e controle de versionamento.

O código-fonte permanece protegido pela legislação de direitos autorais aplicável.

Salvo autorização prévia e expressa do autor, **não é permitida** a reprodução, modificação, redistribuição ou utilização, total ou parcial, deste projeto para fins comerciais ou não comerciais.

Todos os direitos reservados.
