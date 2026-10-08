# 进度记录（PROGRESS）

> 每次会话开始先读这里，结束前更新。
> 开发计划见工作区 `plans/paper-preflight 开发计划.md`（不在本仓库内）。

## W0（2026-10-05 – 10-11）搭建与技术验证（提前于 10-03 完成）

### 已完成

- [x] 2026-10-03 计划获批，D1–D9 全部按推荐：名称 paper-preflight，GitHub 组织 `paper-preflight`（开发期私有），MIT 许可，11/10 发布（备选 12/01）
- [x] 开发环境：uv 0.12.22（winget）；Python 3.12.15 装在 `D:\apps\uv\python`
  - 已设用户级环境变量 `UV_PYTHON_INSTALL_DIR=D:\apps\uv\python`
  - 原因：Claude 桌面应用的沙箱会把写入 `AppData` 的文件重定向到应用私有目录
- [x] 仓库脚手架
  - pyproject（hatchling）、src 布局、CLI（`--version`、`doctor`）
  - 测试、ruff、mypy strict
  - CI（3 系统 × Python 3.11–3.14）、pre-commit
  - LICENSE、CONTRIBUTING、SECURITY、CODE_OF_CONDUCT
  - issue 模板（含"误报报告"）、PR 模板
- [x] ADR-0001、0002、0004–0010
- [x] S6 bibtexparser v2、S7 tree-sitter：结论写在 ADR-0010，决定自写 LaTeX 引用分词器

- [x] S8 基准数据集：HALLMARK v1.2.3、Badalova & Mayr、CiteTracer 已下载到 `evals/.data/`，并在 `evals/datasets.lock` 锁定 SHA-256；CiteAudit 只记录 commit。报告见 `docs/spikes/S8-datasets.md`。要点：
  - B&M 的 CSV 是 cp850 编码，有 90 个字符已丢失；"有问题"一栏没有细分，"仅伪造"口径要我们自己细标 33 条
  - HALLMARK 的 14 类中有 10 类是"真论文、错元数据"
- [x] **提前完成 W1 的离线部分**：
  - LaTeX 掩码与引用分词器；项目发现（include 图、`\includeonly`、循环、缺失文件）
  - `.aux`/`.bcf` 读取；`.bib` 解析（行号、宏、拼接、重复键/字段恢复、抑制注释）
  - 标识符抽取（DOI、arXiv、PMID、ISBN/ISSN 校验）
  - 引用键卫生规则 CIT001–008、TEX001–004
  - `paper-preflight check`（终端与 JSON 输出、中英双语、退出码）
  - 共 59 个测试

- [x] S1–S5 数据源验证（`docs/spikes/S1…S5`）→ ADR-0003 定稿：
  - dblp 只用 SPARQL（搜索 API 有反爬墙）
  - Crossref 有 10.65215 假副本，需要黑名单
  - OpenAlex 只作次要来源
  - S2 默认关闭，只在有 key 时启用
  - arXiv 要取各版本标题
- [x] SARIF 2.1.0 输出（用官方 schema 校验）；SQLite 缓存；数据源客户端基座（限流、冷却、来源不可用识别、离线回放）。共 80 个测试
- [x] 示例论文 `examples/demo-paper/`（main.tex、refs.bib、EXPECTED.md）。离线阶段的预期发现已全部命中

### W0 状态：完成

- [x] 2026-10-03 用户决定：
  - 不建组织，仓库放在个人账号下的私有仓库 https://github.com/amos689/paper-preflight
  - 提交邮箱改用 noreply（只在本仓库设置）；用户已在本机执行 filter-branch，14 个历史提交全部改好
- [x] CI 全绿：lint，以及 Linux 4 个 Python 版本、Windows 2 个、macOS 1 个
  - Action 按提交 SHA 锁定，因为 setup-uv 没有 v10 浮动标签
  - 私有期间矩阵已精简；公开后恢复 3 × 4 全矩阵
- [x] 2026-10-03 仓库改为公开；此后每个功能或修复走一个 PR（合并提交），CI 恢复 3 系统 × 4 Python 全矩阵
- [x] 2026-10-03 用户已在本机设好 `PAPER_PREFLIGHT_EMAIL`、`OPENALEX_API_KEY`、`S2_API_KEY`（只在环境变量里），三者都已验证可用
- [ ] 用户（不阻塞开发）：注册 PyPI（2FA），发 0.0.1 占名

## W1–W2：引用核查主干（2026-10-03 完成，提前）

| PR | 内容 |
|---|---|
| #2 | REF017：DOI/arXiv 中的 LaTeX 转义、前缀与格式错误（离线） |
| #3 | 匹配：标题（含副标题、旧版本标题）、作者、年份（不设 ±1 容差）、venue、错配守卫、10.65215 黑名单 |
| #5 | 修复：来源冷却不会被第一次拒绝重置 |
| #6 | 解析器：标识符优先，按来源批量；记录"谁答了没有、谁不可用" |
| #7 | 修复：跨文件重复键时以第一个定义为准 |
| #8 | 判定引擎（ADR-0002）：五种判定 + REF001–005、REF010–015、REF018、REF090、RUN001 |
| #9 | `check` 默认联网核查被引文献；`--offline` 只用缓存；退出码 2；JSON 增加 `verification` 与 `references` |
| #10 | arXiv 拒绝请求时改走 DataCite（`10.48550/arXiv.<id>`） |
| #11 | Semantic Scholar 补救来源（仅有 key 时）；客户端支持 429 指数退避 |

- 共 180 个测试；ruff、mypy strict 全过。测试从不联网：`tests/conftest.py` 把 `check` 指向录制的响应，并清空凭据变量
- 2026-10-03 实跑示例论文（真实来源、空缓存、带 key）：20 秒，运行完整，11 条判定全部符合 `examples/demo-paper/EXPECTED.md`

## W3：评测、集成与分发（2026-10-03，提前）

| PR | 内容 |
|---|---|
| #13 | HALLMARK 评测框架（`evals/run_hallmark.py`）：flag / clean / abstain 三种结果，"仅伪造 / 任一问题"两种口径 |
| #14–#18 | 评测发现的问题：带版本号的 arXiv DOI、转写姓氏、前缀未注册的 DOI、真 DOI 配编造标题、未来年份与被替换的作者 |
| #19 | `doctor` 逐个检查数据源连通性 |
| #20 | MCP 服务（`paper-preflight mcp`，`[mcp]` 附加依赖）：只读、限于工作区、分页 |
| #21 | Claude Code 插件与市场（`plugins/paper-preflight`）：MCP + `paper-preflight` 技能 |
| #22 | pre-commit 钩子（离线版与在线版） |
| #23 | `explain` 命令 |
| #24–#27 | 全量评测发现的问题：dblp 前缀以标点结尾、HTML 实体、复姓与来源错字、标题里的排版标记 |

- 全量评测（dev_public 1119 条）结果见 `evals/results/hallmark-dev_public.md`；人工核实为标签错误的 VALID 条目列在 `evals/hallmark_disputed.toml`，结果另附剔除它们后的表
- 规则：每个误报都要查到根因；是我们的 bug 就单独开 PR 修，是基准标签问题就写进争议清单并附可核查的理由

## W4：取回与修复参考文献、CI 集成（2026-10-03，提前）

