"""References to Chinese-language works written as English papers cite them.

An English paper cites a Chinese-language article by a translated title, the journal's English
name and pinyin authors, often marked "(in Chinese)". The open indexes mostly hold such articles
under their Chinese title, if at all, so a search for the translation finds nothing: that is no
evidence against the work. On the Chinese-reference experiments' development data (reports/paper
preflight 中文实验结果.md, X1), 0.5.0 called 60% of real ones "not found".
"""

from __future__ import annotations

import re

# "(in Chinese)", "[in Chinese]", "(Chinese)", "in Chinese with English abstract", in a note
MARK = re.compile(
    r"\bin\s+chinese\b|[(\[]\s*chinese\s*[)\]]|\bchinese\s+with\s+english\s+abstract\b|"
    r"\bchinese\s+version\b",
    re.IGNORECASE,
)
# in a title only in brackets: "... Nominal Expressions in Chinese" is a title's own words
_TITLE_MARK = re.compile(
    r"[\s.,;:]*[(\[]\s*(?:in\s+)?chinese(?:\s+with\s+english\s+abstract)?\s*[)\]][\s.]*$",
    re.IGNORECASE,
)
_LANGUAGE = re.compile(r"^\s*(?:chinese|zh(?:-\w+)?|chi|zho|中文)\s*$", re.IGNORECASE)

# English names of Chinese-language journals, as English papers cite them (from the experiments'
# development data; each is the journal's own English title)
JOURNALS = (
    r"chinese journal of computers", r"journal of software", r"acta automatica sinica",
    r"scientia sinica(?:[ :-]+[a-z]+)?", r"sci(?:entia)?\.? sin(?:ica)?\.? inform\w*\.?",
    r"journal of computer research and development",
    r"pattern recognition and artifici?al intelligence", r"acta electronica sinica",
    r"journal of electronics (?:&|and) information technology", r"journal on communications",
    r"control and decision", r"control theory (?:&|and) applications",
    r"journal of image and graphics", r"journal of chinese information processing",
    r"computer engineering and applications", r"journal of computer applications",
    r"application research of computers",
    r"journal of frontiers of computer science and technology",
    r"journal of computer[- ]aided design (?:&|and) computer graphics",
    r"journal of chinese computer systems", r"acta physica sinica", r"acta optica sinica",
    r"chinese journal of lasers", r"acta petrolei sinica", r"acta geographica sinica",
    r"acta ecologica sinica", r"acta aeronautica et astronautica sinica",
    r"chinese journal of theoretical and applied mechanics", r"proceedings of the csee",
    r"automation of electric power systems", r"power system technology",
    r"transactions of china electrotechnical society",
    r"systems engineering[- —]+theory (?:&|and) practice", r"journal of remote sensing",
    r"national remote sensing bulletin", r"geomatics and information science of wuhan university",
    r"acta geodaetica et cartographica sinica", r"chinese journal of scientific instrument",
    r"journal of cyber security", r"netinfo security", r"journal of cryptologic research",
    r"acta scientiae circumstantiae", r"acta mathematicae applicatae sinica",
    r"acta mathematica sinica,? chinese series", r"acta metallurgica sinica",
    r"acta photonica sinica", r"acta armamentarii", r"journal of tsinghua university",
    r"journal of zhejiang university", r"journal of huazhong university of science and technology",
    r"journal of beijing university of aeronautics and astronautics",
    r"journal of china universities of posts and telecommunications",
    r"acta scientiarum naturalium universitatis pekinensis", r"journal of system simulation",
    r"journal of the china society for scientific and technical information",
    r"journal of library science in china", r"data analysis and knowledge discovery",
    r"computer engineering and design", r"computer integrated manufacturing systems",
)  # fmt: skip
# the whole journal field is one of them, perhaps with an edition in parentheses
_JOURNAL = re.compile(
    r"^\s*(?:the\s+)?(?:" + "|".join(JOURNALS) + r")\s*(?:\([^)]*\))?\s*[.,]?\s*$", re.IGNORECASE
)
# pinyin words journal names carry ("Jisuanji Xuebao", "Zhongguo Kexue")
_PINYIN = re.compile(
    r"\b(?:xuebao|zazhi|jisuanji|ruanjian|zidonghua|zhongguo|zhonghua|dianzi|kexue|gongcheng|"
    r"daxue|jishu|yingyong|tongxin|yanjiu)\b",
    re.IGNORECASE,
)


def strip_mark(title: str) -> str:
    """The title without a language mark at its end: "... Systems (in Chinese)"."""
    return _TITLE_MARK.sub("", title).strip()


def translated(*, title: str, venue: str | None, other: str, language: str = "") -> bool:
    """The entry cites a Chinese-language work in English: a language mark (in brackets in the
    title; anywhere in ``other``, the note, pages and howpublished), a language field saying
    Chinese, the English name of a Chinese-language journal, or a journal named in pinyin."""
    if _TITLE_MARK.search(title) or MARK.search(other) or _LANGUAGE.match(language):
        return True
    if venue and MARK.search(venue):
        return True
    return bool(venue and (_JOURNAL.match(venue) or _PINYIN.search(venue)))
