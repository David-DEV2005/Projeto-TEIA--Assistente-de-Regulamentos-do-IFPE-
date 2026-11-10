"""Etapa 3.6: conferencia das respostas finais (pergunta -> busca -> LLM validado).

Uso:
  python src/avaliacao/avaliar_respostas.py [v1|v2|v3] [--fora]
A versao do prompt vem do .env quando nao e informada.
Criterios: para as perguntas do edital, encontrou=True e a resposta contem todas as
expressoes de deve_conter. Para as perguntas fora de escopo, encontrou=False e recusa.
Salva cada resposta (com fontes e tempos) em data/avaliacao/resultados_respostas_<versao>.json,
para leitura manual depois. Requer o Ollama rodando com o LLM e o modelo de embedding.
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.indice.busca_hibrida import sem_acento  # noqa: E402
from src.rag.gerar import responder  # noqa: E402

PERGUNTAS = Path("data/avaliacao/perguntas_teste.json")
FORA_ESCOPO = Path("data/avaliacao/perguntas_fora_escopo.json")
RECUSA = "Não encontrei essa informação no edital"


def normalizar(texto):
    return re.sub(r"\s+", " ", sem_acento(texto.lower()))


def conteudo_ok(resposta, deve_conter):
    t = normalizar(resposta)
    return all(normalizar(e) in t for e in deve_conter)


def conferir(q, s):
    """Devolve (ok, motivo) segundo o comportamento esperado para a pergunta."""
    if "deve_conter" in q:
        if not s.get("encontrou"):
            return False, "recusou uma pergunta que tem resposta no edital"
        if not conteudo_ok(s["resposta"], q["deve_conter"]):
            return False, "respondeu sem o conteudo esperado (conferir se e parfrase)"
        return True, ""
    if s.get("encontrou"):
        return False, "respondeu sem fundamento no edital (deveria recusar)"
    if RECUSA not in s["resposta"]:
        return False, f"recusou com outra mensagem: {s['resposta'][:80]}"
    return True, ""


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    so_fora = "--fora" in sys.argv
    versao = args[0] if args else None
    qs = json.load(open(FORA_ESCOPO, encoding="utf-8"))["perguntas"]
    if not so_fora:
        qs += json.load(open(PERGUNTAS, encoding="utf-8"))["perguntas"]

    detalhes, falhas, ok = [], [], 0
    for q in qs:
        s = responder(q["pergunta"], versao=versao)
        s.pop("prompt", None)
        achou, motivo = conferir(q, s)
        if achou:
            ok += 1
        else:
            falhas.append(q["id"])
        detalhes.append({"id": q["id"], "tipo": q.get("tipo", "edital"), "ok": achou, "motivo": motivo, **s})
        marca = "OK " if achou else "FALHA"
        print(f"{q['id']} {marca} {q['pergunta'][:58]}" + (f"  ({motivo})" if motivo else ""))
        print(f"     -> {s['resposta'][:120]}")

    n = len(qs)
    resumo = {
        "data": datetime.now().isoformat(timespec="seconds"),
        "versao_prompt": detalhes[0]["versao"] if detalhes else "",
        "total": n,
        "ok": ok,
        "falhas": falhas,
    }
    arquivo = Path(f"data/avaliacao/resultados_respostas_{detalhes[0]['versao']}.json")
    arquivo.write_text(
        json.dumps({"resumo": resumo, "resultados": detalhes}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n{ok}/{n} ok  |  falhas: {falhas or 'nenhuma'}")
    print(f"detalhes salvos em {arquivo}")


if __name__ == "__main__":
    main()