| PR | 内容 |
|---|---|
| #30 | 把已核实的记录渲染成 BibTeX（每个字段都来自记录，附出处注释） |
| #31 | `bib fetch`：按 DOI、arXiv 编号或标题取回已核实的 BibTeX；预印本返回正式版并保留 eprint；撤稿警告 |
| #32 | REF016：条目缺 DOI 而记录有时，提示补上（安全修复） |
| #33 | MCP 工具 `preflight_bib_lookup` |
| #34 | `bib fix`：按记录生成修复补丁（safe / unsafe 两级），默认只输出 diff，`--apply` 才写回 |
| #35 | MCP 工具 `preflight_bib_fix`（只返回 diff，不写文件） |
| #36 | GitHub Action（`action.yml`）：任务摘要、SARIF、按 .bib 缓存；自测工作流在 Linux 和 Windows 上实跑演示论文 |
| #37 | 标识符查询按条目缓存：加一条文献后，离线模式下其余条目的判定不再丢失 |
| #39 | REF014 识别编造的会议名（会议名无人认识、且与记录的会议没有共同的词或缩写）：HALLMARK nonexistent_venue 检出率 0% → 61.5%，any_issue 召回率 72.9% → 77.8%，VALID 误报不变 |
| #40 | dblp 的三个批量查询也按条目缓存，离线时新加的预印本不再让其余条目丢失 REF015 |
| #41 | 重新实跑 HALLMARK dev_public，发布新结果（any_issue 精确率 97.2%、召回率 77.8%、F1 86.4%） |

- 2026-10-03 用户最终决定：提交信息不再带 Claude 的 Co-Authored-By 署名，`main` 的历史已由用户改写并强制推送

## W5：召回率攻坚与流水线补全（2026-10-03）

每个 PR 都在 HALLMARK dev_public 全集上对比 main 回放，VALID 误报一条不增。

| PR | 内容 |
|---|---|
| #42 | REF012 识别"只改一两个词"的标题，并在消息里点出改了哪些词（拼写、连字符、"&"、数学符号、RETRACTED 前缀不算）：near_miss_title 46.2% → 78.8% |
| #43 | 会议名录补上 AISTATS、UAI、COLT、WWW 等 16 个；venue 字段里的 URL 不再被当成会议名：wrong_venue 46.8% → 74.5%，preprint_as_published 73.3% → 100% |
| #44 | 编造的会议名只要含有记录会议没有的词就报（缩写、序数词、PMLR 等系列名不算；workshop 仍须完全不相交；只看 booktitle/journal） |
| #45 | 同一已识别会议可作为绑定证据：4–5 个词的标题在同会议同年也能绑定（错作者 → REF010），同会议的年份差不受"重印"限制（REF013） |
| #46 | 只找到"别人写的相似标题"（作者完全不同、标题也不同）时，不再挡住"查无此文"（REF003） |
| #47 | 姓相同、名字却属于另一个人的作者（"Aviral Sharma" 冒充 Archit Sharma）报 REF011；缩写、简称、中间名、连字符、音译、常见昵称不算：swapped_authors 85.1% → 91.0% |
| #48 | CFG001：没有屏蔽掉任何发现的抑制注释会被报出（只在规则确实运行过时判断）；README 补上抑制注释的说明 |
| #49 | `--refresh`（`check`、`bib fetch`、`bib fix`）：忽略本次运行前的缓存，向所有来源重新查询 |
| #50 | 同作者、同会议、同年份、标题只差一两个词的检索结果也能绑定，并由 REF012 点出改动的词 |
| #51 | 重新实跑 HALLMARK：any_issue 精确率 97.6%、召回率 90.5%、F1 93.9%，覆盖率 98.3%；剔除争议标签后 100% 精确、0% 误报 |

## v0.1.0 发布、真实数据评测与 v0.1.1（2026-10-03）

| PR | 内容 |
|---|---|
| #52 | JSON 报告记录每个来源做了什么（请求、缓存命中、否定回答、不可用原因），便于审计和对比 |
| #53 | PubMed 核对 PMID：记录作为锚点，不存在的 PMID 报 REF002，撤稿报 REF004 |
| #54 | PMCID 经 PubMed Central 换成 PMID 再核对 |
| #55 | 通过 GitHub Release 和可信发布（trusted publishing）上传 PyPI，附 PEP 740 证明 |
| #56 | 发布 0.1.0（PyPI 与 GitHub Release） |
| #57 | HALLMARK test_public 保留集结果：any_issue 精确率 97.9%、召回率 88.4%、误报率 2.6% |
| #58–#69 | 真实论文评测（dev 批，20 篇）发现的误报逐类修复：arXiv 早期版本的作者顺序、名字的他国写法与波兰语昵称、写明会议的条目、"Zhang C." 式姓名、Early access 与 12 月出刊的年份、机构作者、预印本年份、弯引号撇号、标题里的标记、同名同作者的另一篇、同姓合作者配对与 Crossref 双文字姓名、无来源收录的网站链接 |
| #70 | 热修复：#62 让 Crossref 的 select 带上了它不接受的 journal-issue，所有 Crossref 请求 400（未发布） |
| #71 | README 顶部加入真实运行的演示 GIF（`docs/demo/make_gif.py` 生成） |
| #72–#73 | Badalova & Mayr 对比中发现的两类误报：dblp 键里的年份、"Gemma Team" 这类团队作者 |
| #74 | 修复 #73 引入的回归：条目里写成 "Team, Chameleon"、"Collaboration, Euclid" 的团队作者（真实论文复跑时发现） |
| #75 | 真实论文评测：两批各 20 篇 arXiv 论文，每条警告和错误人工复核 |
| #76 | 与五个已发表工具对比（Badalova & Mayr 2026） |

真实论文评测（`evals/real_papers.py`，每条警告和错误都人工复核）：

- dev 批（2026-07-01..07 首次提交的 20 篇，924 条参考文献，用于找误报）：0.1.0 每百条 4.5 个误报 → 修复后 0.1 个，真问题 65 个一个不少
- 保留批（2026-07-08..14 的 20 篇，在 dev 批引出的修复之后收集，结果原样报告）：921 条参考文献，109 个报警，84 个真问题（28 个条目错误、56 个已发表的预印本），21 个误报，每百条 2.3 个（门槛 G3：≤3，通过）；无法确定 6%（G4 通过）。误报主要是无来源收录的真实作品（REF003）和同名相关出版物的记录（REF011/REF013），留待下一批新论文验证后再改

与已发表工具对比（Badalova & Mayr 2026，104 条人工核对的参考文献）：按研究的标注，精确率 69.2% [53.6%, 81.4%]、召回率 81.8%、每百条正确文献误报 16.9；五个工具中最好的 50.9% [38.3%, 63.4%]（门槛 G2：区间下限 > 0.51，通过）。第一次运行为 62.8%，之后修了在这份数据里发现的两类误报（#72、#73/#74）

HALLMARK 用最终代码重跑：dev_public 与 test_public 的结论与 0.1.0 完全相同（any_issue 精确率 97.6% / 97.9%，误报率 2.1% / 2.6%）

## v0.1.2（2026-10-04）：真实论文上的误报继续减少

| PR | 内容 |
|---|---|
| #78–#80 | 误报博物馆（真实条目回放测试）、实时冒烟 CI（每周 + 改动数据源查询的 PR） |
| #81–#86 | OLD_WORK（1990 年前）、同名的其他出版物与其他类型、按版本比较、标题杂质 |
| #87–#91 | 期刊名比较（B1）、长标题合并版本后绑定（B2）、dblp 批量查询（冷启动 140 s → 52 s）、进度显示 |
| #93 | 第三批真实论文（07-15..21，保留集）：每百条误报 3.0，未达门槛 1.5；用户决定先修再发 |
| #94–#98 | 修第三批暴露的误报：SICI DOI、团队/联盟/名字拆分、登记处标题杂质与 Springer 章节、卷年份与会议年份、研讨会论文/匿名投稿/1990 年代章节弃权、书的 DOI 用在章节上、研讨会版本 |
| #99 | 第四批真实论文（07-22..28，新保留集） |

