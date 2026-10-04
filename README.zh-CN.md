# paper-preflight

[English](README.md) · **简体中文**

[![CI](https://github.com/amos689/paper-preflight/actions/workflows/ci.yml/badge.svg)](https://github.com/amos689/paper-preflight/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.11–3.14](https://img.shields.io/badge/python-3.11%E2%80%933.14-blue.svg)

**投稿前，把 LaTeX 论文的每一条参考文献拿到真实学术数据库里核对一遍。不靠大模型猜，不乱扣"伪造"的帽子。**

![paper-preflight 检查示例论文：未定义的引用键、指向另一篇论文的 DOI、所有数据源都查不到的文献和已撤稿论文报为错误；已正式发表的预印本、错误的年份和带 LaTeX 转义的 DOI 报为警告](https://raw.githubusercontent.com/amos689/paper-preflight/main/docs/demo/demo.gif)

大模型会编造参考文献，复制来的 BibTeX 也常带着错误的年份、作者和失效的 DOI。paper-preflight
读取你的 `.tex` 和 `.bib`，就每一条被引文献去问 Crossref、dblp、arXiv、DataCite、PubMed 和 OpenAlex（配置
了 key 的话还有 Semantic Scholar）：

- 它真的存在吗？
- 和你写的一致吗？
- 撤稿了吗？
- 你引用的预印本后来正式发表了吗？

判断不了的时候，它会直说"无法确定"，而不是去猜。

> **状态：v0.2，早期版本。** 最希望收到的是误报反馈：请
> [提交 issue](https://github.com/amos689/paper-preflight/issues)。

仓库里的[示例论文](examples/demo-paper)引用了 11 篇文献，其中几条是故意写错的。下面是一次真实运行
（直连真实数据源）的完整输出：

```text
$ paper-preflight check examples/demo-paper --lang zh
paper-preflight 0.2.0 · main.tex · 12 条参考文献，12 个被引用的键

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
| CIT001–CIT008 | 引用键未定义、重复、未被引用或疑似重复；`.bib` 语法错误 |
| REF090 | 无法确定，并且一定给出原因（来源不可用、灰色文献等） |

`paper-preflight explain REF003` 可以查看任何一条规则的说明。

## 准确度如何？

三项实测，全部直连真实数据源：真实论文的参考文献、与已发表工具的对比，以及一个公开基准。

### 真实论文

2026 年 7 月的 20 篇 arXiv 论文（cs、stat、q-bio、quant-ph、astro-ph）的参考文献，按固定规则选取，
在本版全部修复之后才收集；每条警告和错误都人工复核过：

| 参考文献 | 报出的问题 | 真问题 | 误报 | 不确定 | 每百条误报 |
|---|---|---|---|---|---|
| 814 | 107 | 92 | 14 | 1 | 1.7 |

- **平均每篇论文不到一次误报**（平均 41 条参考文献），同时报出 92 个真问题：30 个条目本身的错误（作者
  凭空捏造或写错、DOI 和 arXiv 编号不对、标题、年份和会议写错），62 个引用的预印本已经正式发表。
- **误报大多来自登记处自身的记录错误**（标题被弄乱、书评挂在书名下），以及按原样引用 arXiv 早期
  版本的条目。
- **另有三批各 20 篇论文专门用来找误报，** 每批都先如实测过一次（0.1.0：每百条 4.5 个；0.1.1：2.3 个；
  本版最后一轮修复前：3.0 个）。本版在这三批上为 0.1 到 0.7 个。详见
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
| `test_public`：831 条，开发中从未使用 | 任何问题 | 97.9% | 88.9% | 2.6% | 97.0% |
| | 只算伪造 | 99.0% | 49.0% | 0.6% | 97.0% |
| `dev_public`：1119 条，开发中使用 | 任何问题 | 97.6% | 90.7% | 2.1% | 98.4% |
| | 只算伪造 | 98.1% | 52.7% | 1.0% | 98.4% |

HALLMARK v1.2.3 两个公开数据集的全部条目，2026-10-03 运行。"只算伪造"指标识符错误、查无此文、作者
完全对不上；"任何问题"另加作者、标题、年份或发表场所不符。

- **留出测试集印证了开发集的结果：** 在从未用来调整规则的条目上，精确率相同，召回率只低两个百分点。
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

没有 LaTeX？纯文本的参考文献列表也可以检查，支持常见格式（APA、IEEE、ACM、Nature、Vancouver、
Springer、Elsevier、Chicago、MLA），每行一条、每段一条或带编号均可：

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
| `--fail-on warning` | 警告也算失败（默认只有错误算失败） |
| `--lang zh` | 中文输出（也会按系统语言自动选择） |

退出码：

| 退出码 | 含义 |
|---|---|
| 0 | 没有达到 `--fail-on` 级别的发现 |
| 1 | 有阻塞性发现 |
| 2 | 没有阻塞性发现，但有数据源不可用，暂时不能宣称"没问题" |
| 3 | 用法错误 |

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
- `--level unsafe` 还会按记录改写作者、标题、年份和发表场所，并删除指向别的论文的标识符。请先看
  diff 再应用。
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

## 在编码助手里使用

**Claude Code**：安装插件。插件自带 MCP 服务和一个技能：让 Claude 在说"论文完成"之前先核查参考
文献，只修有证据证明错了的地方，绝不编造参考文献。

```bash
claude plugin marketplace add amos689/paper-preflight
```

```bash
claude plugin install paper-preflight@paper-preflight
```

**Codex、Cursor、VS Code 等支持 MCP 的客户端**：运行 `paper-preflight mcp`。工具都是只读的，并且限
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

`paper-preflight doctor` 会显示哪些已经设置，以及每个数据源此刻能否连通。

## 工作原理

1. **源码优先。** 按 LaTeX 的方式读取项目：会跳过注释和 `\iffalse` 块，遵守 `\includeonly`，`.aux`
   文件新鲜时直接采用；键重复时以第一个定义为准，和 BibTeX 一致。
2. **标识符优先的路由。** DOI 交给它的注册机构（由 doi.org 告诉我们是 Crossref、DataCite 还是
   其他）；arXiv 编号交给 arXiv，arXiv 限流时改走 DataCite；PMID 和 PMCID 交给 PubMed（它也会标出已撤稿的
   文章）；没有标识符的条目按标题在 dblp 和 Crossref 中检索。
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

- 已完成：发布到 PyPI（v0.1）；从 `.bbl`、纯文本、PDF 或 arXiv 编号读取参考文献（v0.2）
- 下一步：继续减少误报，每一轮都用新一周的真实论文来衡量
- 之后：中文参考文献

进度见 [docs/PROGRESS.md](docs/PROGRESS.md) 和[更新日志](CHANGELOG.md)。

## 参与贡献

最有价值的贡献是附带可复现 `.bib` 条目的问题报告，尤其是误报。见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

[MIT](LICENSE)。改写自其他项目的代码见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
