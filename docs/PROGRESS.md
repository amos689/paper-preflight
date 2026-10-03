# 进度记录（PROGRESS）

> 每次会话开始先读这里，结束前更新。
> 开发计划见工作区 `plans/paper-preflight 开发计划.md`（不在本仓库内）。

## 当前阶段：W0（2026-10-05 – 10-11）搭建与技术验证

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

### 进行中

- [ ] S1–S5 数据源 API 验证（dblp SPARQL、Crossref、OpenAlex、arXiv/DataCite/doi.org、Semantic Scholar）→ `docs/spikes/`，之后定稿 ADR-0003
- [ ] SARIF 2.1.0 输出

### 待办（W0 剩余）

- [ ] `examples/demo-paper/`：埋入各类问题的示例论文（伪造条目用虚构作者），依据 S1–S5 的实测元数据编写
- [ ] 依据 S1–S5 定稿 ADR-0003（路由与 S2 补救策略）
- [ ] 用户操作：
  - 建 GitHub 组织 `paper-preflight` 与私有仓库
  - 注册 PyPI（2FA）
  - 申请 OpenAlex、S2 免费 key
  - 提供测试邮箱（只放本机环境变量）
- [ ] 推送到 GitHub，确认 CI 全绿

## 已知问题与备忘

- 本机跑测试要加 `--basetemp=.pytest_tmp`：沙箱不允许写系统临时目录。CI 不受影响。
- Windows 保留设备名（aux、con、nul、prn、com1……）不能当文件名，所以模块叫 `auxdata.py`。
- 后台任务运行期间，提交只用显式路径 `git add <path>`，不要用 `git add -A`。
- 在 Claude 应用内运行时，平台缓存目录（`AppData\Local\paper-preflight`）也会被沙箱重定向；在你自己的终端里运行时位置不同，属正常现象。
- 使用 uv 前，Git Bash 中需要：

  ```bash
  export PATH="/c/Users/asus/AppData/Local/Microsoft/WinGet/Packages/astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe:$PATH"
  ```

  新开的终端会自动读到用户级 PATH，不需要这一步。