评测（main 43a5544）：

- 第四批（保留集，修复全部合并后才收集）：814 条参考文献、107 个报警、92 个真问题、14 个误报，每百条 1.7（门槛 ≤1.5，差 2 个，在统计误差内）；无法确定 3%。用户决定按实发布 0.1.2
- 前三批（用于找误报）：dev 0.1、heldout 0.7、heldout2 0.4（原样测得 3.0）
- Badalova & Mayr：精确率 72.5% [57.2%, 83.9%]，召回率 87.9%
- HALLMARK test_public any_issue：精确率 97.9%、误报率 2.6%（不变），召回率 88.9%

## v0.2.0（2026-10-04）：不需要 .bib 也能检查

| PR | 内容 |
|---|---|
| #92 | D1：项目没有 `.bib` 时读取编译生成的 `.bbl`（biblatex、natbib、IEEEtran、LNCS、Elsevier、AAS 等）；6 篇论文上与 `.bib` 结论一致 91% |
| #101 | D2：`check references.txt` / `check -` 读取纯文本参考文献列表；Badalova & Mayr 104 条：标题 103、第一作者 103、年份 104、标识符 48/48 与人工转录一致，实时核查 102/104 结论一致 |
| #102 | D3：`check paper.pdf`（`[pdf]` 扩展，pypdf）；dev 批 20 篇 PDF：找到 .bib 中 88% 的文献，其中 92% 结论一致 |
| #103 | D4：`check arxiv:<id>` 下载源码到临时目录、检查后删除 |

## v0.2.1（2026-10-04）：第四批误报的修复

| PR | 内容 |
|---|---|
| #105 | A1：arXiv 每个版本的标题和作者都取回（批量，每次请求 50 个版本），条目与最贴合的版本比较；旧式编号（astro-ph/0501436）不取（API 报 500）；取版本失败时只标记离最新版很远的条目 |
| #106 | A2：`@book` 条目不再绑定到期刊里同名的书评（不超过四页的期刊文章） |
| #107 | A3：登记处标题杂质：罗马数字与阿拉伯数字、末词上的脚注数字、单字母量后丢失的符号、"(with Discussion)" |
| #108 | A4：昵称 Gary/Garrison；只在网上发表的出处（Transformer Circuits Thread、LessWrong、AI Alignment Forum、The Gradient）查不到时判"无法确定" |
| #109 | A5：源码没有 `\bibliography` 时，回退使用主文件旁唯一的 `.bib`（仍报 CIT005） |
| #110 | E1：第五批（heldout4）复核与各项回放 |

评测（第五批 heldout4，2026-07-29..08-04，修复全部合并后才收集）：

- 1005 条参考文献、88 个报警、66 个真问题、19 个误报、3 个不确定，每百条 1.9（门槛 ≤1.5，未达到；0.2.0 在同一批上 2.1）；无法确定 6%。用户决定按实发布 0.2.1
- 19 个误报：名字写法 8（不带点的缩写 JR/DR、后缀 IV ×3、Danny/Daniel、Peter/Xi Chen、Zhitao/Rex Ying）、登记处记录 4、标题字段写成"章节, in 书名" 2、年份 3（书被绑定到重印章节、JMLR 卷年、ACM Just Accepted）、机构排第一作者 1、只在 OpenReview 的投稿 1
- 前四批：dev 0.1、heldout 0.7、heldout2 0.4、heldout3 0.4（原样测得 1.7，其误报已用于本版开发）
- HALLMARK test_public any_issue：精确率 98.1%、误报率 2.2%（原 2.6%），召回率 88.9%；Badalova & Mayr 不变

## v0.3.0（2026-10-05）：实验性的引用原文查找 `support`，第五批误报的修复

| PR | 内容 |
|---|---|
| #112–#114 | 第五批误报的修复：不带点的缩写（JR）、后缀 IV、Danny/Daniel、"… Research" 机构不算第一作者、`\texttt` 等命令里的标题文字、标题字段写成"章节, in 书名"、dblp 标题里的 TeX、书不绑定到重印章节、多卷书的卷号、JMLR 卷年 |
| #115 | S1：每处引用所在的句子和它要支撑的说法（LaTeX 转纯文本、分句、分从句、`[cited work]` 占位） |
| #116 | S2/S3：取被引文献的文本（arXiv 源码/PDF → Europe PMC 全文 → 开放获取 PDF → 摘要），BM25 段落排序（数字优先，摘要始终保留） |
| #117 | S4/S5：`support` 命令；本地核验模型 HHEM（默认）、MiniCheck、FactCG；只说"已确认（附原文）"或"未能确认（附原因）"，从不说引用有误；金标集与评测 |
| #118 | S1 修正：`\cite` 作名词或句子主语时也用占位符；句号后的引用归前一句 |

评测：

- 金标集（`evals/support_gold.toml`）：55 篇 CC 许可的 arXiv 论文、298 对（250 处真实引用 + 48 处故意替换的错引）；标签全部由 AI 给出（Sonnet、Opus 两人标注，Fable 处理分歧，再裁决并抽检 20%），不是专家标注
- HHEM、前 4 段、阈值 0.4：说"已确认"35 次，97% 正确 [85%, 99%]，确认了 12% 的真实引用，没有确认任何错引。读更多段落能多确认几处，但正确率降到 89–92%
- 不判"不支持"：得分低的引用真是错引的只有 23–45%（集中还放了错引）；真实论文里错引只占约 3%
- 第五批（修复针对它做的，属开发数据）：19 个误报剩 6 个，每百条 0.6；66 个真问题全部仍报出

## v0.4.0（2026-10-05）：第四轮"发布就绪"

第四轮计划见工作区 `plans/paper-preflight 第四轮改进计划.md`（2026-10-05 批准，全部按推荐）。

| PR | 内容 |
|---|---|
| #120 | R6：技能可用 `npx skills add` / `gh skill install` 装进 Codex、Gemini CLI、Copilot、Cursor 等；README 注明 dblp 走 SPARQL（搜索接口已被 Anubis 封锁） |
| #121 | R1：Hugging Face Space 试用页（`space/`）与发布时自动同步的工作流；需用户建 Space 并设置 `HF_SPACE`、`HF_TOKEN` |
| #122 | R3：第六批 heldout5（0.3.0 保留集）：每百条 1.9 |
| #123 | R2：GPTZero 公布的 151 条幻觉引用：报出 129 条，判为核实 0 条 |
| #124 | R5：MCP 工具 `preflight_cited_passages`（智能体当裁判）；名字核对（"Adam \cite{x}"） |
| #125 | R4：纯文本读取修复；GPTZero 135/151 |
| #126–#128 | 第六批误报修复：登记处记录格式、名字写法、去掉副标题的检索；第六批 20 个误报剩 3 个 |
| #129 | 智能体当裁判的评测：100 对中确认 39% 的真实引用（HHEM 9%），确认全部至少部分成立 |
| #130 | 第七批 heldout6（0.4.0 保留集）：753 条、77 个真问题、9 个误报，每百条 1.2（达到 1.5 门槛） |

尝试后放弃的改动：
- 对"没写期刊/会议的 @article"按灰色文献处理：会去掉 3 个误报，但损失 19 个 HALLMARK 检出；
- 允许四人中有一个异常名字：会让 APS 格式把标题读成作者。

## 0.4.1 打磨（2026-10-07）

