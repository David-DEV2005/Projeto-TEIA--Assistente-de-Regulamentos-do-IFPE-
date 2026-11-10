# Assistente de Regulamentos — Edital de Ingresso IFPE 2027.1

Assistente de perguntas e respostas sobre o Edital de Ingresso do IFPE (curso técnico,
2027.1), construído com RAG (*Retrieval-Augmented Generation*) e executado **100% em
ambiente local**: o modelo de linguagem e o modelo de embeddings rodam no Ollama, sem
envio de dados para serviços externos.

O assistente responde **usando apenas o conteúdo do próprio edital**, cita a fonte de
cada resposta (tópico e página) e se recusa a responder quando a informação não está no
documento — em vez de inventar uma resposta.

## Como funciona

O pipeline tem três etapas, mapeadas nos diretórios de `src/`:

1. **Ingestão** (`src/ingestion/`) — extrai o texto do PDF, limpa, reconstrói as tabelas
   e divide o edital em trechos (*chunks*) por títulos numerados (capítulos e itens do
   edital), preservando o caminho do título e a página como metadados.
2. **Índice** (`src/indice/`) — gera os embeddings dos chunks com o modelo `bge-m3` e os
   grava no ChromaDB. A busca é **híbrida**: BM25 (palavras-chave) + busca vetorial
   (semântica) combinadas por *Reciprocal Rank Fusion* (RRF).
3. **Geração** (`src/rag/`) — recupera os trechos mais relevantes, monta o prompt com
   instruções de fidelidade (responder só com base nos trechos, citar fontes, recusar
   quando não houver respaldo) e gera a resposta com o `llama3.2` via Ollama, em
   temperatura baixa (0.1). As fontes citadas na resposta são verificadas contra os
   metadados dos trechos recuperados.

A interface web (`app/`, em Gradio) expõe o `responder()` com a resposta formatada, as
fontes e um painel de detalhes com os trechos recuperados, tempos e número de tentativas.

## Estrutura do repositório

| Caminho | Conteúdo |
|---|---|
| `app/app.py` | Interface web (Gradio) |
| `src/ingestion/` | Extração de texto, tabelas e chunking do PDF |
| `src/indice/` | Indexação no ChromaDB e busca (vetorial, BM25, híbrida) |
| `src/rag/` | Geração com o LLM, prompts (v1–v3) e formatação da saída |
| `src/avaliacao/` | Avaliação da busca e das respostas geradas |
| `data/raw/` | PDF do edital (não versionado no git) |
| `data/processed/` | Saídas intermediárias: páginas, tabelas, chunks (não versionado) |
| `data/curado/` | Conteúdo corrigido à mão, incorporado aos chunks |
| `data/avaliacao/` | Perguntas de teste (dentro e fora do escopo) e resultados |
| `tests/` | Testes automatizados (`pytest`) |

## Requisitos

- Python 3.10+ (testado em 3.14)
- [Ollama](https://ollama.com) rodando localmente, com os modelos:
  - `llama3.2` (geração)
  - `bge-m3` (embeddings)
- O PDF do edital (ou edital equivalente) para a ingestão

## Instalação

```bash
git clone <url-do-repositorio>
cd assistente-regulamentos-ifpe

python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate    # Linux/macOS

pip install -r requirements.txt

copy .env.example .env         # Windows
# cp .env.example .env         # Linux/macOS
```

As configurações do `.env` (com os valores usados no desenvolvimento):

```
LLM_PROVIDER=ollama       # único provedor suportado
LLM_MODEL=llama3.2
EMBEDDING_MODEL=bge-m3
CHUNKING=titulo            # estratégia de chunk (titulo | fixo)
RETRIEVAL=hibrida         # modo de busca (vetorial | bm25 | hibrida)
TOP_K=5                    # trechos recuperados por pergunta
PROMPT_VERSION=v3
NUM_CTX=8192               # contexto do llama3.2
TEMPERATURE=0.1
```

## Preparação do índice

Coloque o PDF do edital em `data/raw/` e, com o Ollama rodando:

```bash
ollama serve                              # se ainda não estiver rodando
ollama pull llama3.2 bge-m3

python src/ingestion/extrair_texto.py     # data/processed/paginas.json
python src/ingestion/tabelas.py           # data/processed/tabelas.json
python src/ingestion/chunker.py           # data/processed/chunks.json
python src/indice/indexar.py              # chroma_db/ (coleção edital_titulo)
```

Todos os comandos devem ser executados **a partir da raiz do projeto** (os caminhos de
`data/` e `chroma_db/` são relativos ao diretório de trabalho). Rodar o `indexar.py`
de novo recria a coleção do zero.

## Uso

### Interface web

```bash
python app/app.py
```

Abre em `http://localhost:7860`: digite a pergunta (ou clique em uma das perguntas de
exemplo), veja a resposta com as fontes e expanda "Detalhes da busca e da geração" para
os trechos recuperados, tempos e tentativas.

### Linha de comando

```bash
python src/rag/gerar.py "Até quando posso pagar a taxa de inscrição?"
python src/rag/gerar.py "Quem tem direito à isenção?" prova     # só seleção por prova
python src/rag/gerar.py "Quem tem direito à isenção?" -         # sem filtro
python src/rag/gerar.py "Pergunta" - v2                         # outra versão de prompt
```

## Avaliação e testes

```bash
# 20 perguntas de teste: rodada completa com o LLM, salva resultados em data/avaliacao/
python src/avaliacao/avaliar_respostas.py v3

# 6 perguntas fora do escopo (verificação de recusa)
python src/avaliacao/avaliar_respostas.py v3 --fora

# Métricas só da recuperação: acerto@1/@3/@5 e MRR@10, sem gastar LLM
python src/avaliacao/avaliar_busca.py            # estratégia do .env
python src/avaliacao/avaliar_busca.py --sem-vetor   # só BM25 (não precisa do Ollama)

# Testes automatizados (27 testes)
pytest -q
```

Resultado da última rodada completa (prompt v3, busca híbrida, top-5): 14/20 respostas
com todos os itens exigidos + 4 paráfrases válidas, 6/6 recusas corretas para perguntas
fora do escopo.

## Limitações conhecidas

- **Siglas não são expandidas na busca**: perguntas com "ADS" (Análise e Desenvolvimento
  de Sistemas) não recuperam os trechos certos; use o nome completo do curso.
- Três perguntas do conjunto de teste têm resposta incompleta ou imprecisa:
  - *documentos para o pedido de isenção* (omite o grupo do CadÚnico);
  - *a que horas abrem os portões* (cita o item 9.2 em vez do 9.1);
  - *data da lista final de isentos* (não informa a data 9/11/2026).
- Apenas o provedor `ollama` é suportado; `LLM_PROVIDER` com outro valor levanta
  `ValueError`.
- O índice e o PDF não são versionados: em um clone novo é preciso refazer a ingestão
  e a indexação (etapas acima).
