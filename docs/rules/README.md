# Rules · 规则

<!-- Written by scripts/rule_docs.py: edit src/paper_preflight/rules.py and guides.py. -->

Every finding names its rule. `paper-preflight explain <RULE>` prints the same page in the terminal. Rules can be silenced for one entry with `% preflight: ignore[RULE] reason="..."` above it, or for the whole project in [the project's settings](../../README.md#project-settings).

每条报告都注明了规则编号。`paper-preflight explain <规则>` 会在终端里显示同样的说明。可以在条目上方加 `% preflight: ignore[规则] reason="..."` 对单个条目消除某条规则，也可以在[项目设置](../../README.zh-CN.md#项目设置)中对整个项目关闭。

## Reference verification · 文献核查

| Rule | Severity | Finding | 说明 |
|---|---|---|---|
| [REF001](REF001.md) | error | Identifier points to a different work | 标识符指向另一篇作品 |
| [REF002](REF002.md) | error | Identifier does not exist | 标识符不存在 |
| [REF003](REF003.md) | error | Reference not found in any source | 所有来源均未找到该文献 |
| [REF004](REF004.md) | error | Cited work has been retracted | 被引作品已撤稿 |
| [REF005](REF005.md) | warning | Expression of concern or correction | 关注声明或更正 |
| [REF010](REF010.md) | error | Author list is entirely different | 作者列表完全不同 |
| [REF011](REF011.md) | warning | Author list differs | 作者列表部分不同 |
| [REF012](REF012.md) | warning | Title differs from the record | 标题与记录不符 |
| [REF013](REF013.md) | warning | Year differs from the record | 年份与记录不符 |
| [REF014](REF014.md) | warning | Venue differs from the record | 发表场所与记录不符 |
| [REF015](REF015.md) | warning | Preprint has been formally published | 预印本已正式发表 |
| [REF016](REF016.md) | info | A DOI can be added | 可以补充 DOI |
| [REF017](REF017.md) | warning | Identifier written incorrectly | 标识符写法错误 |
| [REF018](REF018.md) | warning | arXiv preprint withdrawn | arXiv 预印本已撤回 |
| [REF019](REF019.md) | info | Linked repository or package not found | 链接的代码仓库或软件包不存在 |
| [REF020](REF020.md) | warning | Venue not found in any catalogue | 发表场所查无此处 |
| [REF021](REF021.md) | info | Linked page gone, with no archived copy | 链接的网页已失效且没有存档 |
| [REF090](REF090.md) | info | Reference could not be verified | 无法核实该文献 |

## Citation keys and the bibliography · 引用键与参考文献文件

| Rule | Severity | Finding | 说明 |
|---|---|---|---|
| [CIT001](CIT001.md) | error | Cited key is not defined | 被引用的键未定义 |
| [CIT002](CIT002.md) | error | Entry key defined twice | 条目键重复定义 |
| [CIT003](CIT003.md) | info | Entry is never cited | 条目未被引用 |
| [CIT004](CIT004.md) | warning | Two entries look like the same work | 两个条目疑似同一篇文献 |
| [CIT005](CIT005.md) | error | Bibliography file missing or unreadable | 参考文献文件缺失或无法读取 |
| [CIT006](CIT006.md) | info | Entry lacks required fields | 条目缺少必填字段 |
| [CIT007](CIT007.md) | error | BibTeX syntax error | BibTeX 语法错误 |
| [CIT008](CIT008.md) | warning | Field appears twice in an entry | 条目中字段重复 |

## LaTeX project structure · LaTeX 项目结构

| Rule | Severity | Finding | 说明 |
|---|---|---|---|
| [TEX001](TEX001.md) | warning | Included file not found | 找不到被包含的文件 |
| [TEX002](TEX002.md) | warning | Include cycle | 文件循环包含 |
| [TEX003](TEX003.md) | info | Remote bibliography not checked | 远程参考文献未检查 |
| [TEX004](TEX004.md) | warning | Source file could not be read | 源文件无法读取 |

## The run · 运行状态

| Rule | Severity | Finding | 说明 |
|---|---|---|---|
| [RUN001](RUN001.md) | warning | Run incomplete: some sources were unavailable | 运行不完整：部分来源不可用 |
| [RUN002](RUN002.md) | info | Checked through a substitute source | 已改用替代来源核查 |

## Configuration · 配置

| Rule | Severity | Finding | 说明 |
|---|---|---|---|
| [CFG001](CFG001.md) | info | Suppression comment had no effect | 抑制注释未生效 |