| PR | 内容 |
|---|---|
| #132 | 演示 GIF 按 0.4.0 重新生成 |
| #133 | logo、徽章和居中的 README 头部（中英文）；PyPI 上的 README 改用 GitHub 绝对链接 |
| #134 | MCP 工具参数全部补上说明（Glama TDQS：参数说明覆盖率原为 0%）；README 去掉"已有在线试用页"的不实描述 |
| #135 | README 头部改成 Markdown，Glama（会去掉 HTML）上也能显示 logo；一份浅色、深色背景都能看清的 logo |
| #136 | arXiv 未应答而 DataCite 已核实时，运行不再判为不完整（新增提示 RUN002）；REF015、REF016 在文字报告中合并成一行，`--details` 逐条查看 |

另外：Glama 已收录（Dockerfile 构建、评分 A），awesome-LaTeX#130 和 awesome-mcp-servers#15891 已提交；Hugging Face Space 因 Gradio/Docker Space 需付费而暂不做。

## 第五轮：英文召回与覆盖，中文做实验（2026-10-07 起）

计划见工作区 `plans/paper-preflight 第五轮开发方案.md`（2026-10-07 定）。用户的决定：英文优先；中文参考文献只做实验验证，不进发布包；.docx 输入放 11 月；不访问知网解析页。目标：10/31 前发 0.5.0。

| PR | 内容 |
|---|---|
| #138 | 基线：HALLMARK 用 0.4.1 重测（test 任何问题召回 89.1%，其余不变）；冻结第八批 heldout7（2026-08-19..25）的名单，本轮改动完成前不跑 |
| #139 | E1：没有标题的期刊条目按期刊、卷、首页查 Crossref（首作者须一致）；七批开发数据回放，71 条从无法确定变为已核实，报警无增减；第七批无法确定 15.4% → 6.4% |
| #140 | E6：第七批 9 个误报修掉 7 个（姓在前的缩写人名、登记库人名里的单位标记、数据库按访问年份、IEEE 提前在线年份、dblp 合卷的研讨会、Substack 与写成别的类型的技术报告）；回放无其他变化；HALLMARK test 误报率 2.2% → 1.9%。登记库标题里的拼写错误（Probelm、Biopolymer）不修：容忍它们会漏掉更多条目自己的拼写错误 |
| #141 | E5：纯文本读取器认得带小写成分的名字（"Yun chen Chen"），但只在规范人名占多数、且小写词不是 on/of 之类虚词时；GPTZero 135 → 136；Badalova & Mayr 字段一致不变；开发集 PDF 找到 815 → 818 条 |
| #142 | E7：`bib fix` 不再把 REF017 的提示语（"(correct the arXiv ID)" 等）当作值写进文件（安全级也会写，属实际 bug）；Zotero 导出的 "2311.07911 [cs]" 修复为纯编号。S2 CorpusID 作标识符不做：开发数据里只有 10 个 .bib 用到，且这些条目靠标题已能找到 |
| #143 | E2：同一作品的两条记录标题只差连字符或空格（SoftMatch 的预印本与 ICLR 版）时算一篇，不再判"有歧义"；真实题名配编造作者因此报 REF010。七批回放无变化；HALLMARK test 召回 89.1% → 89.4%，误报率不变；GPTZero 136 → 137。只署一个人名的条目（iclr 24）仍不判：机构署名（"Meta AI"）会因此误报 |
| #144 | E3：三四个词的短题名，在 dblp 完整收录的会议或期刊、过去的年份、所有来源都答"没有"时，可以判查无此文；若找到的标题以它开头（真实论文被截短引用，如 GPTZero 第 14 条）仍弃权。七批回放无变化；GPTZero 137 → 139；HALLMARK test 伪造口径召回 49.3% → 50.2%，误报率不变 |
| #145 | 第八批 heldout7（0.5.0 保留集，只跑一次）：962 条、53 个报警、41 个真问题、10 个误报、2 个不确定，每百条 1.0（门槛 1.5，通过）。E4 不改：作者被删几位已有提示级 REF011，升为警告会误报 |
| #146 | 0.5.0 发布准备：版本号、CHANGELOG、README（heldout7 每百条 1.0；GPTZero 139/151；HALLMARK test 伪造口径召回 50.2%、误报率 1.9%）、路线图 |

0.5.0 已于 2026-10-07 发布到 PyPI 与 MCP Registry（用户确认、设备授权）。

## 0.5.1：heldout7 的误报（2026-10-07 起）

| PR | 内容 |
|---|---|
| #147 | 冻结第九批 heldout8（2026-08-26..09-01）的名单，修复完成前不跑 |
| #148 | heldout7 的 10 个误报修掉 8 个：作者只在所有同作品记录都缺时才算缺（DataCite、KISTI 记录不全，arXiv 记录完整）；团队署名与记录里的长名配对，"Contributors" 算群体；软件按 Zenodo 发行版的仓库名比对；截短的标题按作者绑到它所截的那篇，报 REF012。英文名、登记库乱码不修。八批回放：去掉 8 个误报，新增 2 个正确的 REF012，丢掉 2 个原判"不确定"；HALLMARK、GPTZero 不变 |
| #149 | 第九批 heldout8（#148 的保留集，只跑一次）：780 条、101 个报警、81 个真问题、19 个误报、1 个不确定，每百条 2.4，**未过 1.5 的门槛**；19 个误报均非 #148 引入（同人异名 4、Error Correction Zoo 页面 4、真实作品查无 4、标题后加数据集名 2、会议名写法 2、登记库作者不全 1、名字里的 \ifmmode 1、MNRAS 卷年 1）。冻结第十批 heldout9（2026-09-02..08）的名单 |
| #150 | 合规：知网 DOI 不再做内容协商（doi.org 会跳到 robots 禁止的 chndoi.org，0.4.x/0.5.0 会跟过去）；中文实验 X1 发现 |
| #151 | 0.5.1 发布：#148 与 #150；README 并列 heldout7（0.5.0，1.0）与 heldout8（0.5.1，2.4）（用户 2026-10-07 决定先发） |

0.5.1 已于 2026-10-07 发布到 PyPI 与 MCP Registry。

## 0.5.2：heldout8 的误报、英文形式的中文文献（2026-10-07 起）

| PR | 内容 |
|---|---|
| #152 | heldout8 的 19 个误报修掉 11 个：副标题前半段 5 个词即可、截短标题按作者绑到更长的记录（这类记录与候选分开存放，不造成歧义、不挡 S2 兜底）、标题后附的数据集名、中间名的昵称、`\ifmmode`、联合会议与 SIG 通讯、Black Hat、MNRAS 12 月在线、登记库标题里的脚注。九批回放：去掉 11 个误报，无新增报警，3 条无法确定变为核实；HALLMARK、GPTZero 不变 |
| #153 | 英文形式的中文文献（中文实验 X1）：新模块 `chinese.py` 识别（括号里的 "(in Chinese)"、note 里的标记、language 字段、约 60 个中文刊英文名、拼音刊名），查不到时弃权（`TRANSLATED_CHINESE_WORK`）；比较标题前去掉标记；中文与拉丁文字标题互为译名记"未知"；英译题名措辞不同只报提示；对这类条目按中文刊 Crossref 记录的怪癖比作者；含汉字即视为中文；中文刊 DOI 里的年份；URL 中 DOI 末尾的 "/"；doiRA 每批 6 个。X1 开发数据：至少一个报警的条目 63/235 → 19/235；九批英文回放、HALLMARK、GPTZero 均不变 |
| #154 | REF002 必须经 Handle API 的"不存在"（代码 100）确认：doiRA 在句柄服务器不应答（代码 2）时也说"不存在"（中文实验 X3：ISTIC 的 DOI 一小时后又能解析）。九批回放、HALLMARK（伪造 DOI 仍 100%）、GPTZero 不变；博物馆 4 个 REF002 案例补录 Handle 回答 |
| #155 | 第十批 heldout9（0.5.2 的保留集，只跑一次）：975 条、48 个报警、31 个真问题、13 个误报、4 个不确定，每百条 1.3（门槛 1.5，通过）。冻结第十一批 heldout10（2026-09-09..15）的名单 |
| #156 | 0.5.2 发布：#152–#154；README 加 heldout9（0.5.2，1.3）一行与路线图；HALLMARK、GPTZero 用最终代码重跑（不变）（用户 2026-10-08 确认） |

