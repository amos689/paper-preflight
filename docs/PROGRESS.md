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

## 下一步

- [ ] 真实论文保留批暴露的误报（需用新的一周论文来验证修复）：无来源收录的老论文与报告（REF003，可考虑按年代或类型弃权）；同名的相关出版物（学位论文摘要、技术报告）被当成所引的那篇（REF013）；同一 DOI 在不同来源的年份取并集（dblp 与 ACM/Crossref）；登记处标题里的杂质（"[Review Article]"、U+FFFD 乱码、Zenodo 的 "org/repo: vX"）
- [ ] 召回率：只有预印本记录的论文上编造/错误的会议名（需要会议名录或已发表版本的会议）；只漏掉部分作者的作者列表（partial_author_list）
- [ ] Crossref 不可用时，用 S2 批量接口按 DOI/arXiv 兜底（需要客户端支持 POST）
- [ ] REF019（条目类型不符）：噪声大（大量 NeurIPS 论文被写成 @article），需先想清楚只报哪些强矛盾
- [ ] 运行清单（run manifest）；`--final`、`--record/--replay`
- [ ] CI 里用 `claude plugin validate --strict` 校验插件清单（需要在 CI 装 Claude Code CLI）
- [ ] 需要用户操作：MCP Registry 发布新版本（`mcp-publisher login github` 后 `mcp-publisher publish`）；投稿 awesome 列表

## 已知问题与备忘

- 本机跑测试要加 `--basetemp=.pytest_tmp`：沙箱不允许写系统临时目录。CI 不受影响。
- Windows 保留设备名（aux、con、nul、prn、com1……）不能当文件名，所以模块叫 `auxdata.py`。
- 后台任务运行期间，提交只用显式路径 `git add <path>`，不要用 `git add -A`。
- arXiv API 常限流（429 或超时）。#10 之后会自动改走 DataCite，但报告仍会注明 arXiv 不可用（撤回状态只有 arXiv 知道）。
- S2 key 的条款：所有接口合计每秒不超过 1 次。适配器按 1.1 秒间隔单连接请求；同时开两个进程会共用 key，可能合计超限。
- 叠放的 PR：合并父 PR 之前，先用 `gh pr edit <子PR> --base main` 转走，否则删分支会把子 PR 关掉且无法重开
- 实跑验证时用临时缓存：设 `PAPER_PREFLIGHT_CACHE_DIR` 指向草稿目录，避免污染真实缓存；不要打印凭据的值。
- 在 Claude 应用内运行时，平台缓存目录（`AppData\Local\paper-preflight`）也会被沙箱重定向；在你自己的终端里运行时位置不同，属正常现象。
- 使用 uv 前，Git Bash 中需要：

  ```bash
  export PATH="/c/Users/asus/AppData/Local/Microsoft/WinGet/Packages/astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe:$PATH"
  ```

  新开的终端会自动读到用户级 PATH，不需要这一步。
