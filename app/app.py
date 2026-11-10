"""Interface web (Gradio) do assistente do Edital de Ingresso IFPE 2027.1.

Uso, a partir da raiz do projeto:
  python app/app.py
Abre em http://localhost:7860. Requer o Ollama rodando com os modelos do
.env e o indice do ChromaDB ja criado (python src/indice/indexar.py).
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gradio as gr  # noqa: E402

from src.rag.gerar import responder  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
EXEMPLO_IDS = ("q01", "q02", "q04", "q05", "q11", "q13")
RESPOSTA_INICIAL = "Faça uma pergunta sobre o edital — por exemplo, uma das perguntas de exemplo abaixo."


def carregar_exemplos():
    caminho = RAIZ / "data" / "avaliacao" / "perguntas_teste.json"
    try:
        with open(caminho, encoding="utf-8") as f:
            qs = json.load(f)["perguntas"]
        exemplos = [q["pergunta"] for q in qs if q["id"] in EXEMPLO_IDS]
    except OSError:
        exemplos = []
    return exemplos or ["Até quando posso pagar a taxa de inscrição?"]


def md_resposta(s):
    partes = [f"**{s['resposta']}**"]
    if s.get("encontrou") is False:
        partes += ["", "_Essa informação não está no edital (ou não foi encontrada nos trechos recuperados)._"]
    if s["fontes"]:
        partes += ["", "**Fontes**"] + [f"- {f['rotulo']}" for f in s["fontes"]]
    return "\n".join(partes)


def md_detalhes(s):
    modo = os.getenv("RETRIEVAL", "hibrida")
    linhas = [
        f"busca: {s['tempos']['busca']}s · geração: {s['tempos']['llm']}s · tentativas: {s['tentativas']}"
        f" · prompt {s['versao']} · recuperação {modo} · {len(s['recuperados'])} trechos recuperados",
        "",
    ]
    if s.get("citacao_automatica"):
        linhas += [
            "O modelo não indicou em que trechos se baseou; as fontes foram atribuídas"
            " automaticamente aos dois primeiros trechos.",
            "",
        ]
    if s.get("erro"):
        linhas += [f"Último erro de validação: {s['erro']}", ""]
    citados = {f["rotulo"] for f in s["fontes"]}
    linhas += ["**Trechos recuperados**", ""]
    for n, r in enumerate(s["recuperados"], 1):
        marca = " (usado na resposta)" if r["rotulo"] in citados else ""
        linhas += [f"**[{n}] {r['rotulo']}**{marca}", ""]
        linhas += [("> " + linha) if linha.strip() else ">" for linha in r["texto"].splitlines()] + [""]
    return "\n".join(linhas)


def md_erro_ollama():
    return "**O Ollama não está rodando.**\n\nAbra um terminal, execute `ollama serve` e tente de novo."


def md_erro_modelo():
    return (
        "**Modelo não encontrado no Ollama.**\n\nExecute "
        f"`ollama pull {os.getenv('LLM_MODEL', 'llama3.2')} {os.getenv('EMBEDDING_MODEL', 'bge-m3')}` e tente de novo."
    )


def md_erro_indice():
    return "**Índice do edital não encontrado.**\n\nExecute `python src/indice/indexar.py` e tente de novo."


def responder_ui(pergunta):
    pergunta = (pergunta or "").strip()
    if not pergunta:
        return "Escreva uma pergunta sobre o edital.", ""
    try:
        s = responder(pergunta)
    except ConnectionError:
        return md_erro_ollama(), ""
    except Exception as e:
        msg = str(e).lower()
        if "not found" in msg or "pull" in msg:
            return md_erro_modelo(), ""
        if "collection" in msg or "does not exist" in msg:
            return md_erro_indice(), ""
        return f"Ocorreu um erro inesperado: {str(e)[:200]}", ""
    return md_resposta(s), md_detalhes(s)


def montar_interface():
    exemplos = carregar_exemplos()
    with gr.Blocks(title="Assistente de Regulamentos IFPE") as demo:
        gr.Markdown(
            "# Assistente de Regulamentos — Edital de Ingresso IFPE 2027.1\n\n"
            "Responde dúvidas sobre o edital usando **apenas o conteúdo do próprio edital**, "
            "com busca híbrida (BM25 + embeddings) e citação da fonte com a página. "
            "Se a pergunta estiver fora do edital, o assistente avisa que não encontrou a informação."
        )
        pergunta = gr.Textbox(
            label="Sua pergunta",
            placeholder="Ex.: Até quando posso pagar a taxa de inscrição?",
            lines=2,
            autofocus=True,
        )
        with gr.Row():
            btn = gr.Button("Perguntar", variant="primary")
            limpar = gr.Button("Limpar")
        gr.Markdown("### Resposta")
        resposta = gr.Markdown(RESPOSTA_INICIAL)
        with gr.Accordion("Detalhes da busca e da geração", open=False):
            detalhes = gr.Markdown("Os trechos recuperados e os tempos aparecem aqui depois de perguntar.")
        gr.Examples(examples=[[p] for p in exemplos], inputs=[pergunta], label="Perguntas de exemplo")
        btn.click(responder_ui, [pergunta], [resposta, detalhes])
        pergunta.submit(responder_ui, [pergunta], [resposta, detalhes])
        limpar.click(
            lambda: ("", RESPOSTA_INICIAL, ""),
            outputs=[pergunta, resposta, detalhes],
        )
    return demo


if __name__ == "__main__":
    montar_interface().launch(theme=gr.themes.Soft())