0.5.2 已于 2026-10-08 发布到 PyPI 与 MCP Registry。

## 0.5.3：heldout9 的误报（2026-10-08 起）

| PR | 内容 |
|---|---|
| #157 | heldout9 的 13 个误报修掉 11 个：复姓只引第一部分（dblp 的 Sabela Ramos Garea，两部分都要 ≥4 个字母）；"Laboratory/Laboratories/Institute" 结尾算群体署名；"Paul Ralph et al." 写成一个名字时算截断；Crossref 检索结果连同其单独存放的副标题比较（Field Methods 的 "How Many Interviews Are Enough?"），只靠副标题找到的记录不挡 S2 兜底（MIT Press 2010 年重印的 Marr《Vision》）；workshop 论文与晚一年的 arXiv 版本；9 月及以后印刷的书算下一年（Cover & Thomas 第 2 版、GPML）；dblp 的 "HECKTOR@MICCAI"；法律评论、"Open Review"、journal 字段里的网址。不修：MNRAS 11 月印刷算下一年（11 月印刷也常是当年的期，改了会坏既有测试）、报告写成 @article。十批回放：去掉 11 个误报和 1 个"不确定"，另有 10 本书由"无法确定"变为核实，无新增报警 |
| #158 | 第十一批 heldout10（#157 的保留集，只跑一次）：1067 条、98 个报警、83 个真问题、14 个误报、1 个不确定，每百条 1.3（门槛 1.5，通过）。误报：ACM 的 10.5555 网址 2、KDD 写成 "&" 2、把预印本库（IACR ePrint、ECCC）当正式发表 2、登记库标题乱码与斜体标记 2、记录作者不全（dblp 的 MUC-7、arXiv 宕机时 DataCite 只有最新版）2、Russ Salakhutdinov 1、书的上线日期（Nielsen & Chuang）1、ePrint 版与会议版的年份 1、标题里的字面花括号 1。另：一篇论文（2609.10121v2）把整条引用写在 @misc 的 note 里，46 条全部弃权。冻结第十二批 heldout11（2026-09-16..22）的名单 |
| #159 | 0.5.3 发布：#157；README 加 heldout10（0.5.3，1.3）一行与路线图；HALLMARK、GPTZero 用 0.5.3 重跑（不变）；补上 CHANGELOG 0.4.1–0.5.3 的比较链接（用户 2026-10-08 确认） |

0.5.3 已于 2026-10-08 发布到 PyPI 与 MCP Registry。

## 第六轮：到 1.0 的长期方案（2026-10-08 批准）

方案见工作区 `plans/paper-preflight 第六轮长期开发方案.md`。用户的决定：不做中文文献、不做宣发；P1–P6 全部按建议执行，过闸门后自行发版，按版本汇报，中间不逐步请示。四个阶段：A 0.6（精度、健壮性、速度、发布自动化）、B 0.7（Word、Typst、Markdown、RIS、CSL-JSON）、C 0.8（灰色文献、作者删减、会议、近似标题）、D 1.0（稳定化）。

### 阶段 A：0.6.0（10/09–10/22）

| PR | 内容 |
|---|---|
| #160 | A1、A2：heldout10 的 14 个误报解决 12 个（11 个不再报，1 个改为指出正确的正式版本）：ACM 10.5555 网址、"&"、IACR ePrint/ECCC 不算正式发表（含 ePrint 版与会议版年份）、登记处乱码与 `\fontshape`、arXiv 宕机时对 DataCite 最新版的作者比较降为提示、Russ/Ruslan、标题里的字面花括号；引用期刊卷页时与预印本标题的差异降为提示。note 里写整条引用的 @misc 按纯文本读出（2609.10121v2：46 条弃权 → 37 条核实）；纯文本读取支持尖括号链接、"de Sá" 这类小写词缀、两句式标题、括号里的年份。十一批回放：去掉 11 个误报，新增 2 个真问题（标题后缀年份）；HALLMARK 两个划分逐条不变，GPTZero 不变，Badalova & Mayr 纯文本字段一致率不变；博物馆加 9 例 |
| #161 | A4、A5、A3：提速与发布自动化。Crossref 礼貌池按其应答头宣布的配额（每秒 3 次、并发 3）请求，任何数据源宣布更严的配额时立即放慢；S2 兜底不再等全部标题检索结束，某条目的 dblp 与 Crossref 都答完就问。冷缓存 75 条的论文：66 秒 → 32 秒（每条 0.89 → 0.43 秒），十一批回放结果不变。release.yml 加 MCP Registry 发布（GitHub OIDC，钉住 mcp-publisher v1.8.1 并校验 SHA256），发版不再需要设备码；`scripts/bump_version.py` 一次改完所有版本号并开 CHANGELOG 小节，测试同时检查 space 的版本。A3 熔断原已有（失败后冷却 10 分钟），不另做 |
| #162 | A6：`evals/replay.py`（逐批回放并与基线比较，带复核结论）与 `evals/review_list.py`（未复核的报警清单）进仓库，evals/README 写明改动的检验方法 |
| #163 | 第十二批 heldout11（0.6.0 的保留集，只跑一次）：868 条、89 个报警、76 个真问题、13 个误报、0 个不确定，每百条 1.50，**恰在 1.5 的门槛上**（初判 14 个误报、1.6；ADS 的 'Santos, João F. C., Jr.' 按博物馆 real-1991rc3-corwin 的先例改判为真问题：BibTeX 会把 'Jr.' 当名字。因改判发生在看到结果之后，0.6.0 仍在 heldout12 上再测一次）。实跑每条 0.48 秒（heldout10 是 1.22）。误报：登记处记录自身的错误 8（作者不全、名字拼错或写成 'Prof.'、HTML 实体、AAS 的 [CSC] 标记、标题错字、BLEU 记成 2001、剑桥 2012 的上线日期）、无索引的真实作品 2、章节与重印本 1、期刊改名 1、拿 arXiv 作者表代替期刊版 1。另：dblp 把两篇 ACL Findings 2024 记成 2014（REF015 文字里的年份错）。冻结第十三批 heldout12（2026-09-23..29）|
| #164 | heldout11 的 13 个误报修掉 5 个（另修 heldout10 的 nielsen-chuang）：mEDRA 名字里的 HTML 实体、登记处把 'Prof.'/'Dr.' 当名字、AAS 的 [CSC] 标记、剑桥 Books Online 只有上线日期的书不比年份、一份记录写错名字而作品的另一份记录（含 OpenAlex 对该 DOI 的记录）写对时不报、dblp 的年份在键与 DOI 一致反驳时更正；'Jr.' 被 BibTeX 当成名字时 REF011 说明原因。十二批回放：去掉 6 个误报和 1 个不确定，无新增；HALLMARK 两个划分逐条不变，GPTZero 不变；博物馆加 5 例。不修：登记处作者不全/拼错、标题错字、年份错、无索引的真实作品、重印本、期刊改名 |
| #165 | 第十三批 heldout12（0.6.0 含 #164 的保留集，只跑一次）：786 条、48 个报警、42 个真问题、6 个误报、0 个不确定，**每百条 0.8（门槛 1.5、目标 1.0 均通过）**；实跑每条 0.47 秒。误报：arXiv 自身标题错字、1988 年的书配 2013 年电子版 DOI、在线优先记录（卷 0）对正式期年份、登记处标题省掉期刊栏目名、两个软件引用带所有者与版本号。冻结第十四批 heldout13（2026-09-30..10-06）|
| #166 | 0.6.0 发布：#160–#162、#164；README 加 heldout11（0.6.0 候选，1.5）与 heldout12（0.6.0，0.8）两行、路线图；HALLMARK、GPTZero 用 0.6.0 重跑（不变）；首次由 release.yml 的 GitHub OIDC 发布到 MCP Registry |

