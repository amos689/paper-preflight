<div align="center">

![paper-preflight](docs/assets/brand/paper-preflight-logo.svg)

**投稿前，把论文的每一条参考文献拿到真实学术数据库里核对一遍。<br>
不靠大模型猜，不乱扣"伪造"的帽子。**

[![CI](https://github.com/amos689/paper-preflight/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/amos689/paper-preflight/actions/workflows/ci.yml)
[![PyPI 版本](https://img.shields.io/pypi/v/paper-preflight?label=PyPI&color=2f6fb0)](https://pypi.org/project/paper-preflight/)
[![MIT 许可证](docs/assets/badges/license.zh-CN.svg)](LICENSE)
[![paper-preflight 在 Glama 上的 MCP 服务器评分](https://glama.ai/mcp/servers/amos689/paper-preflight/badges/score.svg)](https://glama.ai/mcp/servers/amos689/paper-preflight)

[![Python 3.11 至 3.14](docs/assets/badges/python.zh-CN.svg)](pyproject.toml)
[![输入：LaTeX、Word、Markdown 和 PDF](docs/assets/badges/input.zh-CN.svg)](#能读哪些稿件)
[![核对 6 个学术数据库](docs/assets/badges/sources.zh-CN.svg)](#工作原理)
[![判定不用大模型](docs/assets/badges/verdicts.zh-CN.svg)](#设计原则)
[![只读的 MCP 工具](docs/assets/badges/mcp.zh-CN.svg)](docs/mcp.md)

[![在 Windows、Linux 和 macOS 上测试](docs/assets/badges/platforms.zh-CN.svg)](https://github.com/amos689/paper-preflight/actions/workflows/ci.yml)
[![英文和简体中文](docs/assets/badges/languages.zh-CN.svg)](README.md)

[English](README.md) · **简体中文** · [快速上手](#快速上手) ·
[使用手册（英文）](docs/README.md) · [版本发布](https://github.com/amos689/paper-preflight/releases) ·
[反馈问题](https://github.com/amos689/paper-preflight/issues/new/choose)

</div>

![paper-preflight 检查示例论文：未定义的引用键、指向另一篇论文的 DOI、所有数据源都查不到的文献、已撤稿论文和重复的条目键报为错误；已正式发表的预印本、指向同一作品的两个条目、错误的年份和带 LaTeX 转义的 DOI 报为警告](https://raw.githubusercontent.com/amos689/paper-preflight/main/docs/demo/demo.gif)

大模型会编造参考文献，复制来的 BibTeX 也常带着错误的年份、作者和失效的 DOI。paper-preflight 读取你的论文
（LaTeX、Word、Markdown、Typst、PDF 或纯文本的参考文献列表），就每一条被引文献去问 Crossref、dblp、arXiv、
DataCite、PubMed 和 OpenAlex；配置了免费 key 的话还会问 Semantic Scholar，没有 DOI 的图书问 Open Library，
软件、模型和数据集问 GitHub、PyPI、CRAN、Hugging Face 和 OpenML：

- 它真的存在吗？
- 和你写的一致吗？
- 撤稿了吗？
- 你引用的预印本后来正式发表了吗？

每一条发现都有记录作依据，或者所有可能收录该作品的来源都明确回答了"没有"。判断不了的时候，它会直说
"无法确定"并给出原因，而不是去猜。判定过程中没有任何大模型参与。

> **状态：1.0。** 在为这次发布专门留出的三周真实 arXiv 论文上，每百条参考文献 0.79 个误报，同时报出
> 409 个真问题（见[准确度](#准确度如何)）。规则编号、JSON 报告、项目设置、命令和 Python API 在整个 1.x
> 内保持兼容（[哪些是稳定的](docs/stability.md)，英文）。最希望收到的是误报反馈：请
> [提交 issue](https://github.com/amos689/paper-preflight/issues)。

## 快速上手

有 [uv](https://docs.astral.sh/uv/) 就无需安装：

```bash
uvx paper-preflight check path/to/paper
```

`path/to/paper` 可以是论文目录、主 `.tex` 文件或 `.bib` 文件。想长期安装（需要 Python 3.11 或更高）：

```bash
pip install paper-preflight
```

| 扩展 | 增加的功能 | 安装 |
|---|---|---|
| `pdf` | 读取 PDF 里的参考文献列表 | `pip install "paper-preflight[pdf]"` |
| `mcp` | 给编码助手用的 MCP 服务 | `pip install "paper-preflight[mcp]"` |
| `support` | 实验性的引用原文查找，含本地模型 | `pip install "paper-preflight[support]"` |

仓库里的[示例论文](examples/demo-paper)引用了 11 篇文献，其中几条是故意写错的。上面的动图就是
`paper-preflight check examples/demo-paper` 直连真实数据源的一次真实运行：那篇正确的 NeurIPS 论文虽然在
Crossref 里只有假冒副本，仍然通过 dblp 得到核实；没有标识符的那本书由 Open Library 确认；暂不支持其文字的
那本中文书被报告为"无法确定"，而不是"未找到"。

<details>
<summary>同一次运行的中文文本输出</summary>

```text
$ paper-preflight check examples/demo-paper --lang zh
paper-preflight 1.0.0 · main.tex · 12 条参考文献，12 个被引用的键

错误    CIT001 main.tex:31
    引用键 'nonexistent2023' 未在任何参考文献文件中定义（共被引用 1 次）。
错误    REF001 refs.bib:43
    条目 'devlin2019bert' 的 doi（10.1109/cvpr.2016.90）在 Crossref 中指向另一篇作品："Deep Residual Learning for Image Recognition"（He et al.，2016）。
错误    REF003 refs.bib:66
    在 Crossref、dblp 和 Semantic Scholar 中均未找到 'lindqvist2024quantum'，且所有来源都已正常应答。请确认该作品确实存在、标题无误。
错误    REF004 refs.bib:73
    'wakefield1998ileal' 已撤稿（依据：Crossref、OpenAlex）。除非正文讨论的就是撤稿本身，否则不应引用。
错误    CIT002 refs.bib:128
    条目键 'kingma2015adam' 已在第 47 行定义；BibTeX 会忽略这一条。
警告    REF015 refs.bib:31
    'he2015residual' 引用的预印本已正式发表于 CVPR（2016），DOI 10.1109/cvpr.2016.90。建议改引正式版本，并保留 eprint 字段。
警告    CIT004 refs.bib:37
    条目 'devlin2019bert' 与 'he2016deep' 疑似同一篇文献（DOI相同）。
警告    REF013 refs.bib:51
    条目 'kingma2015adam' 的年份是 2016，但 dblp 记录为 2014, 2015。
警告    REF017 refs.bib:112
    条目 'tacl2019example' 的 doi 包含 LaTeX 转义符：'10.1162/tacl\_a\_00276'。应写为：10.1162/tacl_a_00276
提示    REF005 refs.bib:73
    'wakefield1998ileal' 有已发布的更正（依据：Crossref）。
提示    REF090 refs.bib:95
    无法核实 'zhou2016ml'：暂不支持非拉丁文字的标题；没有标识符的灰色文献（图书、报告、软件、网页等）。
提示    CIT003 refs.bib:116
    条目 'lecun1998gradient' 从未被引用。

参考文献核查：已核实 7 · 元数据不符 1 · 标识符冲突 1 · 未找到 1 · 无法确定 1
错误 5 · 警告 4 · 提示 3
```

</details>

## 能读哪些稿件

| 你手上有 | 命令 |
|---|---|
| LaTeX 项目：目录、主 `.tex` 或 `.bib`；只附带编译生成的 `.bbl` 的项目（很多 arXiv 源码就是这样）会读取 `.bbl`（只检查，不修改） | `paper-preflight check path/to/paper` |
| Word 稿件：Zotero、Mendeley 或 EndNote 插入的引用，Word 自带的源管理器，或手打的参考文献列表 | `paper-preflight check paper.docx` |
| Markdown、Quarto 或 R Markdown：`[@key]` 对照其文献库 | `paper-preflight check paper.qmd` |
| Typst：`@key` 对照 `#bibliography(...)`、`.bib` 或 Hayagriva `.yml` | `paper-preflight check paper.typ` |
| 单独的文献库：BibTeX、CSL-JSON（`.json`）、RIS（`.ris`）或 YAML（`.yml`） | `paper-preflight check refs.ris` |
| 纯文本的参考文献列表，常见格式均可（APA、IEEE、ACM、Nature、Vancouver、Springer、Elsevier、MDPI、GOST、Chicago、MLA） | `paper-preflight check references.txt`，或用 `-` 从标准输入读取 |
| 只有 PDF（需 `pdf` 扩展） | `paper-preflight check paper.pdf` |
| 任何一篇 arXiv 论文：源码下载到临时目录，检查完即删除 | `paper-preflight check arxiv:2607.06922` |

每种输入能看出什么、看不出什么，详见 [docs/inputs.md](docs/inputs.md)（英文）。

## 能查出什么

每条参考文献得到一个判定：

| 判定 | 含义 |
|---|---|
| 已核实 | 找到了这篇作品的记录，且与条目一致 |
| 元数据不符 | 找到了作品，但条目里写的不一样：具体哪个字段由发现指明 |
| 标识符冲突 | 条目里的 DOI 或 arXiv 编号属于另一篇作品 |
| 未找到 | 所有可能收录它的来源都已应答，都没有这篇作品 |
| 无法确定 | 判断不了，报告里写明原因 |

具体问题由各条规则报出：

| 规则 | 发现 |
|---|---|
| REF001 | DOI 或 arXiv 编号指向的是另一篇论文 |
| REF002 | DOI 或 arXiv 编号根本不存在 |
| REF003 | 所有来源都已应答，均未找到这篇文献 |
| REF004 · REF005 | 已撤稿，或有关注声明、更正 |
| REF010–REF014 | 作者、标题、年份或发表场所与真实记录不符 |
| REF015 | 引用的预印本已经正式发表 |
| REF016 | 登记机构有 DOI 而条目里没有（作为安全修复提供） |
| REF017 | 标识符写法会导致链接失效（`10.1162/tacl\_a\_00276`、`…v1`） |
| REF018 | 引用的 arXiv 预印本已被作者撤回 |
| REF019 · REF021 | 链接的代码仓库、软件包或数据集不存在；链接的网页已失效且没有存档 |
| REF020 | 引用预印本时写的发表场所，期刊与会议目录中都查不到 |
| REF090 | 无法确定，并且一定给出原因（来源不可用、灰色文献等） |
| CIT001–CIT008 | 引用键未定义、重复、未被引用或疑似重复；`.bib` 语法错误 |
| TEX001–TEX004 | 包含的文件缺失、无法读取或互相包含；远程文献库未检查 |
| RUN001 · RUN002 · CFG001 | 有数据源不可用、核查不完整；由替代来源代为应答；屏蔽注释没有屏蔽任何发现 |

每条规则都有[说明页](docs/rules/README.md)：检查什么、什么时候可能误报、怎么处理。
`paper-preflight explain REF003` 会在终端里显示同样的内容。

## 准确度如何？

四项实测，全部直连真实数据源：

| 测在哪里 | 结果 |
|---|---|
| [真实论文](#真实论文)：为 1.0 留出的三周 arXiv 论文，共 60 篇、2,714 条参考文献，每个报警都人工复核 | **每百条 0.79 个误报**（大约每三篇论文一个），同时报出 409 个真问题 |
| [通过了同行评审的幻觉引用](#通过了同行评审的幻觉引用)：GPTZero 在 NeurIPS 2025 和 ICLR 2026 论文里找到的 151 条 | **报出 142 条（94%）**，9 条无法确定，**没有一条判为核实** |
| [HALLMARK](#hallmark) 公开基准：开发中从未用过的 831 条 | 任何问题：精确率 98.5%、召回率 93.5%、误报率 1.9% |
| [与五个工具对比](#与其他工具对比)：一项已发表研究人工标注的 104 条 | 精确率 72.5%（其余工具 31%–51%），召回率 87.9% |

精确率优先：只有拿到正面证据才会判为伪造；查询无应答或候选有歧义时，结论是"无法确定"，绝不是
"未找到"。评测框架和每次运行的结果都在 [`evals/`](evals/README.md)。

### 真实论文

| arXiv 论文首次提交（每周 20 篇） | 所用版本 | 参考文献 | 报警 | 真问题 | 误报 | 不确定 | 每百条误报 |
|---|---|---|---|---|---|---|---|
| 2026-10-07..13，最近一周 | 1.0 的第一个候选 | 991 | 81 | 76 | 4 | 1 | 0.4 |
| 2026-03-25..31 | 1.0.0 | 809 | 220 | 209 | 8 | 3 | 1.0 |
| 2026-03-18..24 | 1.0.0 | 1,007 | 110 | 105 | 5 | 0 | 0.5 |
| 2026-03-11..17 | 1.0.0 | 898 | 104 | 95 | 8 | 1 | 0.9 |
| **为 1.0 留出的三周** | **1.0.0** | **2,714** | **434** | **409** | **21** | **4** | **0.79** |

### 通过了同行评审的幻觉引用

GPTZero 公布了它在 NeurIPS 2025 论文和 ICLR 2026 投稿中发现的 151 条幻觉引用，每条都经其人工确认。按论文
印出的样子粘贴成纯文本来检查，报出 142 条，没有一条被判为核实。没有报出的 9 条是网页和博客、没有数据源收录
的研讨会、配上编造作者而多篇作品共用其标题的真实标题，以及两条乱到无法检索的条目；每条的原因见
[`evals/results/gptzero.md`](evals/results/gptzero.md)。这些是 GPTZero 自己的工具找到的，也就是检索能发现的
那类幻觉；对各类幻觉的整体召回率更低（见 HALLMARK）。

### HALLMARK

[HALLMARK](https://github.com/rpatrik96/hallmark)（v1.2.3）是真实与伪造 BibTeX 条目混合的公开基准。"只算
伪造"指标识符错误、查无此文、作者完全对不上；"任何问题"另加作者、标题、年份或发表场所不符。

| 数据集 | 口径 | 精确率 | 召回率 | 误报率 | 覆盖率 |
|---|---|---|---|---|---|
| `test_public`：831 条，开发中从未使用 | 任何问题 | 98.5% | 93.5% | 1.9% | 97.7% |
| | 只算伪造 | 99.0% | 50.2% | 0.6% | 97.7% |
| `dev_public`：1,119 条，开发中使用 | 任何问题 | 97.7% | 94.3% | 2.1% | 98.9% |
| | 只算伪造 | 98.2% | 53.7% | 1.0% | 98.9% |

`test_public` 用 1.0.0 运行，`dev_public` 用 0.8.0 运行；没有任何规则是在 `test_public` 上调出来的。

- **误报大多是有争议的标签。** `dev_public` 中被标为"真实"的条目，凡是我们报了问题的，都逐条人工核查过：
  剩下的 11 条其实并不是正确的引用（DOI 属于别的论文、作者列表里有并非作者的人、年份被改动、标题被截断）。
  剔除后两种口径都是 100% 精确率。清单及每条可一查即证的理由见
  [`evals/hallmark_disputed.toml`](evals/hallmark_disputed.toml)。
- **目前还会漏掉的：** 只在末尾漏掉部分作者的作者列表，或只能拿预印本（后续版本会增加作者）来比的作者列表
  （只作为提示点名），以及借用了多篇真实作品共有标题的编造条目。各种伪造类型的明细见
  [`evals/results/`](evals/results/)。

### 与其他工具对比

[Badalova & Mayr (2026)](https://doi.org/10.5281/zenodo.21457492) 人工核对了 104 条参考文献，并公布了五个
工具各自报了哪些。在同样的参考文献上、按他们的标注：

| 工具 | 精确率 [95% 置信区间] | 召回率 | 每百条正确文献的误报 |
|---|---|---|---|
| CheckIfExist | 47.7% [36.0%, 59.6%] | 93.9% | 47.9 |
| HalluCiteChecker | 47.4% [32.5%, 62.7%] | 54.5% | 28.2 |
| Hallucinator | 50.9% [38.3%, 63.4%] | 87.9% | 39.4 |
| HalRef | 31.2% [21.9%, 42.2%] | 72.7% | 74.6 |
| RefChecker | 47.1% [35.7%, 58.8%] | 97.0% | 50.7 |
| **paper-preflight** | **72.5% [57.2%, 83.9%]** | 87.9% | **15.5** |

样本小，区间很宽。研究把"作品存在"的参考文献都标为正确，所以 paper-preflight 的"误报"中有 5 条指出的
其实是真实错误（作者写错、DOI 损坏）。在这份数据里发现的两类误报原因，都在上表这次运行之前修好了（第一次
运行的精确率是 62.8%），详见 [`evals/results/badalova-mayr.md`](evals/results/badalova-mayr.md)。

## 局限

- **非拉丁文字的标题**（中文、日文、西里尔字母等）目前一律报"无法确定"；以英译题名引用的中文文献也一样，
  因为开放索引很少收录译名。
- **没有标识符的灰色文献**（报告、学位论文、手册、标准）常常是"无法确定"：开放登记处收录得很少。图书会问
  Open Library，软件问 GitHub、PyPI 和 CRAN，模型和数据集问 Hugging Face 和 OpenML。
- **网页从不判真伪。** 只有链接的网页已失效且没有存档时才会报出（REF021）。
- **没有任何开放索引收录的作品**：如果它的发表场所在期刊与会议目录里也查不到，结论是"无法确定"；但如果
  场所是目录里有的，仍可能报"未找到"。处理这条发现之前，请先看 [REF003 的说明页](docs/rules/REF003.md)。
- **查不出的情况：** 借用多篇作品共有的真实标题编造的引用，只在末尾漏掉作者的作者列表（只作为提示），
  以及引用了真实论文、但论文里并没有那个说法（只有实验性的
  [`support`](#实验功能为每处引用找到原文出处) 会去读说法）。
- **第一次运行需要联网：** 冷缓存下每条参考文献约 0.4 秒，50 条的论文大约 20 秒。查询结果会缓存，
  `--offline` 只用缓存。有数据源宕机、又没有别的来源能替它回答时，结论是"核查不完整"（退出码 2），绝不会
  宣称"没问题"。

## 获取已核实的 BibTeX

不要凭记忆写条目，按 DOI、arXiv 编号或标题直接取。每个字段都来自登记机构的记录，条目上方的注释写明了出处：

```bash
paper-preflight bib fetch 1810.04805
```

```bibtex
% Verified with paper-preflight against dblp (conf/naacl/DevlinCLT19), 2026-10-03
@inproceedings{devlin2019bert,
  title         = {{BERT:} Pre-training of Deep Bidirectional Transformers for Language Understanding},
  author        = {Devlin, Jacob and Chang, Ming-Wei and Lee, Kenton and Toutanova, Kristina},
  booktitle     = {NAACL-HLT (1)},
  year          = {2019},
  doi           = {10.18653/v1/n19-1423},
  eprint        = {1810.04805},
  archivePrefix = {arXiv},
}
```

- **预印本：** 已经正式发表的 arXiv 预印本会返回正式版本，并保留 `eprint`；要预印本本身请加
  `--prefer preprint`。
- **按标题查：** `--title`（需要时配合 `--author`/`--year`）遇到多篇作品都吻合时会列出候选，而不是替你挑一篇。
- **撤稿：** 已撤稿的作品会附带警告。
- **给脚本和智能体用：** 加 `--format json`。

## 修复参考文献

`bib fix` 把核查发现变成对 `.bib` 文件的修改，修改内容取自已核实的记录。它默认只输出 diff，加上 `--apply`
才会写回文件：

```bash
paper-preflight bib fix path/to/paper --level unsafe
```

```diff
--- a/refs.bib
+++ b/refs.bib
@@ -48,7 +47,7 @@
   title     = {Adam: A Method for Stochastic Optimization},
   author    = {Kingma, Diederik P. and Ba, Jimmy},
   booktitle = {International Conference on Learning Representations (ICLR)},
-  year      = {2016},
+  year      = {2015},
 }
```

- `--level safe`（默认）只修不会改变所引作品的问题：会让链接失效的标识符写法，以及登记机构有、条目里却缺的
  DOI。
- `--level unsafe` 还会按记录改写作者、标题、年份和发表场所，删除指向别的论文的标识符，并把已正式发表的
  预印本改引正式版本（条目类型、发表场所、年份、卷、页码和 DOI；保留 eprint）。请先看 diff 再应用。
- 只改涉及的字段；注释、排版、换行符和编码都保持原样。查无此文的条目永远不会被"修好"：引用的到底是什么，
  只有你能回答。

## 选项与退出码

| 选项 | 作用 |
|---|---|
| `--format json` / `--format sarif` | 机器可读的输出（SARIF 可接入 GitHub 代码扫描）；`-o` 写入文件 |
| `--fail-on warning` | 警告也算失败（默认只有错误算失败；`never` 表示都不算） |
| `--offline` | 完全不联网，只用本地缓存里已有的结果 |
| `--refresh` | 不用缓存，向所有来源重新查询（例如记录刚被更正之后） |
| `--recheck` | 立即重新检索以前因"太新、尚未被收录"而无法判断的条目（不加时每天自动重查一次） |
| `--details` | 逐条列出所有发现；默认情况下，适用于很多条目的建议（预印本已发表、可补的 DOI）合并成一行 |
| `--hide-info` | 不显示提示 |
| `--lang zh` | 中文输出（也会按系统语言自动选择） |

| 退出码 | 含义 |
|---|---|
| 0 | 没有达到 `--fail-on` 级别的发现 |
| 1 | 有阻塞性发现 |
| 2 | 没有阻塞性发现，但有数据源不可用，也没有其他来源能替它回答，暂时不能宣称"没问题" |
| 3 | 用法错误 |
| 4 | 内部错误（请报告给我们） |

JSON 报告遵循[公开的 JSON Schema](docs/schema/check-report.schema.json)（`schema_version` 1.0）：可以新增
字段，但在 1.x 内不会删除字段或改变含义。全部选项、缓存及其有效期见
[docs/configuration.md](docs/configuration.md)（英文）。

## 项目设置

要对整个项目生效，可以在论文旁边（或它上方直到仓库根目录的某个文件夹里）放一个 `paper-preflight.toml`，
或者写在 `pyproject.toml` 的 `[tool.paper-preflight]` 里：

```toml
ignore-rules = ["REF016"]                  # 不报这些规则
ignore-keys = ["internal2024*"]            # 也不报这些条目的任何发现
severity = { REF015 = "info" }             # 已正式发表的预印本只作为提示
disable-sources = ["s2"]                   # 只能关闭可选来源
fail-on = "warning"                        # 同 --fail-on；命令行参数优先
```

也可以用 `check --config <路径>` 指定文件。可选来源有 `s2`、`openlibrary`、`github`、`pypi`、`cran`、
`huggingface`、`openml`、`web`（网页链接）和 `wayback`；判定所依据的核心数据源不能关闭。文件里的错误（未知的
规则或设置项）会直接报错，不会被悄悄忽略。JSON 报告在 `run.notes` 里写明用了哪个文件；MCP 服务也会读取它。

### 屏蔽已确认无误的发现

在条目正上方写一行注释，即可对该条目屏蔽指定规则，还可以注明理由：

```bibtex
% preflight: ignore[REF003] reason="内部技术报告，任何数据库都未收录"
@techreport{lab2024internal,
  ...
}
```

判定结果仍保留在 JSON 报告里，只是不再报出这条发现。没有屏蔽掉任何发现的注释会以 CFG001（提示）报出，
免得过时的注释越积越多（参考文献类规则要等一次完整的联网核查之后才判断，因为离线答复和来源故障都可能让
这些规则没有运行）。

认为某条发现有误？请看[误报的原因与处理](docs/false-positives.md#中文)。

### 配置免费凭据，效果更好

不注册任何账号也能用。下面这些环境变量是可选的，能让核查更快、更完整；它们的值永远不会被打印或记录。

| 环境变量 | 作用 |
|---|---|
| `PAPER_PREFLIGHT_EMAIL` | 进入 Crossref 的礼貌池：更快、更稳定 |
| `OPENALEX_API_KEY` | 更多的 OpenAlex 额度，用于撤稿核查 |
| `S2_API_KEY` | 用 Semantic Scholar 补查其他来源都找不到的文献 |
| `GITHUB_TOKEN` | 引用代码仓库时使用 GitHub 更大的额度（每小时 5,000 次，而不是 60 次） |
| `NCBI_API_KEY` | 查 PMID 和 PMCID 时使用 PubMed 更大的额度（每秒 10 次，而不是 3 次） |

`paper-preflight doctor` 会显示哪些已经设置，以及每个数据源此刻能否连通。

## 接入你的工作流

**Claude Code：** 安装插件。插件自带 MCP 服务和一个技能：让 Claude 在说"论文完成"之前先核查参考文献，只修
有证据证明错了的地方，绝不编造参考文献。

```bash
claude plugin marketplace add amos689/paper-preflight
```

```bash
claude plugin install paper-preflight@paper-preflight
```

**Codex、Gemini CLI、Copilot、Cursor 等智能体：** 安装同一个技能（也可以用
`gh skill install amos689/paper-preflight paper-preflight`）。没有配置 MCP 服务时，它会改用命令行：

```bash
npx skills add amos689/paper-preflight
```

**支持 MCP 的客户端（Codex、Cursor、VS Code 等）：** 运行 `paper-preflight mcp`（需 `mcp` 扩展）。工具都是
只读的，并且限制在你的工作区内，配置见 [docs/mcp.md](docs/mcp.md)（英文）。

**GitHub Actions：** `uses: amos689/paper-preflight@main` 在每次推送时检查论文，报告写进任务摘要页，也可以
生成代码扫描告警，见 [docs/github-action.md](docs/github-action.md)（英文）。

**pre-commit：** 每次提交时几秒内检查引用键和缓存中的核查结果，见 [docs/pre-commit.md](docs/pre-commit.md)
（英文）。

**Python：**

```python
import paper_preflight

report = paper_preflight.check_paper("paper/")
for ref in report.references:
    print(ref.key, ref.verdict, [f.rule for f in ref.findings])
```

返回的是简单、不可变的数据类，详见 [docs/python-api.md](docs/python-api.md)（英文）。

## 实验功能：为每处引用找到原文出处

`support` 会到每篇被引文献里，找一段与引用句的说法相符的原文。它读取被引文献的文本（arXiv 源码、开放获取
的全文或 PDF，都没有时用摘要），再由一个本地小模型（HHEM-2.1-open，0.4 GB）给与这句话最相关的几个段落打分。
需要 `support` 扩展。

```bash
paper-preflight support path/to/paper --download-model --all
```

`--download-model` 只在第一次下载模型权重；`--all` 会把已确认的引用和原文一并列出。目标也可以写成
`arxiv:<编号>`，用法与 `check` 相同。

- **结论只有两种**："已确认"，并逐字引出那段原文；或者"未能确认"，并说明原因（拿不到文本、只有摘要，或者
  没有足够接近的段落）。
- **它从不说某处引用是错的。** 在 298 处引用的标注集上，它的"已确认"有 93% 是对的（95% 置信区间
  82%–98%）；但真实引用中它只能确认大约六分之一，而得分低的引用真是错引的还不到一半。标注集的标签由 AI 模型
  给出，不是专家标注，详见 [`evals/results/support.md`](evals/results/support.md)。
- **也可以让你的智能体来判断。** MCP 工具 `preflight_cited_passages` 返回每句话的说法和被引文献里最相关的
  段落，交给智能体按同样的规则判断，不需要模型。在标注集的 100 处引用上，Claude 智能体据此确认了 39% 的真实
  引用（HHEM 为 9%），每一处确认至少部分成立（标签出自同一系列的模型）。
- **哪些内容会离开你的电脑：** 只有被引文献的标识符，用来获取它们的文本；引用句只在本地打分。

## 工作原理

1. **源码优先。** 按 LaTeX 的方式读取项目：会跳过注释和 `\iffalse` 块，遵守 `\includeonly`，`.aux` 文件新鲜时
   直接采用；键重复时以第一个定义为准，和 BibTeX 一致。
2. **标识符优先的路由。** DOI 交给它的注册机构（由 doi.org 告诉我们是 Crossref、DataCite 还是其他）；arXiv
   编号交给 arXiv，arXiv 限流时改走 DataCite；PMID 和 PMCID 交给 PubMed（它也会标出已撤稿的文章）；没有标识符
   的条目按标题在 dblp 和 Crossref 中检索。dblp 的搜索接口会给脚本弹出反爬验证，我们走的是它的 SPARQL 接口。
   哪个来源问什么、如何控制请求频率，见 [docs/sources.md](docs/sources.md)（英文）。
3. **逐字段比对，带防护。** 比对标题（包括 arXiv 早期版本的标题）、作者（容忍 Reiß/Reis 这类转写差异）、年份
   和发表场所。检索结果只有在足够多字段一致、且没有其他作品同样吻合时才会被采用；已知的假冒 DOI 副本会被跳过。
4. **每条文献一个判定**，见[能查出什么](#能查出什么)。"未找到"要求每个必需来源都明确回答"没有"。
5. **本地缓存。** 查询结果保存在本地的 SQLite 文件里，重复运行很快，`--offline` 也能用。

### 设计原则

- **正面确认，否则弃权。** 限流、宕机或未收录，结论都是"无法确定"，绝不是"未找到"。
- **判定不用大模型。** 每个判定都来自记录和固定的规则，同样的记录得出同样的报告。
- **中性措辞。** 只陈述观察（"在 Crossref、dblp 和 Semantic Scholar 中均未找到，且所有来源都已正常应答"），
  不作指控。
- **本地优先，零遥测。** 只把*被引文献*的元数据（DOI、标题、作者）发给上述公开学术接口；你的论文正文不会离开
  你的电脑。

### 我们绝不做的事

帮助规避查重或 AI 文本检测（降重、降 AI 率）、爬取付费墙或反爬保护的网站、凭记忆替你推荐或"补全"参考文献、
点名羞辱作者。

## 路线图

- **下一步：中文原文参考文献**，先在留出的论文上测量，达标后才发布。
- **让更多灰色文献有结论**：没有标识符的报告、学位论文、手册等。

每个版本带来了什么，见[更新日志](CHANGELOG.md)（英文）；日常进度见 [docs/PROGRESS.md](docs/PROGRESS.md)。

## 参与贡献

最有价值的贡献是附带可复现 `.bib` 条目的问题报告，尤其是误报。见 [CONTRIBUTING.md](CONTRIBUTING.md)；安全
问题见 [SECURITY.md](SECURITY.md)。

## 许可证

[MIT](LICENSE)。改写自其他项目的代码见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
