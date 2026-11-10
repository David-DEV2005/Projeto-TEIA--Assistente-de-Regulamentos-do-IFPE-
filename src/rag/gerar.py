"""Etapas 3.1 a 3.4: pergunta -> busca -> prompt -> resposta validada + fontes.

Uso:
  python src/rag/gerar.py "pergunta" [prova|historico|-] [v1|v2|v3]
No codigo:
  from src.rag.gerar import responder
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv  # noqa: E402

from src.indice.busca_hibrida import buscar_com_modo  # noqa: E402
from src.rag.llm import gerar  # noqa: E402
from src.rag.saida import validar  # noqa: E402

load_dotenv()
PROMPTS = Path(__file__).parent / "prompts"
TENTATIVAS = 3
LEMBRETE = (
    "Sua resposta não era um JSON válido no formato pedido. Responda de novo, somente com o JSON: "
    '{"encontrou": true, "resposta": "...", "trechos_usados": [1]}'
)


def rotulo_fonte(meta):
    """Texto de citacao montado a partir dos metadados (nunca pelo LLM)."""
    pi, pf = meta["pagina_inicio"], meta["pagina_fim"]
    pagina = f"p. {pi}" if pi == pf else f"pp. {pi}-{pf}"
    return f"{meta.get('caminho') or meta['tipo']} ({pagina})"


def montar_contexto(resultados):
    return "\n\n".join(
        f"[{n}] Fonte: {rotulo_fonte(r['meta'])}\n{r['texto']}" for n, r in enumerate(resultados, 1)
    )


def gerar_validado(prompt, n_trechos):
    """Chama o LLM em modo JSON e valida; tenta de novo se a saida for invalida."""
    mensagens = [{"role": "user", "content": prompt}]
    erro = ""
    for tentativa in range(1, TENTATIVAS + 1):
        bruto = gerar(mensagens, json_mode=True)
        try:
            return validar(bruto, n_trechos), tentativa, ""
        except Exception as e:                       # JSON quebrado ou campos errados
            erro = f"{type(e).__name__}: {str(e)[:160]}"
            mensagens += [{"role": "assistant", "content": bruto}, {"role": "user", "content": LEMBRETE}]
    return None, TENTATIVAS, erro


def responder(pergunta, selecao=None, versao=None, k=None):
    versao = versao or os.getenv("PROMPT_VERSION", "v3")
    k = k or int(os.getenv("TOP_K", "5"))
    estrategia = os.getenv("CHUNKING", "titulo")
    modo = os.getenv("RETRIEVAL", "hibrida")

    t0 = time.time()
    resultados = buscar_com_modo(pergunta, k, estrategia, selecao, modo)
    t_busca = time.time() - t0

    modelo_prompt = (PROMPTS / f"{versao}.txt").read_text(encoding="utf-8")
    prompt = modelo_prompt.replace("{contexto}", montar_contexto(resultados)).replace("{pergunta}", pergunta)

    t1 = time.time()
    saida = {"pergunta": pergunta, "versao": versao, "tentativas": 1, "erro": "", "prompt": prompt}
    if versao == "v1":
        saida.update(encontrou=None, resposta=gerar([{"role": "user", "content": prompt}]).strip())
        usados = list(range(1, len(resultados) + 1))
    else:
        r, tentativas, erro = gerar_validado(prompt, len(resultados))
        saida.update(tentativas=tentativas, erro=erro)
        if r is None:
            saida.update(encontrou=False, resposta="Não consegui montar uma resposta válida. Tente reformular a pergunta.")
            usados = []
        else:
            saida.update(encontrou=r.encontrou, resposta=r.resposta.strip())
            usados = r.trechos_usados if r.encontrou else []
            if r.encontrou and not usados:           # respondeu mas nao disse em que se baseou
                usados, saida["citacao_automatica"] = [1, 2], True
    t_llm = time.time() - t1

    vistos, fontes = set(), []
    for n in usados:
        r = resultados[n - 1]
        rotulo = rotulo_fonte(r["meta"])
        if rotulo not in vistos:                     # evita citar duas vezes o mesmo item
            vistos.add(rotulo)
            fontes.append({"id": r["id"], "rotulo": rotulo})
    saida.update(
        fontes=fontes,
        recuperados=[{"id": r["id"], "rotulo": rotulo_fonte(r["meta"]), "texto": r["texto"]} for r in resultados],
        tempos={"busca": round(t_busca, 1), "llm": round(t_llm, 1)},
    )
    return saida


def main():
    if len(sys.argv) < 2:
        sys.exit('Uso: python src/rag/gerar.py "pergunta" [prova|historico|-] [v1|v2|v3]')
    selecao = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != "-" else None
    versao = sys.argv[3] if len(sys.argv) > 3 else None
    s = responder(sys.argv[1], selecao, versao)
    print(f"\nPERGUNTA: {s['pergunta']}  [prompt {s['versao']}]\n")
    print(s["resposta"])
    if s["fontes"]:
        print("\nFontes:")
        for f in s["fontes"]:
            print(f"  - {f['rotulo']}")
    print(f"\n(busca {s['tempos']['busca']}s | LLM {s['tempos']['llm']}s | tentativas: {s['tentativas']}"
          + (f" | erro: {s['erro']}" if s["erro"] else "")
          + (" | citação automática" if s.get("citacao_automatica") else "") + ")")


if __name__ == "__main__":
    main()