### 阶段 B：0.7.0（输入扩展）

| PR | 内容 |
|---|---|
| #167 | B1–B4：Word（.docx）稿件、Markdown/Quarto/R Markdown/Pandoc 与 Typst 项目、CSL-JSON/RIS/YAML（Hayagriva、CSL YAML）文献库。Word 先读文献管理器的域代码（Zotero、Mendeley 的 CSL-JSON，EndNote 的 XML，含 base64 的 EN.CITE.DATA），再读 Word 自带的源管理器，最后读"References/参考文献"标题之后手打的列表（遇表格、图注、下一节停止），只用标准库。Quarto 书按 `_quarto.yml` 列出的章节（含分部、子目录和 include），bookdown 书按 `rmd_files`。合成一致性（开发批 20 篇、924 条，citeproc-py 渲染）：域代码判定一致 99.6%，APA 94.0%、IEEE 96.9%、NLM 96.0%（门槛 98% 与 90%）。真实稿件：Zenodo 的 12 份 .docx、3 篇 JOSS 论文（paper.md）、mlr3book（Quarto 书）、TMwR（bookdown 书）、egwalker 论文（Typst＋Hayagriva），引用键与 grep 逐一核对一致；真实导出的 3 份 RIS、4 份 CSL-JSON、1 份 Hayagriva 全部读出。跨格式测试：同样三条文献写成 .bib、CSL-JSON、CSL YAML、RIS、Hayagriva、Word 域代码，读出的标题、作者、年份、出处、类型、标识符完全一致。真实样例发现并修好：Quarto 书只读了首章、Typst 包导入 `@preview/...` 被当成引用、出版社页面网址里 DOI 后带路径被当成另一个 DOI（REF002 错误）、登记处人名乱码（"DuÅ¡ica"）、同一本书的不同章节共用书的 DOI 被报重复（CIT004）、APA 的 "Hassen, A. et al."、"Dada, O. (L.)"、地名冒号前有空格。纯文本：NLM 的分部标题（"Dust. IV. The ..."）、年份取卷号前的（不取 arXiv 编号或页码）、协作组作者、"ten"/"ter" 词缀、A–Z 以外的大写字母与首字母。十三批回放：判定与报警逐条不变；HALLMARK 两个划分逐条不变，GPTZero 不变，PDF 判定一致 756/820（92%，原 749/814），Badalova & Mayr 纯文本标题 104/104 |
| #168 | 第十四批 heldout13（0.7.0 的保留集，#167 的代码，只跑一次）：1,014 条、89 个报警、79 个真问题、7 个误报、3 个不确定，**每百条 0.7（门槛 1.5、目标 1.0 均通过）**；实跑每条 0.43 秒。误报：Crossref 只有在线日期的三篇（AMS 两篇、CiCP 一篇，引用的是卷年）、2007 年的书对 2009 年的电子版、两处登记处的符号写法（TeX 标记的 ℓ、ADS 的 M sub sun）、把论文在 Zenodo 上的代码当成论文的正式版本。不确定：两篇 arXiv 与会议记录作者表不同、一处 ADS 与 Crossref 标题不同。heldout14（10-07..10-13）要等这一周过完、arXiv 公布后再冻结 |
| #169 | 0.7.0 发布：#167、#168；README 加 heldout13（0.7.0，0.7）一行、路线图；HALLMARK、GPTZero 用 0.7.0 重跑（不变）|

### 阶段 C：0.8.0（召回与覆盖）

