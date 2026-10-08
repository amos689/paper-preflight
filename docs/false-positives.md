# When a finding is wrong · 误报的原因与处理

[English](#english) · [中文](#中文)

## English

paper-preflight reports a problem only when a record backs it, or when every source that could
know a work answered that it does not. Even so, about one flag in ten on real papers is a false
alarm: on the latest held-out week, 7 false alarms against 79 real problems in 1,014 references
(0.7 per 100 references; the README has [every week](../README.md#on-real-papers)). This page
says where they come from and what to do.

### Where false alarms come from

1. **The registry is wrong.** Most false alarms are records with errors of their own: an author
   list that stops short, a misspelt name, a year that is the online date rather than the
   issue's, a symbol written the registry's own way. paper-preflight compares every record it
   reached for a work before reporting a name missing, and knows several registries' habits,
   but cannot know them all.
2. **Versions.** Titles, author lists and years change between a preprint and its publication,
   and between a book's editions and printings. Every known version is compared; a version no
   source holds is not.
3. **Translations and transliterations.** A work in another language cited by a translated
   title, or names transliterated differently. Translated titles of Chinese-language works are
   recognised and never called "not found"; non-Latin titles are not judged at all yet.
4. **Works the indexes miss.** Theses, reports, workshop papers, very new and very old works,
   regional journals. paper-preflight abstains on the kinds it knows ("cannot determine", with
   the reason); a real work outside them can still be reported not found (REF003).
5. **A title garbled beyond recognition**, or a reference read wrongly from plain text or a PDF,
   where formatting has to be guessed.

### What to do

1. **Read the rule's page.** Every finding names its rule; [its page](rules/README.md), or
   `paper-preflight explain <RULE>`, says when it can be wrong.
2. **Check against the source.** Open the DOI or the record the message names. When the entry
   is right and the record wrong, the finding is a false alarm.
3. **Silence it, with the reason,** above the entry:
   `% preflight: ignore[REF013] reason="Crossref has the online date"`. For a rule that does
   not suit the project, use [the settings](configuration.md#project-settings).
4. **Report it.** False positives are the bugs we most want to hear about: open
   [an issue](https://github.com/amos689/paper-preflight/issues/new/choose) with the "False
   positive" template, the BibTeX entry and the finding. Most fixed false alarms started as one
   example.

### What is never a false alarm

- **"Cannot determine"** (REF090) is an abstention, not a judgement. Its reason tells what was
  left unchecked.
- **An outage** never makes a reference "not found": the run is reported incomplete instead
  (RUN001, exit code 2).

## 中文

只有当某条记录能作为依据，或所有可能收录该作品的来源都答复“没有”时，paper-preflight 才会报告问题。
即便如此，在真实论文上大约每十个报警中有一个是误报：在最近一周的留出集上，1,014 条参考文献中有 79
个真问题、7 个误报（每百条 0.7 个；每周的结果见 [README](../README.zh-CN.md)）。本页说明误报从何而来、
遇到时怎么办。

### 误报从何而来

1. **登记机构的记录本身有误。** 多数误报来自记录自己的错误：作者列表不全、姓名拼错、年份用的是在线
   发表日期而不是期号日期、符号按登记机构自己的方式书写。paper-preflight 在报告缺少某位作者之前，
   会比对该作品能找到的所有记录，也掌握若干登记机构的习惯，但不可能全部掌握。
2. **版本差异。** 预印本与正式版本之间、图书不同版次与印次之间，标题、作者和年份都可能变化。
   所有已知版本都会参与比较；没有任何来源收录的版本则无法比较。
3. **翻译与音译。** 以译名引用的其他语言作品，或音译不同的姓名。以英译题名引用的中文文献会被识别，
   不会被判为“查无此文”；非拉丁文字的标题目前暂不判定。
4. **索引漏收的作品。** 学位论文、报告、研讨会论文、很新或很早的作品、地区性期刊。对已知会漏收的
   类型，paper-preflight 会放弃判断（“无法确定”，并给出原因）；不在这些类型中的真实作品，仍可能被报
   为查无此文（REF003）。
5. **标题错得面目全非**，或从纯文本、PDF 中读取参考文献时格式猜错。

### 怎么处理

1. **阅读规则说明。** 每条报告都注明了规则编号；[规则说明页](rules/README.md)或
   `paper-preflight explain <规则>` 会说明它什么时候可能误报。
2. **对照来源核对。** 打开消息中给出的 DOI 或记录。如果条目正确而记录有误，这就是误报。
3. **注明原因后消除，** 在条目上方加注释：
   `% preflight: ignore[REF013] reason="Crossref 记录的是在线日期"`。如果某条规则不适合整个项目，
   请使用[项目设置](configuration.md#project-settings)。
4. **提交 issue。** 误报是我们最想知道的问题：请用 “False positive” 模板
   [提交 issue](https://github.com/amos689/paper-preflight/issues/new/choose)，附上 BibTeX 条目和
   报告内容。大多数已修复的误报，都始于用户提供的一个例子。

### 这些不算误报

- **“无法确定”**（REF090）是放弃判断，而不是结论。其中的原因说明了哪些地方没有被检查。
- **来源故障** 永远不会让文献变成“查无此文”：这时运行会被标记为不完整（RUN001，退出码 2）。
