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

O projeto foi concebido para priorizar o processamento local sempre que tecnicamente possível, preservando a confidencialidade das informações processuais e reduzindo custos operacionais.

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

## 📄 Documentarista Petições

Responsável pela preparação estruturada de peças e documentos jurídicos, fornecendo uma base padronizada para o desenvolvimento da atividade jurídica.

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

Atualmente contempla fluxos para:

- Procuração
- Contrato de Honorários
- Declaração de Hipossuficiência
- Petições
- Juntadas

### 📚 Biblioteca de Petições

A Biblioteca de Petições constitui a base estruturada utilizada pelo Documentarista para orientar a preparação das peças.

A primeira frente implementada é o Juizado Especial Cível, contemplando estruturas para:

- Petição Inicial
- Contestação
- Contestação com Pedido Contraposto
- Réplica
- Embargos de Declaração
- Recurso Inominado

A biblioteca foi concebida para expansão progressiva para outros ritos e procedimentos, preservando a separação entre a infraestrutura pública do projeto e as estratégias intelectuais internas utilizadas pelo escritório.

---

## 🧑‍⚖️ Documentarista de Audiências

Agente especializado na organização e acompanhamento de audiências, com processamento de documentos e informações de pauta.

Principais recursos:

- recebimento de documentos pelo Telegram;
- OCR e extração de informações;
- identificação e normalização de dados da audiência;
- revisão das informações extraídas;
- geração de agenda em formato `.ics`;
- notificações e alertas;
- separação entre audiências pendentes de revisão e audiências confirmadas.

O agente foi desenvolvido como módulo independente, com armazenamento e ciclo operacional próprios.

---

## 🏛️ Documentarista Previdenciário

Agente especializado na documentação inicial de clientes para demandas previdenciárias.

Fluxo de processamento:

Documento ou foto

⬇

OCR

⬇

Extração de Dados

⬇

Revisão pelo usuário

⬇

Confirmação

⬇

Geração do Kit Previdenciário

Atualmente gera automaticamente:

- Procuração;
- Declaração de Hipossuficiência;
- Renúncia ao Teto;
- Contrato de Honorários.

O agente possui bot Telegram próprio e token independente, mantendo o módulo previdenciário separado dos demais agentes.

A estrutura foi concebida para reutilizar a infraestrutura segura do projeto sem depender diretamente do núcleo do bot principal.

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

O projeto prioriza o processamento local dos modelos de IA e dos dados sensíveis, reduzindo a dependência de serviços externos.

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

O Telegram constitui uma das principais interfaces operacionais do sistema.

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
├── peticionamento/
├── previdenciario/
│   ├── bot_prev.py
│   ├── engine_prev.py
│   ├── kit_prev.py
│   └── ui_prev.py
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

biblioteca_peticoes/
└── juizados/
    ├── inicial/
    ├── contestacao/
    ├── contestacao_pedido_contraposto/
    ├── replica/
    ├── embargos_declaracao/
    └── recurso_inominado/

services/
│
├── OCR
├── Conversor PDF
├── Parser
├── Prompt Builder
└── Templates

telegram_formatter/

audiencias/
├── extractor.py
├── models.py
├── normaliza.py
├── ocr.py
├── protocolo.py
├── store.py
├── watcher.py
├── notifier.py
└── ics_builder.py

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

O Agente Jurídico OLV foi concebido com cinco princípios fundamentais:

### Privacidade

O projeto prioriza o processamento local de dados e a separação entre infraestrutura pública e dados operacionais do escritório, reduzindo a exposição de informações processuais e documentais.

### Modularidade

Cada componente possui responsabilidades bem definidas, permitindo manutenção simplificada e expansão da plataforma.

### Produtividade

Automatizar tarefas repetitivas para que o profissional concentre seus esforços na atividade intelectual e estratégica.

### Responsabilidade profissional

A automação tem função de apoio à atividade jurídica. A análise dos fatos, definição da estratégia, interpretação jurídica e decisão sobre o conteúdo das peças permanecem sob responsabilidade do profissional.

### Separação entre infraestrutura e estratégia

O repositório público contém componentes técnicos, estruturas documentais e bases destinadas à automação jurídica.

Metodologias proprietárias, estratégias internas de trabalho e camadas privadas de produção do escritório não fazem parte deste repositório.

---

# 📈 Roadmap

## Implementado

- Orquestrador Jurídico
- Documentarista Petições
- Biblioteca de Petições — Juizado Especial Cível
- Documentarista de Audiências
- Documentarista Previdenciário — MVP
- OCR Jurídico
- Controladoria
- DJEN
- Banco Vetorial
- Biblioteca Jurídica
- Templates DOCX
- Integração Telegram
- Agenda de Audiências

## Próximas expansões

- CPC
- CLT
- Juizado Especial Federal

## Em desenvolvimento

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

© 2026 Raphael V. A. Oliveira – Oliveira Advocacia.

Este repositório é disponibilizado para fins de demonstração técnica, documentação da arquitetura do projeto e controle de versionamento.

O código-fonte permanece protegido pela legislação de direitos autorais aplicável.

Salvo autorização prévia e expressa do autor, **não é permitida** a reprodução, modificação, redistribuição ou utilização, total ou parcial, deste projeto para fins comerciais ou não comerciais.

Todos os direitos reservados.