| PR | 内容 |
|---|---|
| #170 | heldout13 的 7 个误报全部修掉（另修 heldout3、heldout12 各一个）：Crossref 只有在线日期的文章差一年时，取一次完整记录，用期号自带的日期（AMS 两篇、CiCP 一篇）；出版社后补的图书记录（DOI 比书的日期晚两年以上注册）可能带着后来印次的日期和作者顺序，条目年份更早、作者相同只顺序不同时不报，且只在没有别的记录对得上时才选它（Bhatia 2007、Paley–Wiener），随书注册的记录照旧（Gravity 2014 仍报 2012）；IEEE 标题里的 `<tex-math>` 标签、太阳质量的写法（M sub sun / M(solar)）、普林斯顿的丛书编号 (PMS-30)；DataCite 与 dblp 的软件、数据记录（论文代码的 Zenodo 存档）不再当成预印本的正式版本。十四批回放：去掉 8 个误报和 1 个不确定，新增 1 个真问题（作者写了两遍），13 本经典图书由无法确定变为核实；HALLMARK 两个划分逐条不变，GPTZero 不变，实跑冒烟通过；博物馆加 11 例 |
| #171 | C8、C3：太新的条目（今年或明年、还没有任何来源收录）记在本地缓存里，之后每次运行每天重查一次标题检索，`check --recheck` 立即重查；评测脚本关掉这一机制（`remember_too_new=False`），回放照旧只用缓存。RFC 按编号核实：`type={RFC}, number=…`、"RFC 791"、rfc-editor.org/IETF 链接都换成 RFC Editor 在 Crossref 注册的 DOI（10.17487/rfc791，Crossref 不补零）|
| #172 | C1：没有 DOI 的图书用 Open Library 核实（每秒 1 次、缓存；有联系邮箱时写进 User-Agent）。只问其他来源都没找到的图书条目，按 ISBN 或书名＋第一作者检索，书名、作者和某一版次的年份都对得上才采用，对不上的记录放一边、从不拿来指错。十四批回放：原先无法判断的 102 本书中 48 本变为核实（Pearl 1988、Cormen 2022、Misner–Thorne–Wheeler 1973……），报警无增无减；演示论文的 Deep Learning 由无法确定变为核实；`doctor` 检查 Open Library 是否应答 |
| #173 | C2：引用软件时，用 GitHub 仓库、PyPI、CRAN（经 R-hub 的 crandb）核实：只问链接到仓库或软件包、其他来源都没找到的条目；仓库或软件包存在，且它的名字或描述就是条目标题时判为核实，不比作者和年份（软件按版本引用，所有者是账号）；链接的仓库或软件包不存在时报新规则 REF019（提示）。GitHub 无令牌每小时 60 次，有 `GITHUB_TOKEN` 时 5,000 次。十四批回放：47 条软件引用由无法确定变为核实（smolagents、TRL、Alpaca、aider……），报警无增无减，没有出现 REF019 |
| #174 | C6、C7、C5：只找到预印本、又没有正式版本的作品，条目写的期刊或会议在 OpenAlex、dblp、Crossref 的目录里都查不到时报 REF020（警告）；带届次、缩写、年份或 Proceedings 的场所不查（真实的研讨会也不在目录里），COLM 加入已知会议。arXiv 自己的记录知道论文全部版本的标题时，即使比对的是 DataCite 的记录也报换词（REF012）。作者中间被删的人在提示里点名，仍为提示。HALLMARK dev：编造会议 71.8%→94.9%、近似标题 86.5%→94.2%，真实条目误报不变；十四批回放：第一版新增 18 个 REF020 全是误报（13 个 COLM、5 个真实研讨会），收窄后只新增 1 个真问题（标题错字 heterrogeneous）|
| #175 | D1（提前做）：JSON 报告的 JSON Schema（`docs/schema/check-report.schema.json`，`schema_version` 0.1），测试用它校验在线、离线、不核查三种报告；README 写明字段只增不删、退出码 4（内部错误）。校验当即发现 schema 草稿里 `build_data` 的类型写错（实际是文件名或 null）。`schema_version` 到 1.0 时再改为 1.0 |
| #176 | D2（提前做）：项目设置文件 `paper-preflight.toml` 或 `pyproject.toml` 的 `[tool.paper-preflight]`，从被检查的路径向上找到仓库根，也可用 `--config` 指定：忽略规则、忽略条目（可用通配符）、调整严重级别、关闭可选来源（核心来源不能关）、`fail-on`；命令行优先；写错（未知规则、设置项、来源）一律报错，退出码 3；MCP 服务同样读取 |
| #177 | D3（提前做）：Python API `paper_preflight.check_paper(path)`，返回简单、不可变的数据类（Report、Reference、MatchedRecord、Finding），选项与命令行一致（是否联网、缓存、项目设置、语言），`report.to_dict()` 即 JSON 报告；包的 `__init__` 延迟导入，命令行启动不受影响。函数名不用 `check`：它会被同名的内部模块 `paper_preflight.check` 遮住。文档 docs/python-api.md |
| #178 | C4：网页链接。其他来源都没找到、链接到未收录网站的条目，用 HEAD 请求检查链接（说页面不在时再用不读正文的 GET 确认，Kaggle 这类对 HEAD 回 404、对 GET 回 200 的网站因此不误报），返回 404/410 且 Wayback Machine 从未存档时报 REF021（提示）；401/403/429/5xx/超时一律不下结论；不访问本机和内网地址。十四批回放：280 篇论文里 5 处，警告和错误无增无减 |
| #179 | D4：`bib fix --level unsafe` 修 REF015，把已正式发表的预印本改引正式版本：条目类型改为正式版本的类型（`@misc` 改 `@inproceedings`），按记录写入发表场所、年份、卷（期刊）、页码和 DOI，只写着 arXiv preprint 的 journal/booktitle/howpublished 删掉，保留 eprint；记录没说是哪种出版物（期刊文章、会议论文、书的章节）时不修。新增的字段与条目原有字段的等号对齐。演示论文的 ResNet 预印本应用修复后再查，不再报 REF015 |
| #180 | D6：性能收尾。冷缓存实测（heldout13 的 4 篇论文，每篇各用空缓存，含阶段 C 新增的 Open Library、GitHub、场所目录、网页链接查询）：209 条 93 秒，每条 0.44 秒，达到 ≤0.6 秒的目标（最慢一篇 0.62 秒）。GitHub Action 的缓存改为每次运行都保存：先取同一参考文献表（.bib 或 .bbl）最近的缓存，没有就取任意最近的缓存；原先参考文献表不变时永远复用第一次的缓存，之后过期的答案和当时太新的条目每次运行都要重查 |
| #181 | D5（第一部分）：每条规则一页说明（`docs/rules/`，中英文）：检查什么、什么时候可能误报、怎么处理、怎样消除；内容写在 `guides.py`，`explain`、MCP 的 `preflight_explain`、SARIF 报告的帮助文本（GitHub 代码扫描里显示）与这些页面同源，`scripts/rule_docs.py` 生成页面，测试保证页面与源同步、每条规则都有中英文说明。顺带修好：SARIF 报告里每条规则的帮助链接原先指向不存在的 `docs/rules/<规则>.md`。README 的规则表补上 REF018–REF021 |
| #182 | 修回归：0.7.0（#167）为“同一本书的两章可共用书的 DOI”加的豁免太宽，只要两个条目都有 booktitle、标题不同就不报 CIT004，演示论文里 BERT 条目借用 ResNet 的 DOI 因此不再报出（EXPECTED.md 写着应报，但没有测试守住）。改为两个条目的 booktitle 必须相同才算同一本书的章节。新增测试：演示论文 EXPECTED.md 的每条离线行都必须成立。十四批回放：CIT004 无增无减 |
| #183 | D5（第二部分）：用户手册 `docs/README.md`（安装、各用途对应的页面、判定方式），新增 `docs/inputs.md`（各种输入格式）、`docs/configuration.md`（逐条目消除、项目设置、`check` 的选项、退出码、输出格式、环境变量、缓存及各类答复的保留时间）、`docs/false-positives.md`（误报从何而来、怎么处理、哪些不算误报，中英文）、`docs/sources.md`（每个来源问什么、不做什么、接入新来源的七个步骤）；测试检查 README、CONTRIBUTING 和 docs 下所有页面的相对链接和标题锚点都存在。顺带更正过时的说明：README 的状态行（v0.4）、MCP 文档里“等首个 PyPI 版本”、pre-commit 示例的 `rev: main`、CONTRIBUTING 的 pre-alpha、web.py 里“只发 HEAD 请求”。另写兼容性约定 `docs/stability.md`（D1 的“1.0 之后遵守语义化版本”）：从 1.0 起，规则编号、退出码、JSON schema、命令行、设置项、Python API、MCP 工具只在大版本中做不兼容的改动；判定结果、措辞、严重度可以在任何版本中改进 |
| #184 | `NCBI_API_KEY` 真正用上：`doctor` 一直列出它，但 PubMed 从未带着它查询；有 key 时 PMID、PMCID 按每秒 10 次查询（原为 3 次）。key 按 NCBI 的要求放在查询参数里，不进入缓存键，测试确认缓存文件里没有它；`doctor` 显示是否带 key。README 中英文凭据表补上这一行 |
| #185 | `explain --lang zh` 的严重度和修复级别也显示中文（原先仍是 warning、unsafe 等英文），规则列表同样 |
| #186 | C5 收窄（为升级成警告做准备）：开发集 280 篇里“漏掉列表中间的某某”提示共 46 条，其中 19 条点名的并不是人：登记机构把单位当成作者（Qassim University、Ural Federal University、Sandia National Laboratories、Austrian Research Institute……）、占位名（Paper Authors、(Primary Paper Contributors)）、合作组（DESI Collaboration、SciPy 1.0 Contributors、The Cancer Genome Atlas Research Network）、单名，以及上百人的合作组长列表（200/1140、485/486）。现在这些不再点名，超过 30 人的列表也不点名；仍是提示，升级与否看 heldout14 |
| #187 | 覆盖（1.0 目标“无法确定 ≤4%”）：链接到 Hugging Face 模型或数据集、OpenML 数据集、其他来源都没找到的条目，像软件一样核实：仓库或数据集存在、名字就是条目标题即判为核实。OpenML 答复“Unknown dataset”时报 REF019；Hugging Face 对不存在和私有仓库都答 401，所以从不报。可选来源 `huggingface`、`openml`，`doctor` 探测二者。十四批回放（补查）：29 条由无法确定变为核实（Hub 23 条：FLUX.1-dev、Qwen3.5-9B、DAPO-Math-17K、Nemotron-CC-v2……；OpenML 6 条），逐条核对无误，报警无增无减；280 篇的“无法确定”由 4.24% 降到 4.02%。灰色文献弃权由阶段 C 前的 502 条降到 380 条，其中 245 条是网页（按 C4 设计不判真伪），网页以外由 188 条降到 135 条 |
| #188 | 冻结三个留出批次（经你同意，用 7 月以前从未抽过的周代替等待新周）：heldout14（2026-06-24..30，1,638 个条目）、heldout15（06-17..23，1,784 个）、heldout16（06-10..16，3,564 个），各 20 篇，同一抽样脚本和学科配额，在 #170–#187 全部合并之后、任何一批运行之前提交名单。与以往各批、彼此之间都不重复；和以往一样，arXiv 的日期筛选会带进少数编号在后几个月的论文（heldout14 4 篇、heldout15 2 篇）；heldout16 的 2606.13475 曾在 support 实验里作为被引文献读过正文，参考文献从未用于调规则，照常保留。这些论文是几个月后才查，被引作品收录更全，误报和弃权可能略偏乐观，所以 10-07..13 的新周仍会作为对照。用法：heldout14 测 0.8.0；后两批测之后的改动；三批与新周一起作为 1.0 的精度依据 |
| #189 | heldout14（2026-06-24..30，0.8.0 的留出批次，main 5e048db，只跑一次）：1,127 条、143 个报警、132 个真问题、10 个误报、1 个不确定，**每百条 0.9（门槛 1.5、目标 1.0）**，实跑每条 0.43 秒，无法确定 3%。真问题：93 个已发表的预印本、17 个写成链接的标识符、10 个条目作者或名字错（有的整串名字都是编的）、6 个错年份、2 个标题引错、1 个错会议、1 个不存在的 DOI、1 个指向别篇的 arXiv 编号、1 个作者栏写成“iang et al.”。误报：登记机构自己的写法 6 个（标题丢了“3/4”、章节号“Chapter 1”、Ueber/Foerster 与 Über/Förster、dblp 漏一位作者、Bas 即 Sebastiaan Kooijman），手写的作者栏 3 个（“and 324 others”“Black et al.”、以 OpenAI 署名而 arXiv 列的是个人），未被索引的 ITU-R 报告 1 个。每个报警都人工复核 |
| #190 | 发布 0.8.0（阶段 C 与 D 的大部分）：heldout14 每百条 0.9；HALLMARK test 任何问题召回 93.5%、误报率 1.9%（0.7.0：90.3%），编造会议 97%（78%）、近似标题 85%（70%），dev 召回 94.3%、误报率 2.1%（11 条有争议的标签不变）；GPTZero 139/151、核实 0 条，不变；冷缓存每条 0.43 秒。README 的演示输出用 0.8.0 实跑刷新（原先还是 0.4.0：Deep Learning 现由 Open Library 确认，CIT004 恢复），真实论文表加 heldout14 一行并注明是更早的一周，HALLMARK 表、路线图更新 |
| #191 | GPTZero 召回 139→**142/151**（1.0 目标 ≥142），核实 0 条：一位有名有姓的人引用至少 8 个词、唯一对应他人作品的标题时，按作者全错绑定（REF010；书不适用，书评和后续版本常用同一书名，回放时 Koza 的书被绑到 Biosystems 上的书评，已排除）；标题被截短、第一作者对、只有预印本被收录、条目年份在预印本之后两年内时，绑定该预印本，报标题截短（REF012）和其他合著者（REF011）；没有发表场所也没有链接的 @misc（纯文本里没读出出处的条目）也查 dblp；dblp 标题检索把“Q &A”读作“Q&A”。300 篇回放（含 heldout14）：报警无增无减；HALLMARK dev 不变 |
| #192 | heldout15（2026-06-17..23，0.8.0 加 #191 的留出批次，main 35dcdb0，只跑一次）：1,093 条、136 个报警、96 个真问题、**39 个误报、每百条 3.6，未过 1.5 的门槛**，1 个不确定；每条 0.54 秒，无法确定 5%。误报都不来自 #191：自己的 bug 6 个（以括号结尾的 ASCE DOI 被截掉“)”，再被判为不存在和写法错误）；物理与天文 16 个（合作组论文按前几位作者引用、同位素写法 $^{13}$CO/CO-13、ADS 条目引用 arXiv 预印本却被拿去比期刊版、登记处把名字写坏/顺序颠倒/改名、按中文题名收录的论文、会议年份）；年份 4 个（Crossref 只给在线日期）；研讨会版本、会议别名、按作者要求引用的软件与数据集、报告、标题里的版次、韩文罗马字、译名 13 个。按规则：一批不过就研究并修复，用 heldout16 衡量；连续两批不过才停下来 |

