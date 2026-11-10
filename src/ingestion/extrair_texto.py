import json
from collections import Counter
from pathlib import Path

import pymupdf

RAW = Path("data/raw")
OUT = Path("data/processed")


def ler_paginas(pdf_path):
    doc = pymupdf.open(pdf_path)
    return [pagina.get_text() for pagina in doc]


def linhas_repetidas(paginas, minimo=0.5):
    """Linhas que aparecem em pelo menos `minimo` das páginas (menu, rodapé)."""
    contagem = Counter()
    for texto in paginas:
        contagem.update({l.strip() for l in texto.splitlines() if l.strip()})
    limite = len(paginas) * minimo
    return {linha for linha, n in contagem.items() if n >= limite}


def limpar_pagina(texto, numero, repetidas):
    saida = []
    for linha in texto.splitlines():
        l = linha.strip()
        if not l or l in repetidas:
            continue
        if l.isdigit() and int(l) == numero:
            continue
        saida.append(l)
    return "\n".join(saida)


def main():
    pdf = next(RAW.glob("*.pdf"))
    paginas = ler_paginas(pdf)
    repetidas = linhas_repetidas(paginas)

    print(f"Arquivo: {pdf.name} ({len(paginas)} páginas)")
    print(f"Linhas repetidas removidas: {len(repetidas)}")
    for linha in sorted(repetidas):
        print("  -", linha[:100])

    limpas = [
        {"pagina": i + 1, "texto": limpar_pagina(t, i + 1, repetidas)}
        for i, t in enumerate(paginas)
    ]

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "paginas.json", "w", encoding="utf-8") as f:
        json.dump({"arquivo": pdf.name, "paginas": limpas}, f, ensure_ascii=False, indent=1)
    with open(OUT / "texto_limpo.txt", "w", encoding="utf-8") as f:
        for p in limpas:
            f.write(f"\n=== PÁGINA {p['pagina']} ===\n{p['texto']}\n")

    vazias = [p["pagina"] for p in limpas if not p["texto"].strip()]
    print("Páginas vazias após a limpeza:", vazias)


if __name__ == "__main__":
    main()