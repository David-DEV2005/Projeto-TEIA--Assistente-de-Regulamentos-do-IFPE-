"""Etapa 2.2: gera os embeddings dos chunks e grava no ChromaDB.

Uso:
  python src/indice/indexar.py            # usa CHUNKING do .env (titulo ou fixo)
  python src/indice/indexar.py fixo       # indexa a linha de base
Cada estrategia vira uma colecao separada (edital_titulo, edital_fixo) em chroma_db/.
Rodar de novo recria a colecao do zero.
"""
import json
import os
import sys
import time
from pathlib import Path

import chromadb
import ollama
from dotenv import load_dotenv

load_dotenv()

PROC = Path("data/processed")
DB = "chroma_db"
ARQUIVOS = {"titulo": "chunks.json", "fixo": "chunks_fixos.json"}
CAMPOS_META = ["tipo", "item", "titulo", "caminho", "secao", "tipo_selecao",
               "pagina_inicio", "pagina_fim", "parte", "documento"]
LOTE = 16


def metadados(chunk):
    """Chroma so aceita str/int/float/bool: troca None por texto vazio."""
    meta = {campo: ("" if chunk.get(campo) is None else chunk[campo]) for campo in CAMPOS_META}
    meta["chunk_id"] = chunk["id"]
    return meta


def gerar_embeddings(textos, modelo):
    return ollama.embed(model=modelo, input=textos)["embeddings"]


def main(estrategia=None):
    estrategia = estrategia or os.getenv("CHUNKING", "titulo")
    if estrategia not in ARQUIVOS:
        sys.exit(f"CHUNKING deve ser um de {list(ARQUIVOS)}; recebi '{estrategia}'")
    modelo = os.getenv("EMBEDDING_MODEL", "bge-m3")

    dados = json.load(open(PROC / ARQUIVOS[estrategia], encoding="utf-8"))
    chunks = [c for c in dados["chunks"] if c["indexar"]]
    print(f"Estratégia: {estrategia} | modelo: {modelo} | chunks a indexar: {len(chunks)}")

    cliente = chromadb.PersistentClient(path=DB)
    nome = f"edital_{estrategia}"
    try:
        cliente.delete_collection(nome)
    except Exception:
        pass                                   # primeira vez: nao existia
    colecao = cliente.create_collection(
        nome, metadata={"hnsw:space": "cosine", "modelo_embedding": modelo}
    )

    inicio = time.time()
    for i in range(0, len(chunks), LOTE):
        lote = chunks[i:i + LOTE]
        vetores = gerar_embeddings([c["texto_indexado"] for c in lote], modelo)
        colecao.add(
            ids=[c["id"] for c in lote],
            embeddings=vetores,
            documents=[c["texto"] for c in lote],
            metadatas=[metadados(c) for c in lote],
        )
        feitos = min(i + LOTE, len(chunks))
        decorrido = time.time() - inicio
        restante = decorrido / feitos * (len(chunks) - feitos)
        print(f"  {feitos}/{len(chunks)} chunks | {decorrido:.0f}s | faltam ~{restante:.0f}s")

    print(f"Pronto: coleção '{nome}' com {colecao.count()} itens em {time.time() - inicio:.0f}s")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)