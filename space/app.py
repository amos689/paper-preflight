"""The paper-preflight Hugging Face Space: check a paper's references without installing anything.

The check is the released package's (requirements.txt pins it); this file is only the page.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import gradio as gr
from runner import MAX_ENTRIES, InputError, Outcome, check

INTRO = f"""
# paper-preflight

Check every reference of a paper against real scholarly records: Crossref, dblp, arXiv,
DataCite, OpenAlex, Semantic Scholar and PubMed. It finds references that do not exist,
identifiers that point to another paper, wrong authors, titles or years, retracted papers and
preprints that have been published. No LLM decides anything: every finding rests on a record,
and an unanswered lookup is reported as "cannot determine", never as "not found".

**Privacy:** your files are deleted after the check. Only the references' metadata (titles,
authors, identifiers) is sent to the scholarly sources above. This demo checks up to
{MAX_ENTRIES} references; for more, and for LaTeX projects on your own machine:
`pip install paper-preflight` ([GitHub](https://github.com/amos689/paper-preflight)).

在线检查论文的每条参考文献：不存在的文献、指向别的论文的标识符、错误的作者/标题/年份、已撤稿的
论文、已正式发表的预印本。判定不用大模型；查不到时报"无法确定"，不报"不存在"。文件检查完即删除。
"""


def _downloads(outcome: Outcome) -> list[str]:
    folder = Path(tempfile.mkdtemp(prefix="preflight-out-"))
    files = {"report.json": outcome.json, "report.sarif": outcome.sarif}
    if outcome.diff:
        files["fixes.diff"] = outcome.diff
    for name, text in files.items():
        (folder / name).write_text(text, encoding="utf-8")
    return [str(folder / name) for name in files]


def _run(arxiv: str, upload: str | None, pasted: str, lang: str, show_info: bool) -> tuple:
    try:
        outcome = check(
            arxiv=arxiv or "",
            upload=Path(upload) if upload else None,
            pasted=pasted or "",
            lang="zh" if lang == "中文" else "en",
            show_info=show_info,
        )
    except InputError as exc:
        raise gr.Error(str(exc)) from exc
    diff = outcome.diff or "No fixes to suggest. (Fixes are suggested for .bib files only.)"
    return (
        f"```text\n{outcome.summary}\n```",
        outcome.rows,
        outcome.text,
        diff,
        _downloads(outcome),
    )


with gr.Blocks(title="paper-preflight: check a paper's references") as demo:
    gr.Markdown(INTRO)
    with gr.Row():
        lang = gr.Radio(["English", "中文"], value="English", label="Language / 语言")
        show_info = gr.Checkbox(value=False, label="Also show info findings / 显示提示")
    with gr.Tabs():
        with gr.Tab("arXiv paper"):
            arxiv = gr.Textbox(label="arXiv ID or link", placeholder="1706.03762")
            arxiv_button = gr.Button("Check", variant="primary")
            gr.Examples([["1706.03762"]], inputs=[arxiv])
        with gr.Tab("Upload a file"):
            upload = gr.File(
                label=".bib, .bbl, .tex, .txt, .pdf, or a .zip of the LaTeX project "
                "(Overleaf: Menu → Download → Source)",
                file_types=[".bib", ".bbl", ".tex", ".txt", ".pdf", ".zip"],
                type="filepath",
            )
            upload_button = gr.Button("Check", variant="primary")
        with gr.Tab("Paste references"):
            pasted = gr.Textbox(
                label="One reference per line or paragraph, as printed in the paper",
                lines=12,
            )
            pasted_button = gr.Button("Check", variant="primary")
    summary = gr.Markdown()
    table = gr.Dataframe(
        headers=["Severity", "Rule", "Where", "Finding"], wrap=True, interactive=False
    )
    with gr.Accordion("Full report", open=False):
        report = gr.Textbox(lines=20, show_label=False)
    with gr.Accordion("Suggested .bib fixes (review before applying)", open=False):
        diff = gr.Code(language=None, show_label=False)
    files = gr.File(label="Downloads: JSON, SARIF, fixes", file_count="multiple")

    outputs = [summary, table, report, diff, files]
    blank = gr.State("")
    none = gr.State(None)
    arxiv_button.click(_run, [arxiv, none, blank, lang, show_info], outputs)
    upload_button.click(_run, [blank, upload, blank, lang, show_info], outputs)
    pasted_button.click(_run, [blank, none, pasted, lang, show_info], outputs)

demo.queue(default_concurrency_limit=1, max_size=20)

if __name__ == "__main__":
    demo.launch()
