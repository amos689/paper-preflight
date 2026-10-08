"""What each rule checks, when it can be wrong, and what to do about a finding.

One source for `explain`, the MCP server's `preflight_explain`, the help text of SARIF reports
and the pages in docs/rules/ (written from this module by scripts/rule_docs.py; a test keeps
them in step). Every rule in rules.RULES has a guide.
"""

from __future__ import annotations

from dataclasses import dataclass

from paper_preflight.findings import Message


@dataclass(frozen=True)
class Guide:
    checks: Message  # what the rule looks at, and how
    wrong: Message  # when a finding can be wrong
    action: Message  # what to do about it


def _guide(checks: tuple[str, str], wrong: tuple[str, str], action: tuple[str, str]) -> Guide:
    return Guide(Message(*checks), Message(*wrong), Message(*action))


_NONE_KNOWN = (
    "No case is known. If you meet one, please report it: false positives are the bugs we most "
    "want to hear about.",
    "目前没有已知的情形。如果遇到，请提交 issue：误报是我们最想知道的问题。",
)

GUIDES: dict[str, Guide] = {
    "CIT001": _guide(
        ("A key used in a citation command (`\\cite` and its natbib and biblatex variants, "
         "`\\nocite`; `--cite-command` adds your own macros) that no entry of the project's "
         "bibliographies defines. When the build's `.aux` or `.bbl` is there, the keys LaTeX "
         "actually cited are used. LaTeX prints \"?\" or the bare key in their place.",
         "引用命令（`\\cite` 及其 natbib、biblatex 变体，以及 `\\nocite`；"
         "可用 `--cite-command` 加上自定义宏）里用到、但项目的参考文献中没有任何条目定义的键。"
         "存在编译生成的 `.aux` 或 `.bbl` 时，以 LaTeX 实际引用的键为准。LaTeX 会在这些位置印出“?”"
         "或键名本身。"),
        ("The entry is in a bibliography that was not found: a `.bib` named through a macro, "
         "loaded outside the main file, or a remote one (TEX003). A citation macro "
         "paper-preflight does not know can also hide keys.",
         "条目所在的参考文献没有被找到：通过宏给出文件名的 `.bib`、在主文件之外加载的文件，"
         "或远程参考文献（TEX003）。paper-preflight 不认识的引用宏也可能让键被漏读。"),
        ("Add the entry, or correct the key's spelling. A `.bib` kept elsewhere is passed with "
         "`--bib`; a main file guessed wrong is named with `--main`.",
         "补上条目，或改正键的拼写。放在别处的 `.bib` 用 `--bib` 传入；"
         "主文件判断错误时用 `--main` 指定。"),
    ),
    "CIT002": _guide(
        ("The same entry key defined twice, in one `.bib` file or in two. BibTeX keeps the first "
         "and ignores the other, so a citation may print another work than the one you edited.",
         "同一个条目键被定义了两次（在同一个或两个 `.bib` 文件中）。BibTeX 只保留第一个、"
         "忽略另一个，所以引用印出的可能不是你修改过的那一条。"),
        ("Two bibliographies that are never loaded together (one per build) share keys "
         "legitimately.",
         "两个从不同时加载的参考文献文件（各用于一种编译）共用键名是正常的。"),
        ("Delete one copy, or rename it and update the citations that meant it. When the copies "
         "differ, keep the one `check` verifies.",
         "删掉其中一份，或给它改名并更新原本指向它的引用。两份内容不同时，"
         "保留 `check` 核实通过的那份。"),
    ),
    "CIT003": _guide(
        ("An entry no citation uses. Reported when a manuscript is checked, not a bibliography "
         "on its own, and not when `\\nocite{*}` includes every entry.",
         "没有被任何引用用到的条目。只在检查稿件时报告（单独检查参考文献文件时不报）；"
         "使用 `\\nocite{*}` 收录全部条目时也不报。"),
        ("The entry is cited through a macro paper-preflight does not know (add it with "
         "`--cite-command`), or the `.bib` is shared by several papers.",
         "条目是通过 paper-preflight 不认识的宏引用的（用 `--cite-command` 加上），"
         "或者这个 `.bib` 由多篇论文共用。"),
        ("Nothing is wrong with the paper. Delete the entry if it is a leftover; for a shared "
         "bibliography, turn the rule off in the project's settings: "
         "`ignore-rules = [\"CIT003\"]`.",
         "论文本身没有问题。如果是遗留条目就删掉；共用的参考文献可以在项目设置中关闭此规则："
         "`ignore-rules = [\"CIT003\"]`。"),
    ),
    "CIT004": _guide(
        ("Two entries with different keys that share a DOI, an arXiv ID, or their title and year "
         "(titles of four words or more). The paper then cites one work twice, under two numbers.",
         "两个键不同的条目有相同的 DOI、arXiv 编号，或相同的标题和年份（标题至少四个词）。"
         "这样论文会以两个编号重复引用同一篇作品。"),
        ("Two chapters of one book that both carry the book's DOI are told apart by their titles "
         "and not reported. A paper and its erratum, or a two-part work published in one year "
         "under one title, are real pairs.",
         "同一本书的两个章节都带着书的 DOI 时，会按章节标题区分开，不会报告。论文与它的勘误、"
         "同一年以同一标题发表的上下两部分，是确实存在的成对条目。"),
        ("Keep one entry and point the other's citations to it. If the two really are different "
         "works, silence it above either entry: `% preflight: ignore[CIT004]`.",
         "保留一个条目，把另一个的引用改为指向它。如果两者确实是不同的作品，"
         "在任一条目上方加注释消除：`% preflight: ignore[CIT004]`。"),
    ),
    "CIT005": _guide(
        ("A bibliography named by `\\bibliography`, `\\addbibresource` or `--bib` that does not "
         "exist or cannot be read. None of its entries is checked, and LaTeX will not find them "
         "either.",
         "`\\bibliography`、`\\addbibresource` 或 `--bib` 指定的参考文献文件不存在或无法读取。"
         "其中的条目都没有被检查，LaTeX 同样找不到它们。"),
        ("The file is made by a build step that has not run yet, or its path is built by a "
         "macro.",
         "该文件由尚未运行的编译步骤生成，或者它的路径是由宏拼出来的。"),
        ("Correct the path or create the file. A generated bibliography is checked after the "
         "build, or passed with `--bib`.",
         "改正路径或补上文件。生成的参考文献文件可以在编译之后再检查，或用 `--bib` 传入。"),
    ),
    "CIT006": _guide(
        ("An entry without a field its type requires in BibTeX or biblatex: an `@article` "
         "without `journal`, an `@inproceedings` without `booktitle`, any entry without `year` "
         "or `date`. The style may print an incomplete reference.",
         "条目缺少其类型在 BibTeX 或 biblatex 中要求的字段：`@article` 没有 `journal`，"
         "`@inproceedings` 没有 `booktitle`，或任何条目没有 `year`/`date`。"
         "参考文献样式可能印出不完整的条目。"),
        ("Styles differ in what they need, and biblatex alternatives count (`journaltitle`, "
         "`date`; an editor for a book). `@misc` has no required fields.",
         "不同样式的要求不同；biblatex 的替代字段同样有效（`journaltitle`、`date`；"
         "图书可以只有编者）。`@misc` 没有必填字段。"),
        ("Add the field, or change the entry type to what the work is. "
         "`paper-preflight bib fetch <DOI or arXiv ID>` gives the complete entry from the record.",
         "补上字段，或把条目类型改成作品实际的类型。`paper-preflight bib fetch <DOI 或 arXiv 编号"
         ">` "
         "可以按记录给出完整的条目。"),
    ),
    "CIT007": _guide(
        ("An entry the BibTeX parser cannot read: unbalanced braces, a missing comma or quote. "
         "It is skipped, and BibTeX may skip it too or swallow the next entry.",
         "BibTeX 解析器无法读取的条目：花括号不配对、缺少逗号或引号。该条目会被跳过，"
         "BibTeX 也可能跳过它，或把下一个条目一并吞掉。"),
        ("The parser follows BibTeX's grammar; a construct only biber accepts may be reported.",
         "解析器遵循 BibTeX 的语法；只有 biber 接受的写法可能被报告。"),
        ("Fix the syntax at the line given. If biber reads the entry and you build with biber, "
         "please report it.",
         "在给出的行号处修正语法。如果 biber 能读取该条目且你用 biber 编译，请提交 issue。"),
    ),
    "CIT008": _guide(
        ("A field given twice in one entry (two `year` or two `doi` fields). Only the first "
         "counts, which may not be the one you corrected.",
         "同一条目中一个字段出现了两次（两个 `year` 或两个 `doi`）。只有第一个生效，"
         "而它未必是你改正过的那个。"),
        _NONE_KNOWN,
        ("Delete the copy you do not mean.", "删掉你不需要的那一份。"),
    ),
    "TEX001": _guide(
        ("`\\input`, `\\include` or `\\subfile` names a file that is not there. The citations in "
         "it are not checked.",
         "`\\input`、`\\include` 或 `\\subfile` 指向的文件不存在。其中的引用没有被检查。"),
        ("The file is generated during the build, or its path depends on a macro paper-preflight "
         "does not expand.",
         "该文件在编译过程中生成，或者它的路径依赖 paper-preflight 不展开的宏。"),
        ("Correct the path. For a generated file, check after the build or ignore the finding.",
         "改正路径。生成的文件可以在编译之后再检查，或忽略这条提示。"),
    ),
    "TEX002": _guide(
        ("A file that includes itself, directly or through other files. LaTeX would loop; "
         "paper-preflight reads each file once.",
         "某个文件直接或间接地包含了它自己。LaTeX 会陷入循环；paper-preflight 每个文件只读一次。"),
        ("A conditional around the `\\input` (`\\ifdefined`, a flag) is not evaluated: the cycle "
         "may never happen in a real build.",
         "`\\input` 外面的条件判断（`\\ifdefined`、开关变量）不会被求值："
         "实际编译时这个循环可能根本不会发生。"),
        ("Remove the recursive include, or ignore the finding if a condition prevents it.",
         "去掉递归的包含；如果条件判断会阻止它，可以忽略这条提示。"),
    ),
    "TEX003": _guide(
        ("`\\addbibresource[location=remote]{https://...}`: bibliographies are not downloaded, so "
         "its entries are not checked.",
         "`\\addbibresource[location=remote]{https://...}`：远程参考文献不会被下载，"
         "因此其中的条目没有被检查。"),
        _NONE_KNOWN,
        ("Download the bibliography and pass it with `--bib` to have it checked.",
         "下载该参考文献文件，用 `--bib` 传入即可检查。"),
    ),
    "TEX004": _guide(
        ("A source file that could not be opened: no permission, a broken link, a file another "
         "program holds. Its citations are not checked.",
         "无法打开的源文件：没有权限、链接已损坏，或文件被其他程序占用。其中的引用没有被检查。"),
        _NONE_KNOWN,
        ("Fix the file's permissions or path, then check again.",
         "修正文件的权限或路径后重新检查。"),
    ),
    "CFG001": _guide(
        ("A `% preflight: ignore[RULE]` comment that silenced nothing on its entry: the problem "
         "was fixed since, or the rule name is misspelt. Reported only once the rule has run on "
         "the entry; reference rules need a complete online run.",
         "`% preflight: ignore[规则]` 注释没有消除该条目的任何报告：问题已经改好，"
         "或者规则名拼错了。只有在该规则确实对这个条目运行过之后才报告；"
         "文献核查类规则需要一次完整的联网运行。"),
        ("A source that stopped holding a record can make a reference rule fall silent for a "
         "run.",
         "某个来源不再收录某条记录时，文献核查类规则可能在这次运行中没有触发。"),
        ("Delete the comment, or the rule from it.", "删掉这条注释，或从中删去该规则。"),
    ),
    "REF001": _guide(
        ("The entry's DOI, arXiv ID, PMID or PMCID resolves to a record whose title and authors "
         "are another work's, and no other source confirms the identifier for this entry. "
         "Typical of a pasted wrong DOI, and of invented references, which often borrow a real "
         "identifier.",
         "条目的 DOI、arXiv 编号、PMID 或 PMCID 指向的记录，标题和作者都属于另一篇作品，"
         "且没有其他来源能证实该标识符属于这个条目。常见于复制错的 DOI，"
         "也常见于编造的文献——它们往往借用真实存在的标识符。"),
        ("A registry's record can itself be wrong (a DOI deposited with another work's metadata). "
         "A book's DOI given for one of its chapters is accepted when the `booktitle` names the "
         "book.",
         "登记机构的记录本身也可能有误（DOI 登记时填了另一篇作品的元数据）。"
         "为书中某一章给出整本书的 DOI 时，只要 `booktitle` 写的就是这本书，就不会报告。"),
        ("Open the identifier and compare. `bib fix --level unsafe` removes it; "
         "`paper-preflight bib fetch --title \"...\"` finds the right one.",
         "打开该标识符的页面核对。`bib fix --level unsafe` 会删除它；`paper-preflight bib fetch --t"
         "itle \"...\"` 可以找到正确的标识符。"),
    ),
    "REF002": _guide(
        ("doi.org, arXiv or PubMed answers that the identifier does not exist: a typo, a DOI "
         "never registered, an invented arXiv ID.",
         "doi.org、arXiv 或 PubMed 答复该标识符不存在：拼写错误、从未注册的 DOI、"
         "编造的 arXiv 编号。"),
        ("A DOI registered in the last few days may not resolve yet.",
         "最近几天才注册的 DOI 可能还无法解析。"),
        ("Correct the identifier (a mistyped digit, a stray suffix) or remove it.",
         "改正标识符（打错的数字、多余的后缀）或将其删除。"),
    ),
    "REF003": _guide(
        ("The work was searched for by its title in every source that searches titles, every "
         "source answered, and nothing matched. Not reported for "
         "references the indexes are known to miss (grey literature, very new or pre-1990 works, "
         "workshop papers, non-Latin titles): those are REF090.",
         "按标题在所有支持标题检索的来源中检索了该作品，所有来源都正常应答，但没有任何匹配。"
         "对已知索引常常漏收的文献（灰色文献、很新或 1990 年以前的作品、研讨会论文、"
         "非拉丁文字的标题）不报此规则，而报 REF090。"),
        ("A real work can be missing from every index: an internal report, a thesis, a regional "
         "journal, a work cited by a translated title. A badly garbled title does not match "
         "either.",
         "真实的作品也可能不在任何索引里：内部报告、学位论文、地区性期刊、以译名引用的作品。"
         "标题错得太多也会检索不到。"),
        ("Check that the work exists and that its title is written as published. If it exists "
         "and is just not indexed, silence it with the reason: "
         "`% preflight: ignore[REF003] reason=\"internal report\"`.",
         "确认该作品确实存在、标题与发表时一致。如果作品存在、只是没有被索引，可以注明原因后消除："
         "`% preflight: ignore[REF003] reason=\"内部报告\"`。"),
    ),
    "REF004": _guide(
        ("Crossref (with Retraction Watch's data), OpenAlex or PubMed marks the cited work as "
         "retracted or withdrawn by its publisher. A partial retraction is a warning.",
         "Crossref（含 Retraction Watch 的数据）、OpenAlex 或 PubMed 标记被引作品已撤稿或被出版方撤"
         "回。部分撤稿报为警告。"),
        ("The notice is attached to the work's own DOI, so a wrong match is unlikely; a "
         "retraction is very rarely reversed.",
         "撤稿声明关联在作品自己的 DOI 上，误配的可能很小；撤稿被撤销的情况极少。"),
        ("Remove the citation, unless the text discusses the retraction itself; then silence it "
         "with the reason.",
         "删除该引用；如果正文讨论的就是这次撤稿，可以注明原因后消除。"),
    ),
    "REF005": _guide(
        ("The cited work has an expression of concern (a warning) or a published correction "
         "(an info), reported by Crossref, OpenAlex or PubMed.",
         "被引作品有关注声明（警告）或已发布的更正（提示），依据来自 Crossref、"
         "OpenAlex 或 PubMed。"),
        _NONE_KNOWN,
        ("Read the notice. Cite the correction too if it changes what you rely on.",
         "阅读该声明。如果更正影响到你引用的内容，请同时引用更正。"),
    ),
    "REF010": _guide(
        ("The work was identified, by its identifier or an unambiguous title match, but none of "
         "the entry's authors is on the record. Typical of invented references, which pair a "
         "real title with made-up names.",
         "已经通过标识符或无歧义的标题匹配确定了作品，但条目中的作者没有一位出现在记录里。"
         "常见于编造的文献：真实的标题配上虚构的作者。"),
        ("Names transliterated very differently, an organisation as author, or a record that "
         "lists the editors. Records of Semantic Scholar, Open Library and the software "
         "registries are not compared.",
         "音译差别很大的姓名、以机构为作者，或记录列的是编者。Semantic Scholar、"
         "Open Library 和软件平台的记录不参与作者比对。"),
        ("Compare with the work's page. `bib fix --level unsafe` writes the record's authors.",
         "对照作品页面核对。`bib fix --level unsafe` 会按记录写入作者。"),
    ),
    "REF011": _guide(
        ("Some authors are not on the record, the first author differs, a given name belongs to "
         "someone else, or a suffix (Jr.) is read as the given name. An info when the entry lists "
         "only some of the authors without \"and others\", or when the record is likely short "
         "(older Crossref records, DataCite standing in for arXiv).",
         "有作者不在记录里、第一作者不同、名字属于另一个人，或后缀（Jr.）被当成了名字。"
         "条目只列出部分作者却没写 \"and others\"，或记录很可能不全（较早的 Crossref 记录、"
         "代替 arXiv 应答的 DataCite）时，只作为提示。"),
        ("Author lists change between versions (an author added in v2), and records can be "
         "incomplete. Every record of the work is consulted before a name is reported missing.",
         "作者列表会随版本变化（第二版新增作者），记录也可能不全。"
         "只有在该作品的所有记录中都找不到时，才会报告缺少某位作者。"),
        ("Check against the version you cite. `bib fix --level unsafe` writes the record's list; "
         "end a list you shorten on purpose with \"and others\".",
         "对照你引用的版本核对。`bib fix --level unsafe` 会按记录写入作者列表；"
         "有意缩短的列表请以 \"and others\" 结尾。"),
    ),
    "REF012": _guide(
        ("The title differs from the record's beyond capitals, punctuation and LaTeX markup: "
         "either it is far from it, or a few words are reworded (named in the message). "
         "Rewording is reported only when every title the work has had is known.",
         "标题与记录不符，且差异不只是大小写、标点和 LaTeX 标记：要么相差很大，"
         "要么有几个词被替换（消息中会列出）。只有在作品历来所有版本的标题都已知时，"
         "才会报告换词。"),
        ("A title changed between preprint and publication (all known versions are compared), "
         "or a translated title of a work in another language (then an info).",
         "预印本与正式版本之间标题有改动（会与所有已知版本比较），"
         "或以译名引用其他语言的作品（此时只作为提示）。"),
        ("Use the title of the version you cite. `bib fix --level unsafe` writes the record's "
         "title with its capitals protected.",
         "使用你所引版本的标题。`bib fix --level unsafe` 会写入记录中的标题，"
         "并保护其中的大写字母。"),
    ),
    "REF013": _guide(
        ("The year is none of the record's dates: print, online and issue dates, and for a "
         "preprint the years of its versions.",
         "条目的年份不在记录的任何日期之中：印刷、在线和期号日期，预印本还包括其各版本的年份。"),
        ("A conference paper dated by the conference rather than the proceedings, or a book's "
         "later printing. Publishers' online-first dates and digitised backfiles are handled "
         "where known.",
         "会议论文按会议年份而非论文集出版年份标注，或图书的后续印次。"
         "出版社的在线优先日期和后来数字化的旧书记录，在已知的情况下已做处理。"),
        ("Use the year of the version you cite. `bib fix --level unsafe` writes the record's "
         "year.",
         "使用你所引版本的年份。`bib fix --level unsafe` 会写入记录中的年份。"),
    ),
    "REF014": _guide(
        ("The journal or booktitle names another venue than the record's, after known acronyms "
         "and abbreviations are expanded.",
         "期刊或会议名与记录中的发表场所不同（已展开已知的缩写和简称后再比较）。"),
        ("A workshop co-located with a conference, a renamed journal, or proceedings published "
         "in a series (LNCS) under another name.",
         "与主会同期举办的研讨会、改过名的期刊，或以丛书名义（如 LNCS）出版的会议论文集。"),
        ("Use the venue of the version you cite. `bib fix --level unsafe` writes the record's "
         "venue.",
         "使用你所引版本的发表场所。`bib fix --level unsafe` 会写入记录中的发表场所。"),
    ),
    "REF015": _guide(
        ("The entry cites a preprint (arXiv or another server) that has been published since, "
         "in a journal or proceedings: found through the DOI's relations, dblp, or a record with "
         "the same title and authors.",
         "条目引用的预印本（arXiv 或其他预印本平台）已经正式发表在期刊或会议论文集上："
         "通过 DOI 的关联关系、dblp，或标题和作者都相同的记录找到。"),
        ("You may mean the preprint on purpose (content cut from the published version). A "
         "deposit of the paper's code or data is never counted as its publication.",
         "你可能有意引用预印本（例如正式版本删掉了相关内容）。论文代码或数据的存档不会被当作正式发"
         "表。"),
        ("Cite the published version and keep the eprint field: `bib fix --level unsafe` does "
         "it. To keep the preprint, silence it with the reason, or make the rule an info in the "
         "project's settings: `severity = { REF015 = \"info\" }`.",
         "改引正式版本并保留 eprint 字段：`bib fix --level unsafe` 可以自动完成。如果要保留预印本，"
         "可以注明原因后消除，或在项目设置中把它降为提示：`severity = { REF015 = \"info\" }`。"),
    ),
    "REF016": _guide(
        ("The work's record has a DOI the entry lacks. Found once the entry is bound to its "
         "record by title, authors and year.",
         "作品的记录中有 DOI，而条目没有。在条目按标题、作者和年份对应到记录之后给出。"),
        _NONE_KNOWN,
        ("Add it: `bib fix` does at its safe level, the default.",
         "补上它：`bib fix` 在默认的 safe 级别就会补上。"),
    ),
    "REF017": _guide(
        ("An identifier written so that links break: LaTeX escapes or braces in a DOI "
         "(`10.1162/tacl\\_a\\_00276`), a URL or `doi:` prefix in the `doi` field, an arXiv DOI "
         "with a version suffix, an arXiv ID with its subject class.",
         "标识符的写法会让链接失效：DOI 中的 LaTeX 转义或花括号（`10.1162/tacl\\_a\\_00276`）、"
         "`doi` 字段带着网址或 `doi:` 前缀、arXiv 的 DOI 带版本号后缀、arXiv 编号带着学科分类。"),
        _NONE_KNOWN,
        ("`bib fix` corrects it at its safe level. A value that cannot be corrected (not an "
         "identifier at all) is left for you.",
         "`bib fix` 在 safe 级别会改正它。无法改正的值（根本不是标识符）留给你处理。"),
    ),
    "REF018": _guide(
        ("arXiv lists the cited preprint as withdrawn by its authors.",
         "arXiv 显示被引用的预印本已被作者撤回。"),
        _NONE_KNOWN,
        ("Cite the version or the work that replaces it; a withdrawn preprint's earlier versions "
         "stay readable, but its authors no longer stand by it.",
         "改引取代它的版本或作品；被撤回预印本的早期版本仍可阅读，但作者已不再认可其内容。"),
    ),
    "REF019": _guide(
        ("The entry links to a GitHub repository, a PyPI package or a CRAN package, and that "
         "registry answers it does not exist. Asked only when nothing else found the reference.",
         "条目链接到 GitHub 仓库、PyPI 或 CRAN 软件包，而对应平台答复它不存在。"
         "只在其他来源都找不到该文献时才查询。"),
        ("A repository made private or deleted after a move. A refused or rate-limited request "
         "is never read as \"not found\".",
         "仓库被设为私有，或迁移后被删除。被拒绝或受限流的请求不会被当作“不存在”。"),
        ("Update the link to where the project lives now, or cite an archived release "
         "(Zenodo, Software Heritage).",
         "把链接改为项目现在的地址，或引用其存档版本（Zenodo、Software Heritage）。"),
    ),
    "REF020": _guide(
        ("The work was found only as a preprint, and the venue the entry names is in none of "
         "the catalogues of journals and conferences (OpenAlex, dblp, Crossref). Venues cited "
         "with an edition, an acronym, a year or \"Proceedings\" are not looked up, since real "
         "workshops are in no catalogue either.",
         "作品只找到预印本，而条目写的发表场所在期刊与会议目录（OpenAlex、dblp、Crossref）"
         "中都查不到。带届次、缩写、年份或 Proceedings 的场所不会被查询，"
         "因为真实的研讨会同样不在目录里。"),
        ("A venue too new for the catalogues, or one outside them (some non-English journals).",
         "过新、目录尚未收录的场所，或目录之外的场所（部分非英文期刊）。"),
        ("Check where the work was published and cite that. If the venue is real, silence it "
         "with the reason and please report it.",
         "核对作品实际发表在哪里并据此引用。如果该场所确实存在，可注明原因后消除，"
         "并请提交 issue。"),
    ),
    "REF021": _guide(
        ("For a reference nothing else found, the linked page answers 404 or 410 (confirmed by a "
         "second request) and the Wayback Machine has no copy of it. Web pages are never judged "
         "true or false: this is an info.",
         "对于其他来源都找不到的文献，其链接的网页返回 404 或 410（经第二次请求确认），"
         "且 Wayback Machine 没有存档。网页的真伪从不判定：这只是一条提示。"),
        ("A page removed for a while, or a site that answers tools differently from browsers. "
         "Refusals (401, 403, 429), server errors and timeouts are never read as \"gone\".",
         "暂时下线的页面，或对工具与对浏览器应答不同的网站。拒绝访问（401、403、429）、"
         "服务器错误和超时从不被当作“失效”。"),
        ("Give a link that works, or a copy (save one with web.archive.org/save).",
         "换成能打开的链接或存档副本（可以用 web.archive.org/save 保存一份）。"),
    ),
    "REF090": _guide(
        ("The reference could be neither verified nor shown wrong; the message says why (a "
         "source unavailable, offline, grey literature, too new, a title too short to search, "
         "and so on). It is an abstention, never a judgement.",
         "该文献既不能核实，也不能证明有误；消息里会说明原因（来源不可用、离线、灰色文献、过新、"
         "标题过短无法检索等）。这是放弃判断，而不是结论。"),
        ("Not a judgement, so never wrong as such; the reasons are listed so you know what was "
         "left unchecked.",
         "既然不是结论，也就谈不上判错；列出原因是为了让你知道哪些地方没有被检查。"),
        ("Check the reference by hand when it matters. Some reasons go away: run online, re-run "
         "after an outage, add the work's DOI or arXiv ID, or set `S2_API_KEY`.",
         "需要时人工核对。有些原因可以消除：联网运行、在来源恢复后重跑、"
         "给条目补上 DOI 或 arXiv 编号，或设置 `S2_API_KEY`。"),
    ),
    "RUN001": _guide(
        ("Some sources did not answer and nothing could answer in their place, so some "
         "references were not fully checked. The run exits with code 2: the paper cannot be "
         "called clean yet.",
         "部分来源没有应答，也没有其他来源能够代替，因此有些文献没有被完整核查。"
         "运行以退出码 2 结束：目前还不能认定论文没有问题。"),
        _NONE_KNOWN,
        ("Re-run later. Answers already received are cached, so the next run only asks what is "
         "missing.",
         "稍后重新运行。已收到的答复都有缓存，下次运行只会补问缺少的部分。"),
    ),
    "RUN002": _guide(
        ("arXiv did not answer and DataCite, which registers arXiv's DOIs, answered in its "
         "place. What only arXiv knows (withdrawn preprints, the titles of earlier versions) was "
         "not checked.",
         "arXiv 没有应答，由为 arXiv 登记 DOI 的 DataCite 代为应答。"
         "只有 arXiv 掌握的信息（预印本是否撤回、早期版本的标题）这次没有被核查。"),
        _NONE_KNOWN,
        ("Re-run later for a full check.", "稍后重新运行，即可完整核查。"),
    ),
}  # fmt: skip
