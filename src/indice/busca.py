"""Etapa 2.3: busca vetorial no ChromaDB.

Uso na linha de comando:
  python src/indice/busca.py "Até quando posso pagar a taxa de inscrição?"
  python src/indice/busca.py "pergunta" 5 titulo prova
        (k=5, estrategia=titulo, filtro de selecao=prova)
Uso no codigo:
  from src.indice.busca import buscar
"""
import os
import sys

import chromadb
import ollama
from dotenv import load_dotenv

load_dotenv()

DB = "chroma_db"


def buscar(pergunta, k=None, estrategia=None, selecao=None):
    """Devolve os k chunks mais proximos da pergunta.

    selecao: None (sem filtro), 'prova' ou 'historico'. Com filtro, os chunks
    'geral' tambem entram, porque valem para os dois tipos de selecao.
    """
    k = k or int(os.getenv("TOP_K", "5"))
    estrategia = estrategia or os.getenv("CHUNKING", "titulo")
    modelo = os.getenv("EMBEDDING_MODEL", "bge-m3")

    vetor = ollama.embed(model=modelo, input=[pergunta])["embeddings"][0]
    colecao = chromadb.PersistentClient(path=DB).get_collection(f"edital_{estrategia}")

    filtro = None
    if selecao:
        filtro = {"tipo_selecao": {"$in": [selecao, "geral"]}}

    r = colecao.query(query_embeddings=[vetor], n_results=k, where=filtro)
    resultados = []
    for i in range(len(r["ids"][0])):
        resultados.append({
            "id": r["ids"][0][i],
            "texto": r["documents"][0][i],
            "meta": r["metadatas"][0][i],
            "score": 1 - r["distances"][0][i],      # similaridade de cosseno
        })
    return resultados


def main():
    if len(sys.argv) < 2:
        sys.exit('Uso: python src/indice/busca.py "pergunta" [k] [titulo|fixo] [prova|historico]')
    pergunta = sys.argv[1]
    k = int(sys.argv[2]) if len(sys.argv) > 2 else None
    estrategia = sys.argv[3] if len(sys.argv) > 3 else None
    selecao = sys.argv[4] if len(sys.argv) > 4 else None

    print(f"Pergunta: {pergunta}")
    for n, r in enumerate(buscar(pergunta, k, estrategia, selecao), 1):
        m = r["meta"]
        pag = m["pagina_inicio"] if m["pagina_inicio"] == m["pagina_fim"] else f"{m['pagina_inicio']}-{m['pagina_fim']}"
        rotulo = m["caminho"] or m["tipo"]
        print(f"\n[{n}] score {r['score']:.3f} | {r['id']} | p. {pag} | seleção: {m['tipo_selecao']}")
        print(f"    {rotulo[:110]}")
        print("    " + r["texto"][:260].replace("\n", " "))


if __name__ == "__main__":
    main()