## 下一步

- [x] 0.5.2：修 heldout8 的误报类型＋中文实验 X1 的英译中文文献误报，heldout9 每百条 1.3。中文 MVP 暂缓（用户决定）
- [x] heldout10 跑一次：每百条 1.3，过门槛（#158）
- [x] 0.5.3 发布（#159，用户 2026-10-08 确认）
- [x] 第六轮阶段 A（0.6.0，#160–#166）：heldout11 每百条 1.5、heldout12 每百条 0.8；实跑每条约 0.47 秒；发版自动化（MCP Registry 走 GitHub OIDC，不再需要设备码）
- [x] 第六轮阶段 B（0.7.0，#167–#169）：Word、Markdown/Quarto/R Markdown、Typst、CSL-JSON/RIS/YAML；.docx 合成一致性 99.6%/94.0%/96.9%/96.0%；heldout13 每百条 0.7
- [ ] heldout14（10-07..10-13）：这一周过完、arXiv 公布后冻结，作为阶段 C 的保留集；heldout13 的 7 个误报（Crossref 只有在线日期的卷年、书的电子版日期、登记处的符号写法、Zenodo 上的代码被当成正式版本）在阶段 C 处理
- [ ] 阶段 C（0.8.0）、阶段 D（1.0）：见 `plans/paper-preflight 第六轮长期开发方案.md`
- 宣发不在本轮范围内（用户决定）；awesome-mcp-servers、awesome-LaTeX 的 PR 保持开着

## 已知问题与备忘

- 本机跑测试要加 `--basetemp=.pytest_tmp`：沙箱不允许写系统临时目录。CI 不受影响。
- Windows 保留设备名（aux、con、nul、prn、com1……）不能当文件名，所以模块叫 `auxdata.py`。
- 后台任务运行期间，提交只用显式路径 `git add <path>`，不要用 `git add -A`。
- arXiv API 常限流（429 或超时）。#10 之后会自动改走 DataCite；0.4.1 起，DataCite 已核实的条目不再让运行判为不完整，改由 RUN002 提示撤回状态这次没查。
- S2 key 的条款：所有接口合计每秒不超过 1 次。适配器按 1.1 秒间隔单连接请求；同时开两个进程会共用 key，可能合计超限。
- 叠放的 PR：合并父 PR 之前，先用 `gh pr edit <子PR> --base main` 转走，否则删分支会把子 PR 关掉且无法重开
- 实跑验证时用临时缓存：设 `PAPER_PREFLIGHT_CACHE_DIR` 指向草稿目录，避免污染真实缓存；不要打印凭据的值。
- 在 Claude 应用内运行时，平台缓存目录（`AppData\Local\paper-preflight`）也会被沙箱重定向；在你自己的终端里运行时位置不同，属正常现象。
- 使用 uv 前，Git Bash 中需要：

  ```bash
  export PATH="/c/Users/asus/AppData/Local/Microsoft/WinGet/Packages/astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe:$PATH"
  ```

  新开的终端会自动读到用户级 PATH，不需要这一步。
