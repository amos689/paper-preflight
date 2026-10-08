<div align="center">

![paper-preflight](docs/assets/brand/paper-preflight-logo.svg)

**投稿前，把 LaTeX 论文的每一条参考文献拿到真实学术数据库里核对一遍。<br>
不靠大模型猜，不乱扣"伪造"的帽子。**

[![CI](https://github.com/amos689/paper-preflight/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/amos689/paper-preflight/actions/workflows/ci.yml)
[![PyPI 版本](https://img.shields.io/pypi/v/paper-preflight?label=PyPI&color=2f6fb0)](https://pypi.org/project/paper-preflight/)
[![MIT 许可证](docs/assets/badges/license.zh-CN.svg)](LICENSE)
[![paper-preflight 在 Glama 上的 MCP 服务器评分](https://glama.ai/mcp/servers/amos689/paper-preflight/badges/score.svg)](https://glama.ai/mcp/servers/amos689/paper-preflight)

[![Python 3.11 至 3.14](docs/assets/badges/python.zh-CN.svg)](pyproject.toml)
[![输入：LaTeX、BibTeX 和 PDF](docs/assets/badges/input.zh-CN.svg)](#快速上手)
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

大模型会编造参考文献，复制来的 BibTeX 也常带着错误的年份、作者和失效的 DOI。paper-preflight
读取你的 `.tex` 和 `.bib`，就每一条被引文献去问 Crossref、dblp、arXiv、DataCite、PubMed 和 OpenAlex（配置
了 key 的话还有 Semantic Scholar；没有 DOI 的图书还会问 Open Library，软件、模型和数据集问 GitHub、PyPI、CRAN、Hugging Face 和 OpenML）：

- 它真的存在吗？
- 和你写的一致吗？
- 撤稿了吗？
- 你引用的预印本后来正式发表了吗？

判断不了的时候，它会直说"无法确定"，而不是去猜。

> **状态：0.x 版本，正在走向稳定的 1.0。** 最希望收到的是误报反馈：请
> [提交 issue](https://github.com/amos689/paper-preflight/issues)。

仓库里的[示例论文](examples/demo-paper)引用了 11 篇文献，其中几条是故意写错的。下面是一次真实运行
（直连真实数据源）的完整输出：

```text
$ paper-preflight check examples/demo-paper --lang zh
paper-preflight 0.4.0 · main.tex · 12 条参考文献，12 个被引用的键

错误    CIT001 main.tex:31
    引用键 'nonexistent2023' 未在任何参考文献文件中定义（共被引用 1 次）。
错误    REF001 refs.bib:43
    条目 'devlin2019bert' 的 doi（10.1109/cvpr.2016.90）在 Crossref 中指向另一篇作品："Deep Residual Learning for Image Recognition"（He et al.，2016）。
错误    REF003 refs.bib:66
    在 Crossref、dblp 和 Semantic Scholar 中均未找到 'lindqvist2024quantum'，且所有来源都已正常应答。请确认该作品确实存在、标题无误。
错误    REF004 refs.bib:73
    'wakefield1998ileal' 已撤稿（依据：Crossref、OpenAlex）。除非正文讨论的就是撤稿本身，否则不应引用。
错误    CIT002 refs.bib:127
    条目键 'kingma2015adam' 已在第 47 行定义；BibTeX 会忽略这一条。
警告    REF015 refs.bib:31
    'he2015residual' 引用的预印本已正式发表于 CVPR（2016），DOI 10.1109/cvpr.2016.90。建议改引正式版本，并保留 eprint 字段。
警告    CIT004 refs.bib:37
    条目 'devlin2019bert' 与 'he2016deep' 疑似同一篇文献（DOI相同）。
警告    REF013 refs.bib:51
    条目 'kingma2015adam' 的年份是 2016，但 dblp 记录为 2014, 2015。
警告    REF017 refs.bib:111
    条目 'tacl2019example' 的 doi 包含 LaTeX 转义符：'10.1162/tacl\_a\_00276'。应写为：10.1162/tacl_a_00276
提示    REF005 refs.bib:73
    'wakefield1998ileal' 有已发布的更正（依据：Crossref）。
提示    REF090 refs.bib:86
    无法核实 'goodfellow2016deep'：没有标识符的灰色文献（图书、报告、软件、网页等）。
提示    REF090 refs.bib:94
    无法核实 'zhou2016ml'：暂不支持非拉丁文字的标题；没有标识符的灰色文献（图书、报告、软件、网页等）。
提示    CIT003 refs.bib:115
    条目 'lecun1998gradient' 从未被引用。

参考文献核查：已核实 6 · 元数据不符 1 · 标识符冲突 1 · 未找到 1 · 无法确定 2
错误 5 · 警告 4 · 提示 4
```

每一条发现都有记录作依据（或者所有来源都明确回答了"没有"）。那篇正确的 NeurIPS 论文虽然在 Crossref
里只有假冒副本，仍然通过 dblp 得到核实；两本没有标识符的书被报告为"无法确定"，而不是"未找到"。

## 能查出什么

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
| CIT001–CIT008 | 引用键未定义、重复、未被引用或疑似重复；`.bib` 语法错误 |
| REF090 | 无法确定，并且一定给出原因（来源不可用、灰色文献等） |

每条规则都有[说明页](docs/rules/README.md)：检查什么、什么时候可能误报、怎么处理。
`paper-preflight explain REF003` 会在终端里显示同样的内容。

## 准确度如何？

四项实测，全部直连真实数据源：已发表论文里的幻觉引用、真实论文的参考文献、与已发表工具的对比，以及一个
公开基准。

### 通过了同行评审的幻觉引用

GPTZero 公布了它在 NeurIPS 2025 论文和 ICLR 2026 投稿中发现的 151 条幻觉引用，每条都经其人工确认。
按论文印出的样子粘贴成纯文本来检查：

| 参考文献 | 报出 | 无法确定 | 判为核实 |
|---|---|---|---|
| 151 | **139（92%）** | 12 | **0** |

- **没有一条被判为核实。** 没有报出的 12 条是网页和博客、没有数据源收录的研讨会、配上编造作者但数据源
  分不清指哪篇的真实标题、被截短的真实标题，以及两条乱到无法检索的条目；每条的原因见
  [`evals/results/gptzero.md`](evals/results/gptzero.md)。
- 这些是 GPTZero 自己的工具找到的，也就是检索能发现的那类幻觉；对各类幻觉的整体召回率更低（见下文
  HALLMARK）。

### 真实论文

连续几周的 arXiv 论文（每周 20 篇，cs、stat、q-bio、quant-ph、astro-ph），按固定规则选取，名单都在所
衡量的改动之前固定，只跑一次；每条警告和错误都人工复核过：

| 首次提交 | 版本 | 参考文献 | 报出的问题 | 真问题 | 误报 | 不确定 | 每百条误报 |
|---|---|---|---|---|---|---|---|
| 2026-08-19..25 | 0.5.0 | 962 | 53 | 41 | 10 | 2 | 1.0 |
| 2026-08-26..09-01 | 0.5.1 | 780 | 101 | 81 | 19 | 1 | 2.4 |
| 2026-09-02..08 | 0.5.2 | 975 | 48 | 31 | 13 | 4 | 1.3 |
| 2026-09-09..15 | 0.5.3 | 1,067 | 98 | 83 | 14 | 1 | 1.3 |
| 2026-09-16..22 | 0.6.0 候选 | 868 | 89 | 76 | 13 | 0 | 1.5 |
| 2026-09-23..29 | 0.6.0 | 786 | 48 | 42 | 6 | 0 | 0.8 |
| 2026-09-30..10-06 | 0.7.0 | 1,014 | 89 | 79 | 7 | 3 | 0.7 |

- **最近一周：大约每三篇论文一次误报**（平均 51 条参考文献），同时报出 79 个真问题：47 个已正式发表的预印本、
  8 个写错的年份、7 个写成链接或带 LaTeX 转义的标识符、5 个条目的作者或名字写错、4 个写错的会议、5 个引错的
  标题，以及两条根本对不上任何作品的参考文献。误报是登记处只按在线日期记年份的三篇文章、一本书对它的电子版、
  登记处自己写法的两个符号，以及被当成论文正式版本的论文代码。
- **之前两周（0.6.0）：1.5，然后 0.8。** 第一周 13 个误报中 8 个是登记处记录自身的错误（作者不全、名字拼错、
  HTML 实体、错字、年份错），其中 5 个已在 0.6.0 修复。
- **有一周超过了 1.5 的目标**（2.4），其中 19 个误报有 11 个已在 0.5.2 修复。
- **第一周平均每两篇论文一次误报**（平均 48 条参考文献），同时报出 41 个真问题：16 个条目本身的错误（写错的年份、
  名字和标题，漏掉的第一作者，把一篇论文的标题配上另一篇的作者，写法会让链接失效的标识符），25 个引用的
  预印本已经正式发表。
- **误报大多来自登记处自身的记录错误**（作者列表不全、乱码符号、作者的英文名）**以及作者列表里的合作组
  名称**（"MAGPI Team"）；另有两个来自被截掉结尾的标题。
- **另有七批各 20 篇论文专门用来找误报，** 每批都先如实测过一次（0.1.0：每百条 4.5 个；0.1.1：2.3 个；
  0.1.2 最后一轮修复前：3.0 个；0.1.2：1.7 个；0.2.1：1.9 个；0.3.0：1.9 个；0.4.0：1.2 个）。详见
  [`evals/README.md`](evals/README.md#real-papers)。

### 与其他工具对比

[Badalova & Mayr (2026)](https://doi.org/10.5281/zenodo.21457492) 人工核对了 104 条参考文献，并公布了
五个工具各自报了哪些。在同样的参考文献上、按他们的标注：

| 工具 | 精确率 [95% 置信区间] | 召回率 | 每百条正确文献的误报 |
|---|---|---|---|
| CheckIfExist | 47.7% [36.0%, 59.6%] | 93.9% | 47.9 |
| HalluCiteChecker | 47.4% [32.5%, 62.7%] | 54.5% | 28.2 |
| Hallucinator | 50.9% [38.3%, 63.4%] | 87.9% | 39.4 |
| HalRef | 31.2% [21.9%, 42.2%] | 72.7% | 74.6 |
| RefChecker | 47.1% [35.7%, 58.8%] | 97.0% | 50.7 |
| **paper-preflight** | **72.5% [57.2%, 83.9%]** | 87.9% | **15.5** |

样本小，区间很宽。研究把"作品存在"的参考文献都标为正确，所以有些报警在这里算作误报：paper-preflight
在这类文献上的报警中，有 5 条指出的是真实错误（作者写错、DOI 损坏）。在这份数据里发现的两类误报原因，
以及研究的 CSV 弄乱的四个人名，都在上表这次运行之前修好了；第一次运行的精确率是 62.8%。详见
[`evals/results/badalova-mayr.md`](evals/results/badalova-mayr.md)。

### 公开基准：HALLMARK

[HALLMARK](https://github.com/rpatrik96/hallmark) 是真实与伪造 BibTeX 条目混合的公开基准。

| 数据集 | 口径 | 精确率 | 召回率 | 误报率 | 覆盖率 |
|---|---|---|---|---|---|
| `test_public`：831 条，开发中从未使用 | 任何问题 | 98.4% | 90.3% | 1.9% | 97.7% |
| | 只算伪造 | 99.0% | 50.2% | 0.6% | 97.7% |
| `dev_public`：1119 条，开发中使用 | 任何问题 | 97.6% | 91.7% | 2.1% | 98.9% |
| | 只算伪造 | 98.2% | 53.7% | 1.0% | 98.9% |

HALLMARK v1.2.3 两个公开数据集的全部条目，2026-10-08 用 0.7.0 运行。"只算伪造"指标识符错误、查无此文、作者
完全对不上；"任何问题"另加作者、标题、年份或发表场所不符。

- **留出测试集印证了开发集的结果：** 在从未用来调整规则的条目上，精确率略高，召回率低一个半百分点。
- **`dev_public` 中被标为"真实"的条目，凡是我们报了问题的，都逐条人工核查过。** 剩下的 11 条其实并不是正确的
  引用：DOI 属于别的论文、作者列表里有并非作者的人、年份被改动、标题被截断。
- **剔除这 11 条后，两种口径都是 100% 精确率、0% 误报。** 清单及每条可一查即证的理由见
  [`evals/hallmark_disputed.toml`](evals/hallmark_disputed.toml)。
- **目前还会漏掉的：** 只有预印本记录的论文上编造的会议名（arXiv 记录无法否定一个会议名），以及只是
  漏掉部分作者的作者列表。各种伪造类型的明细见 [`evals/results/`](evals/results/)。

精确率优先：只有拿到正面证据才会判为伪造；查询无应答或候选有歧义时，结论是"无法确定"，绝不是
"未找到"。评测框架和每次运行的结果都在 [`evals/`](evals/README.md)。

## 快速上手

有 [uv](https://docs.astral.sh/uv/) 就无需安装（也可以 `pip install paper-preflight`）：

```bash
uvx paper-preflight check path/to/paper
```

`path/to/paper` 可以是论文目录、主 `.tex` 文件，或单个 `.bib` 文件。没有 `.bib` 的项目（很多 arXiv
源码就是这样）会读取编译生成的 `.bbl`（只检查，不修改）。

用 Word、Markdown 或 Typst 写作？稿件同样可以检查：

```bash
uvx paper-preflight check paper.docx     # Word：Zotero、Mendeley、EndNote 插入的引用，或手打的列表
uvx paper-preflight check paper.qmd      # Markdown、Quarto、R Markdown：[@key] 对照其文献库
uvx paper-preflight check paper.typ      # Typst：@key 对照 #bibliography(...)，.bib 或 Hayagriva .yml
```

Word 稿件里由 Zotero、Mendeley 或 EndNote 插入的引用，域代码中带有文献管理软件对每篇作品的完整记录，优先读取；
其次是 Word 自带的源管理器；都没有时，读取"参考文献"标题之后手打的列表。文献库也可以单独检查：
CSL-JSON（`.json`）、RIS（`.ris`）、YAML（`.yml`，Hayagriva 或 CSL）。

没有稿件？纯文本的参考文献列表也可以检查，支持常见格式（APA、IEEE、ACM、Nature、Vancouver、
Springer、Elsevier、MDPI、GOST、Chicago、MLA），每行一条、每段一条或带编号均可：

```bash
uvx paper-preflight check references.txt
pbpaste | uvx paper-preflight check -      # 或从标准输入读取
```

任何一篇 arXiv 论文，直接给编号即可：源码会下载到临时目录，检查完即删除。

```bash
uvx paper-preflight check arxiv:2607.06922
```

只有 PDF？装上 `pdf` 扩展后，也能读出其中的参考文献列表：

```bash
uvx --from 'paper-preflight[pdf]' paper-preflight check paper.pdf
```

| 选项 | 作用 |
|---|---|
| `--format json` / `--format sarif` | 机器可读的输出（SARIF 可接入 GitHub 代码扫描） |
| `--offline` | 完全不联网，只用本地缓存里已有的结果 |
| `--refresh` | 不用缓存，向所有来源重新查询（例如记录刚被更正之后） |
| `--recheck` | 立即重新检索以前因"太新、尚未被收录"而无法判断的条目（不加时每天自动重查一次） |
| `--fail-on warning` | 警告也算失败（默认只有错误算失败） |
| `--details` | 逐条列出所有发现；默认情况下，适用于很多条目的建议（预印本已发表、可补的 DOI）合并成一行 |
| `--lang zh` | 中文输出（也会按系统语言自动选择） |

退出码：

| 退出码 | 含义 |
|---|---|
| 0 | 没有达到 `--fail-on` 级别的发现 |
| 1 | 有阻塞性发现 |
| 2 | 没有阻塞性发现，但有数据源不可用，也没有其他来源能替它回答，暂时不能宣称"没问题" |
| 3 | 用法错误 |
| 4 | 内部错误（请报告给我们） |

JSON 报告遵循[公开的 JSON Schema](docs/schema/check-report.schema.json)（`schema_version` 0.1）：
可以新增字段，但不会删除字段或改变含义，除非换新的 `schema_version`。测试会用它校验每一份报告。

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
- **按标题查：** `--title`（需要时配合 `--author`/`--year`）遇到多篇作品都吻合时会列出候选，而不是
  替你挑一篇。
- **撤稿：** 已撤稿的作品会附带警告。
- **给脚本和 AI 助手用：** 加 `--format json`。

## 修复参考文献

`bib fix` 把核查发现变成对 `.bib` 文件的修改，修改内容取自已核实的记录。它默认只输出 diff，加上
`--apply` 才会写回文件：

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

- `--level safe`（默认）只修不会改变所引作品的问题：会让链接失效的标识符写法，以及登记机构有、
  条目里却缺的 DOI。
- `--level unsafe` 还会按记录改写作者、标题、年份和发表场所，删除指向别的论文的标识符，并把已正式
  发表的预印本改引正式版本（条目类型、发表场所、年份、卷、页码和 DOI；保留 eprint）。请先看 diff 再
  应用。
- 只改涉及的字段；注释、排版、换行符和编码都保持原样。查无此文的条目永远不会被"修好"：引用的到底
  是什么，只有你能回答。

## 屏蔽已确认无误的发现

在条目正上方写一行注释，即可对该条目屏蔽指定规则，还可以注明理由：

```bibtex
% preflight: ignore[REF003] reason="内部技术报告，任何数据库都未收录"
@techreport{lab2024internal,
  ...
}
```

判定结果仍保留在 JSON 报告里，只是不再报出这条发现。没有屏蔽掉任何发现的注释会以 CFG001（提示）报出，
免得过时的注释越积越多。参考文献类规则只在完整的联网核查之后才判断是否被用到，因为离线答复和来源故障
都可能让这些规则没有运行。

认为某条发现有误？请看[误报的原因与处理](docs/false-positives.md#中文)。

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
`huggingface`、`openml`、`web`（网页链接）和 `wayback`；判定所依据的核心数据源不能关闭；文件里的错误（未知的规则或设置项）
会直接报错，不会被悄悄忽略。JSON 报告在 `run.notes` 里写明用了哪个文件；MCP 服务也会读取它。

## 实验功能：为每处引用找到原文出处

`support` 会到每篇被引文献里，找一段与引用句的说法相符的原文。它读取被引文献的文本：arXiv 源码、
开放获取的全文或 PDF，都没有时用摘要。然后由一个本地小模型（HHEM-2.1-open，0.4 GB）给与这句话最相关
的几个段落打分。

```bash
pip install "paper-preflight[support]"
```

```bash
paper-preflight support path/to/paper --download-model --all
```

`--download-model` 只在第一次下载模型权重。`--all` 会把已确认的引用和原文一并列出。目标也可以写成
`arxiv:<编号>`，用法与 `check` 相同。

- **结论只有两种**："已确认"，并逐字引出那段原文；或者"未能确认"，并说明原因：拿不到文本、只有
  摘要，或者没有足够接近的段落。只是点名所引对象的引用（"Adam \cite{...}"），如果被引文献的标题里就是
  这个名字，也算确认。
- **它从不说某处引用是错的。** 在 298 处引用的标注集上，它的"已确认"有 93% 是对的（95% 置信区间
  82%–98%）。但真实引用中它只能确认大约六分之一；而得分低的引用，真是错引的还不到一半。标注集的标签
  由 AI 模型给出，不是专家标注，详见 [`evals/results/support.md`](evals/results/support.md)。
- **也可以让你的智能体来判断。** MCP 工具 `preflight_cited_passages` 返回每句话的说法和被引文献里
  最相关的段落，交给 Claude、Codex 等智能体按同样的规则判断；它不需要模型，也不需要 `support` 扩展。在标注集的 100 处
  引用上，Claude 智能体据此确认了 39% 的真实引用（HHEM 为 9%），每一处确认至少部分成立（标签出自同一
  系列的模型）。
- **哪些内容会离开你的电脑**：引用句只在本地打分。发出去的只有被引文献的标识符，用来获取它们的文本；
  拿到的文本保存在本地缓存里。

## 在 Python 里调用

```python
import paper_preflight

report = paper_preflight.check_paper("paper/")
for ref in report.references:
    print(ref.key, ref.verdict, [f.rule for f in ref.findings])
```

返回的是简单、不可变的数据类，详见 [docs/python-api.md](docs/python-api.md)（英文）。

## 在编码助手里使用

**Claude Code**：安装插件。插件自带 MCP 服务和一个技能：让 Claude 在说"论文完成"之前先核查参考
文献，只修有证据证明错了的地方，绝不编造参考文献。

```bash
claude plugin marketplace add amos689/paper-preflight
```

```bash
claude plugin install paper-preflight@paper-preflight
```

**Codex、Gemini CLI、Copilot、Cursor 等智能体**：安装同一个技能。没有配置 MCP 服务时，它会改用命令行：

```bash
npx skills add amos689/paper-preflight
```

也可以用 `gh skill install amos689/paper-preflight paper-preflight` 安装。

**支持 MCP 的客户端（Codex、Cursor、VS Code 等）**：运行 `paper-preflight mcp`。工具都是只读的，并且限
制在你的工作区内，配置见 [docs/mcp.md](docs/mcp.md)。

**pre-commit**：每次提交时几秒内检查引用键和缓存中的核查结果，见
[docs/pre-commit.md](docs/pre-commit.md)。

**GitHub Actions**：`uses: amos689/paper-preflight@main` 在每次推送时检查论文，报告写进任务摘要页，
也可以生成代码扫描告警，见 [docs/github-action.md](docs/github-action.md)。

## 配置免费凭据，效果更好

不注册任何账号也能用。下面这些环境变量是可选的，能让核查更快、更完整；它们的值永远不会被打印或
记录。

| 环境变量 | 作用 |
|---|---|
| `PAPER_PREFLIGHT_EMAIL` | 进入 Crossref 的礼貌池：更快、更稳定 |
| `OPENALEX_API_KEY` | 更多的 OpenAlex 额度，用于撤稿核查 |
| `S2_API_KEY` | 用 Semantic Scholar 补查其他来源都找不到的文献 |
| `GITHUB_TOKEN` | 引用代码仓库时使用 GitHub 更大的额度（每小时 5,000 次，而不是 60 次） |
| `NCBI_API_KEY` | 查 PMID 和 PMCID 时使用 PubMed 更大的额度（每秒 10 次，而不是 3 次） |

`paper-preflight doctor` 会显示哪些已经设置，以及每个数据源此刻能否连通。

## 工作原理

1. **源码优先。** 按 LaTeX 的方式读取项目：会跳过注释和 `\iffalse` 块，遵守 `\includeonly`，`.aux`
   文件新鲜时直接采用；键重复时以第一个定义为准，和 BibTeX 一致。
2. **标识符优先的路由。** DOI 交给它的注册机构（由 doi.org 告诉我们是 Crossref、DataCite 还是
   其他）；arXiv 编号交给 arXiv，arXiv 限流时改走 DataCite；PMID 和 PMCID 交给 PubMed（它也会标出已撤稿的
   文章）；没有标识符的条目按标题在 dblp 和 Crossref 中检索。dblp 的搜索接口现在会给脚本弹出反爬验证，我们走的是它的
   SPARQL 接口，不受影响。
3. **逐字段比对，带防护。** 比对标题（包括 arXiv 早期版本的标题）、作者（容忍 Reiß/Reis 这类转写
   差异）、年份和发表场所。检索结果只有在足够多字段一致、且没有其他作品同样吻合时才会被采用；已
   知的假冒 DOI 副本会被跳过。
4. **每条文献一个判定**：已核实、元数据不符、标识符冲突、未找到，或带原因的"无法确定"。"未找到"
   要求每个必需来源都明确回答"没有"。
5. **判定过程中没有任何大模型。** 查询结果缓存在本地（SQLite），重复运行很快，`--offline` 也
   能用。

## 设计原则

- **正面确认，否则弃权。** 限流、宕机或未收录，结论都是"无法确定"，绝不是"未找到"。
- **中性措辞。** 只陈述观察（"在 Crossref、dblp 和 Semantic Scholar 中均未找到，且所有来源都已
  正常应答"），不作指控。
- **本地优先，零遥测。** 只把*被引文献*的元数据（DOI、标题、作者）发给上述公开学术接口；你的论文
  正文不会离开你的电脑。

## 我们绝不做的事

帮助规避查重或 AI 文本检测（降重、降 AI 率）、爬取付费墙或反爬保护的网站、凭记忆替你推荐或"补全"
参考文献、点名羞辱作者。

## 路线图

- 已完成：发布到 PyPI（v0.1）；从 `.bbl`、纯文本、PDF 或 arXiv 编号读取参考文献（v0.2）；
  实验性的引用原文查找 `support`（v0.3）；更多智能体可装、由智能体判断的 `support`、在已发表论文的幻觉引用
  上实测召回（v0.4）；没有标题的条目按期刊、卷、页查找，在数据源允许时判断短标题和配上编造作者的真实标题
  （v0.5）；以英译题名引用的中文文献不再被判为"查无此文"（v0.5.2）；复姓、副标题、研讨会论文和图书的
  误报更少（v0.5.3）；速度翻倍，note 里整条写出的参考文献按纯文本读取（v0.6）；Word、Markdown、Quarto、
  R Markdown 和 Typst 稿件，CSL-JSON、RIS 与 YAML 文献库（v0.7）
- 下一步：到各自的登记处核对图书、软件和标准，减少删减作者、编造会议和近似标题的漏报（v0.8）；然后是稳定的 1.0
- 试验中：中文原文参考文献，先测量再决定是否发布

进度见 [docs/PROGRESS.md](docs/PROGRESS.md) 和[更新日志](CHANGELOG.md)。

## 参与贡献

最有价值的贡献是附带可复现 `.bib` 条目的问题报告，尤其是误报。见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

[MIT](LICENSE)。改写自其他项目的代码见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
