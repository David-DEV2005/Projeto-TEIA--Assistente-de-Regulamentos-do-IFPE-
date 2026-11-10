from pathlib import Path
import pymupdf

pdf = next(Path("data/raw").glob("*.pdf"))
doc = pymupdf.open(pdf)

sem_texto = [i + 1 for i, p in enumerate(doc) if len(p.get_text().strip()) <= 50]
print("Páginas sem texto:", sem_texto)

com_tabela = []
for i, p in enumerate(doc):
    try:
        if p.find_tables().tables:
            com_tabela.append(i + 1)
    except Exception:
        pass
print("Páginas com tabela detectada:", com_tabela)

for n in (8, 30, 60):
    texto = doc[n - 1].get_text()
    print(f"\n--- página {n} do PDF ---")
    print(texto[:700])