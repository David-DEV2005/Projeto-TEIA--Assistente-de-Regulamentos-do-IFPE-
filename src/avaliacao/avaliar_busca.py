"""Etapa 2.5: mede a busca (vetorial, bm25, hibrida) com as perguntas de teste.

Uso:
  python src/avaliacao/avaliar_busca.py [titulo|fixo|ambos] [--sem-vetor]
Metricas: acerto@1, @3, @5 (a resposta esta entre os N primeiros) e MRR@10.
Com --sem-vetor mede so o BM25 (nao precisa do Ollama nem do ChromaDB).
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.indice.busca_hibrida import (  # noqa: E402
    buscar_bm25, fundir_rrf, sem_acento, ARQUIVOS, PROC,
)

PERGUNTAS = Path("data/avaliacao/perguntas_teste.json")
CANDIDATOS = 20
MAX_RANK = 10


def normalizar(texto):
    return re.sub(r"\s+", " ", sem_acento(texto.lower()))


def acerta(texto, deve_conter):
    t = normalizar(texto)
    return all(normalizar(e) in t for e in deve_conter)


def primeiro_acerto(ids, textos, deve_conter):
    for pos, id_ in enumerate(ids[:MAX_RANK], 1):
        if acerta(textos[id_], deve_conter):
            return pos
    return None


def carregar_textos(estrategia):
    dados = json.load(open(PROC / ARQUIVOS[estrategia], encoding="utf-8"))
    return {c["id"]: c["texto"] for c in dados["chunks"] if c["indexar"]}


def avaliar(estrategia, usar_vetor):
    perguntas = json.load(open(PERGUNTAS, encoding="utf-8"))["perguntas"]
    textos = carregar_textos(estrategia)
    modos = ["bm25"] + (["vetorial", "hibrida"] if usar_vetor else [])
    ranks = {m: {} for m in modos}
    sem_cobertura = []

    if usar_vetor:
        from src.indice.busca import buscar

    for q in perguntas:
        if not any(acerta(t, q["deve_conter"]) for t in textos.values()):
            sem_cobertura.append(q["id"])
        bm = [r["id"] for r in buscar_bm25(q["pergunta"], CANDIDATOS, estrategia)]
        ranks["bm25"][q["id"]] = primeiro_acerto(bm, textos, q["deve_conter"])
        if usar_vetor:
            vet = [r["id"] for r in buscar(q["pergunta"], CANDIDATOS, estrategia)]
            hib = [i for i, _, _ in fundir_rrf({"v": vet, "b": bm}, MAX_RANK)]
            ranks["vetorial"][q["id"]] = primeiro_acerto(vet, textos, q["deve_conter"])
            ranks["hibrida"][q["id"]] = primeiro_acerto(hib, textos, q["deve_conter"])
    return perguntas, modos, ranks, sem_cobertura


def resumo(modo, ranks):
    r = list(ranks.values())
    n = len(r)
    ate = lambda k: sum(1 for x in r if x and x <= k)
    mrr = sum(1 / x for x in r if x) / n
    return f"{modo:<9} acerto@1 {ate(1)}/{n}  @3 {ate(3)}/{n}  @5 {ate(5)}/{n}  MRR@10 {mrr:.2f}"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    usar_vetor = "--sem-vetor" not in sys.argv
    estrategias = ["titulo", "fixo"] if (not args or args[0] == "ambos") else [args[0]]
    for est in estrategias:
        perguntas, modos, ranks, sem = avaliar(est, usar_vetor)
        print(f"\n===== chunking: {est} =====")
        if sem:
            print("ATENCAO: nenhum chunk contem a resposta esperada para:", sem)
        for m in modos:
            print(resumo(m, ranks[m]))
        print("\nPosição do primeiro acerto (— = fora do top 10):")
        print("id   " + "".join(f"{m:>10}" for m in modos) + "   pergunta")
        for q in perguntas:
            cel = lambda m: ranks[m][q["id"]] or "—"
            print(f"{q['id']:<5}" + "".join(f"{str(cel(m)):>10}" for m in modos) + f"   {q['pergunta'][:55]}")


if __name__ == "__main__":
    main()