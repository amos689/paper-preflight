"""Reading a plain-text reference list: pasted from Word, a web page or a PDF."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from paper_preflight.bib.plaintext import parse_plaintext, parse_reference, split_references
from paper_preflight.check import run_check
from paper_preflight.cli import app
from paper_preflight.fixes import plan
from paper_preflight.identifier_lint import check_identifier_syntax


@pytest.mark.parametrize(
    ("text", "starts"),
    [
        # numbered, a reference running over two lines
        ("[1] A. Smith, “One,” 2020.\n[2] B. Lee,\n“Two,” 2021.\n",
         [(1, "A. Smith"), (2, "B. Lee")]),
        ("1. Smith, J. One. 2020.\n2. Lee, K. Two. 2021.\n", [(1, "Smith"), (2, "Lee")]),
        # paragraphs
        ("Smith, J. (2020).\nOne.\n\nLee, K. (2021). Two.\n", [(1, "Smith"), (4, "Lee")]),
        # one per line, as pasted from Word
        ("Smith, J. (2020). One.\nLee, K. (2021). Two.\n", [(1, "Smith"), (2, "Lee")]),
        # lines wrapped as in a PDF: a reference ends at a line ending in a period
        (
            "Smith, J. and Lee, K. A long title that\nwraps. Nature 1, 2 (2020).\n"
            "Wu, X. Another title that runs on\nto the next line. Science 3, 4 (2021).\n"
            "Li, Y. A third title, again too long for\none line. Cell 5, 6 (2022).\n",
            [(1, "Smith"), (3, "Wu"), (5, "Li")],
        ),
    ],
)  # fmt: skip
def test_split_references(text: str, starts: list[tuple[int, str]]) -> None:
    found = split_references(text)
    assert [(line, ref.split(",")[0].split(" ")[0]) for line, ref in found] == [
        (line, first.split(" ")[0]) for line, first in starts
    ]


def test_wrapped_lines_split_where_authors_start() -> None:
    text = (
        "Alain, G. and Bengio, Y. Understanding intermediate\n"
        "layers using linear classifier probes. arXiv preprint\n"
        "arXiv:1610.01644, 2016.\n"
        "Beigi, M., Shen, Y., and Huang, L. Sycophancy mitigation. In\n"
        "Proceedings of EMNLP, pp. 1-9, November 2025. URL https://aclanthology.org/2025.\n"
        "emnlp-main.661/. doi: 10.18653/v1/2025.emnlp-main.\n"
        "661.\n"
    )
    found = split_references(text, wrapped=True)
    assert [line for line, _ in found] == [1, 4]  # not at "Proceedings", nor at "2025."
    assert "10.18653/v1/2025.emnlp-main.661" in found[1][1]  # the DOI put back whole


def test_a_word_broken_at_a_line_end_is_joined() -> None:
    ((_, reference),) = split_references("[1] A. Smith, “Deep lan-\nguage models,” 2020.\n[2] x\n")[
        :1
    ]
    assert "language models" in reference


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        # IEEE
        ("K. He, X. Zhang, S. Ren, and J. Sun, “Deep residual learning for image recognition,” in "
         "Proc. IEEE Conf. Comput. Vis. Pattern Recognit. (CVPR), 2016, pp. 770–778.",
         {"author": "K. He and X. Zhang and S. Ren and J. Sun", "year": "2016",
          "title": "Deep residual learning for image recognition", "type": "inproceedings"}),
        # APA, with a DOI link
        ("Lopez, P. (2009). GROBID: Combining automatic bibliographic data recognition and term "
         "extraction for scholarship publications. In Research and Advanced Technology for "
         "Digital Libraries (pp. 473–474). https://doi.org/10.1007/978-3-642-04346-8_62",
         {"author": "Lopez, P.", "year": "2009", "doi": "10.1007/978-3-642-04346-8_62",
          "title": "GROBID: Combining automatic bibliographic data recognition and term "
                   "extraction for scholarship publications"}),
        # APA with an organisation as author
        ("CiteX. (2026). CiteX: Workshop on Citation Extraction and Parsing. https://example.org",
         {"author": "CiteX", "year": "2026", "url": "https://example.org"}),
        # ACM / ACL: the year after the authors
        ("Ashish Vaswani, Noam Shazeer, Niki Parmar, et al. 2017. Attention is all you need. In "
         "Advances in Neural Information Processing Systems, pages 5998–6008.",
         {"author": "Ashish Vaswani and Noam Shazeer and Niki Parmar and others", "year": "2017",
          "title": "Attention is all you need",
          "booktitle": "Advances in Neural Information Processing Systems"}),
        # natbib: authors. title. venue, year; an arXiv preprint
        ("Ilya Loshchilov and Frank Hutter. Decoupled weight decay regularization. arXiv preprint "
         "arXiv:1711.05101, 2017",
         {"author": "Ilya Loshchilov and Frank Hutter", "title": "Decoupled weight decay "
          "regularization", "eprint": "1711.05101", "year": "2017"}),
        # Nature
        ("Silver, D. et al. Mastering the game of Go with deep neural networks and tree search. "
         "Nature 529, 484–489 (2016).",
         {"author": "Silver, D. and others", "journal": "Nature", "year": "2016",
          "title": "Mastering the game of Go with deep neural networks and tree search"}),
        # Vancouver
        ("Vaswani A, Shazeer N, Parmar N, et al. Attention is all you need. Adv Neural Inf "
         "Process Syst. 2017;30:5998-6008.",
         {"author": "Vaswani, A. and Shazeer, N. and Parmar, N. and others", "year": "2017",
          "title": "Attention is all you need", "journal": "Adv Neural Inf Process Syst"}),
        # Springer LNCS
        ("He, K., Zhang, X., Ren, S., Sun, J.: Deep residual learning for image recognition. In: "
         "CVPR, pp. 770–778 (2016)",
         {"author": "He, K. and Zhang, X. and Ren, S. and Sun, J.", "booktitle": "CVPR",
          "title": "Deep residual learning for image recognition", "year": "2016"}),
        # Elsevier numbered
        ("K. He, X. Zhang, S. Ren, J. Sun, Deep residual learning for image recognition, in: "
         "CVPR, 2016, pp. 770–778.",
         {"author": "K. He and X. Zhang and S. Ren and J. Sun", "booktitle": "CVPR",
          "title": "Deep residual learning for image recognition", "year": "2016"}),
        # Chicago author-date, the title in quotes after the year
        ("He, Kaiming, Xiangyu Zhang, Shaoqing Ren, and Jian Sun. 2016. “Deep Residual Learning "
         "for Image Recognition.” In Proceedings of the IEEE Conference on Computer Vision and "
         "Pattern Recognition, 770–78.",
         {"author": "He, Kaiming and Xiangyu Zhang and Shaoqing Ren and Jian Sun", "year": "2016",
          "title": "Deep Residual Learning for Image Recognition"}),
        # MLA
        ("LeCun, Yann, Yoshua Bengio, and Geoffrey Hinton. \"Deep learning.\" Nature 521.7553 "
         "(2015): 436-444.",
         {"author": "LeCun, Yann and Yoshua Bengio and Geoffrey Hinton", "title": "Deep learning",
          "journal": "Nature", "year": "2015"}),
        # biblatex: "In:" before a journal with its volume, a language code, an ISSN, a visit
        ("Petr Knoth et al. “CORE: A Global Aggregation Service for Open Access Papers”. en. In: "
         "Scientific Data 10.1 (June 2023). issn: 2052-4463. doi: 10.1038/s41597-023-02208-w. "
         "url: https://www.nature.com/articles/s41597-023-02208-w (visited on 04/24/2025).",
         {"author": "Petr Knoth and others", "journal": "Scientific Data", "year": "2023",
          "doi": "10.1038/s41597-023-02208-w", "type": "article"}),
        # an arXiv ID never filled in, and a DOI written wrongly, are kept as written
        ("Nuo Lou and et al. Dsp: Diffusion-based span prediction for masked text modeling. arXiv "
         "preprint arXiv:2305.XXXX, 2023",
         {"author": "Nuo Lou and others", "eprint": "2305.XXXX"}),
        ("Ilia Kulikov. Importance of search. 2019. doi: 0.18653/v1/W19-8609.",
         {"doi": "0.18653/v1/W19-8609"}),
        # APA with a group first and APA 7's ellipsis before the last of many authors
        ("Gemma, Kamath, A., Ferret, J., … Hussenot, L. (2025). Gemma 3 Technical Report. "
         "https://arxiv.org/abs/2503.19786",
         {"author": "Gemma and Kamath, A. and Ferret, J. and Hussenot, L. and others",
          "eprint": "2503.19786"}),
        ("Yang, A., Lin, H., & al., et. (2025). Qwen2.5 Technical Report.",
         {"author": "Yang, A. and Lin, H. and others"}),
        # a venue's acronym in parentheses is part of its name
        ("Sebastian Pado and Christopher D Manning. Machine translation evaluation with textual "
         "entailment features. In Proceedings of the Fourth Workshop on Statistical Machine "
         "Translation (WMT), pages 37–41, 2009",
         {"booktitle": "Proceedings of the Fourth Workshop on Statistical Machine Translation "
                       "(WMT)"}),
        # a technical report, and pages right after the title
        ("Augustine Kong. A note on importance sampling using standardized weights. University "
         "of Chicago, Dept. of Statistics, Tech. Rep, 348:14, 1992",
         {"type": "techreport", "institution": "University of Chicago, Dept. of Statistics, "
                                               "Tech. Rep"}),
        ("Ilia Kulikov and Jason Weston. Importance of search and evaluation strategies in neural "
         "dialogue modeling. pp. 76–87, 01 2019. doi: 10.18653/v1/W19-8609.",
         {"title": "Importance of search and evaluation strategies in neural dialogue modeling"}),
        # AAS: no title, the journal and volume after the year
        ("Abbott, B. P., Abbott, R., et al. 2017, ApJL, 848, L12, doi: 10.3847/2041-8213/aa91c9",
         {"author": "Abbott, B. P. and Abbott, R. and others", "year": "2017", "journal": "ApJL",
          "title": None, "doi": "10.3847/2041-8213/aa91c9"}),
        ("A. Baskin and A. Laor. MNRAS, 474(2):1970-1994, Feb. 2018. doi: 10.1093/mnras/stx2850.",
         {"author": "A. Baskin and A. Laor", "journal": "MNRAS", "title": None}),
        # SIAM: the journal before its volume, and "and" before the last author
        ("B. Adcock, N. Dexter, and S. Moraga, Optimal approximation of infinite-dimensional "
         "holomorphic functions, Calcolo, 61 (2024), p. 12.",
         {"author": "B. Adcock and N. Dexter and S. Moraga", "journal": "Calcolo",
          "title": "Optimal approximation of infinite-dimensional holomorphic functions"}),
        # APS: two authors joined by "and", a book
        ("H.-P. Breuer and F. Petruccione, The Theory of Open Quantum Systems (Oxford University "
         "Press, 2002).",
         {"author": "H.-P. Breuer and F. Petruccione"}),
        # a long author list with a name a PDF mangled
        ("Jerome Ku, Eric Nguyen, David W. Romero, Garyk Brixi, Brandon Yang, Anton V orontsov, "
         "Ali Taghibakhshi, Amy X. Lu, and Michael Poli. Systems and algorithms for "
         "convolutional multi-hybrid language models at scale. arXiv preprint arXiv:2503.01868, "
         "2025.",
         {"title": "Systems and algorithms for convolutional multi-hybrid language models at "
                   "scale"}),
        # "St." is no sentence's end
        ("Peter St. John, Dejun Lin, and John St. John. BioNeMo framework. arXiv preprint "
         "arXiv:2411.10548, 2024.",
         {"author": "Peter St. John and Dejun Lin and John St. John",
          "title": "BioNeMo framework"}),
        # a year in parentheses late in another style is not APA's
        ("J. Preskill, Quantum computing in the NISQ era and beyond, Quantum 2, 79 (2018).",
         {"author": "J. Preskill", "title": "Quantum computing in the NISQ era and beyond"}),
        # a title with no authors
        ("ANSI/NISO Z39.96-2024: JATS: Journal Article Tag Suite (2024).",
         {"title": "ANSI/NISO Z39.96-2024: JATS: Journal Article Tag Suite", "year": "2024",
          "author": None}),
        # an accented capital starts a name
        ("Étienne Pardoux and Alexander Yu Veretennikov. Poisson equation for multiscale "
         "diffusions. Journal of Mathematical Sciences, 111(3):3713-3719, 2002.",
         {"author": "Étienne Pardoux and Alexander Yu Veretennikov",
          "title": "Poisson equation for multiscale diffusions",
          "journal": "Journal of Mathematical Sciences", "type": "article"}),
        # a title that asks runs into its journal, and math left in from a PDF
        ("W L Chan and R O Shelton. Can machine learning improve delta hedging? Journal of "
         "Derivatives, $9(1): 39-56,2001$.",
         {"title": "Can machine learning improve delta hedging?",
          "journal": "Journal of Derivatives", "year": "2001"}),
        # ... but a question with a subtitle stays one title
        ("M. J. Simpson and M. J. Plank. When Do Trajectories Matter? Identifiability Analysis "
         "for Stochastic Transport Phenomena. 2026. arXiv:2604.15598.",
         {"title": "When Do Trajectories Matter? Identifiability Analysis for Stochastic "
                   "Transport Phenomena", "journal": None}),
        # a venue that starts with its edition or its year
        ("K. A. Sankararaman and F. Bromberg. The impact of neural network overparameterization "
         "on gradient confusion. In 37th International Conference on Machine Learning (ICML), "
         "pages 8469-8479, 2020.",
         {"booktitle": "37th International Conference on Machine Learning (ICML)",
          "type": "inproceedings"}),
        ("Tom Eccles, Jeffrey Tweedale, and Yvette Izza. Let's pretend: A study of negotiation "
         "with autonomous agents. In 2009 IEEE/WIC/ACM International Joint Conference on Web "
         "Intelligence and Intelligent Agent Technology (WI-IAT), volume 3, pp. 449-452. IEEE, "
         "2009.",
         {"booktitle": "2009 IEEE/WIC/ACM International Joint Conference on Web Intelligence "
                       "and Intelligent Agent Technology (WI-IAT)"}),
        # no venue, the year after the title, and an arXiv URL a PDF broke at the slash
        ("Robert Huben, Logan Riggs, and Lee Sharkey. Sparse autoencoders can interpret randomly "
         "initialized transformers, 2025. URL https://arxiv.org/ abs/2501.17727.",
         {"title": "Sparse autoencoders can interpret randomly initialized transformers",
          "year": "2025", "eprint": "2501.17727"}),
        # numbered twice
        ("[3] K. Arnold, J. Smith, and A. Doe. Variability in triage decision making. "
         "Resuscitation, 85:12341239, 2014.",
         {"author": "K. Arnold and J. Smith and A. Doe", "journal": "Resuscitation"}),
        # Nature's style as \url prints it (2609.10121v2): a link in angle brackets, a family
        # name with a lower-case particle
        ("Myung, Y., de Sá, A. G. C. & Ascher, D. B. Deep-PK: deep learning for small molecule "
         "pharmacokinetic and toxicity prediction. Nucleic Acids Research 52, W469–W475 "
         "(2024). <https://doi.org/10.1093/nar/gkae254>",
         {"author": "Myung, Y. and de Sá, A. G. C. and Ascher, D. B.",
          "title": "Deep-PK: deep learning for small molecule pharmacokinetic and toxicity "
                   "prediction",
          "journal": "Nucleic Acids Research", "year": "2024"}),
        ("Breiman, L. Random Forests. Machine Learning 45, 5–32 (2001). "
         "<https://doi.org/10.1023/a:1010933404324>",
         {"author": "Breiman, L.", "title": "Random Forests", "journal": "Machine Learning"}),
        # a title of two sentences, its journal's volume after them
        ("Nilakantan, R., Bauman, N., Dixon, J. S. & Venkataraghavan, R. Topological torsion: a "
         "new molecular descriptor for SAR applications. Comparison with other descriptors. "
         "Journal of Chemical Information and Computer Sciences 27, 82–85 (1987).",
         {"title": "Topological torsion: a new molecular descriptor for SAR applications. "
                   "Comparison with other descriptors",
          "journal": "Journal of Chemical Information and Computer Sciences"}),
        # MDPI and ACS: names separated by semicolons
        ("Paravina, R.D.; Pérez, M.M.; Ghinea, R. Acceptability and perceptibility "
         "thresholds in dentistry. J. Esthet. Restor. Dent. 2019, 31, 103-112.",
         {"author": "Paravina, R.D. and Pérez, M.M. and Ghinea, R.",
          "title": "Acceptability and perceptibility thresholds in dentistry", "year": "2019"}),
        # GOST: dotted initials after the family name, "//" before the container
        ("Pham N. T., Vo T. H., Nguyen M. H. The impact of digital transformation on economic "
         "growth: A global evidence // Journal of Finance - Marketing Research. 2025. Vol. 16. "
         "No. 2. P. 1-12.",
         {"author": "Pham, N. T. and Vo, T. H. and Nguyen, M. H.",
          "title": "The impact of digital transformation on economic growth: A global evidence",
          "journal": "Journal of Finance - Marketing Research", "year": "2025"}),
        ("Boyd S., Vandenberghe L. Convex optimization. Cambridge: Cambridge University Press, "
         "2004. 716 p.",
         {"author": "Boyd, S. and Vandenberghe, L.", "title": "Convex optimization"}),
        # Vancouver with a particle first
        ("de Smalen LM, Boersch A, Handschin C. Impaired age-associated mitochondrial "
         "translation is mitigated by exercise. Proc Natl Acad Sci U S A. 2023;120(36):e2302.",
         {"author": "de Smalen, L. M. and Boersch, A. and Handschin, C.",
          "title": "Impaired age-associated mitochondrial translation is mitigated by exercise"}),
        # NLM with a title in capitals, which reads like a name; a family name starting with Ż
        ("Zhang B, Sennrich R. Root Mean Square Layer Normalization. In: Advances in Neural "
         "Information Processing Systems. 2019.",
         {"author": "Zhang, B. and Sennrich, R.", "title": "Root Mean Square Layer Normalization",
          "booktitle": "Advances in Neural Information Processing Systems"}),
        ("Goyeneche D, Życzkowski K. Genuinely multipartite entangled states and orthogonal "
         "arrays. Physical review A. 2014;90(2):022316.",
         {"author": "Goyeneche, D. and Życzkowski, K.",
          "title": "Genuinely multipartite entangled states and orthogonal arrays"}),
        # APA's description of a preprint after its title; a venue that starts lower-case
        ("Takase, S., Kiyono, S., Kobayashi, S., & Suzuki, J. (2025). Spike No More: Stabilizing "
         "the Pre-training of Large Language Models (arXiv:2312.16903).",
         {"title": "Spike No More: Stabilizing the Pre-training of Large Language Models",
          "eprint": "2312.16903"}),
        ("Brixi G, Durrant MG, Ku J. Genome modeling and design across all domains of life with "
         "Evo 2. bioRxiv. 2025.",
         {"title": "Genome modeling and design across all domains of life with Evo 2"}),
        # NLM: a title in numbered parts; the year before the volume, not in the arXiv number
        ("Planck Collaboration, Ade PAR, Aghanim N, et al. Planck early results. XVII. Origin "
         "of the submillimetre excess dust emission in the Magellanic Clouds. Astron Astrophys. "
         "2011;536:arXiv:1101.2046.",
         {"author": "Planck Collaboration and Ade, P. A. R. and Aghanim, N. and others",
          "title": "Planck early results. XVII. Origin of the submillimetre excess dust emission "
                   "in the Magellanic Clouds",
          "year": "2011"}),
        ("Friel ED, Jacobson HR. Abundances of Red Giants in Old Open Clusters. V. Be 31, Be 32, "
         "and NGC 1193. Astron J. 2010;139:1942-67.",
         {"title": "Abundances of Red Giants in Old Open Clusters. V. Be 31, Be 32, and NGC 1193",
          "year": "2010"}),
        ("Stalevski M, Tristram KRW, Asmus D. Dissecting the active galactic nucleus in Circinus "
         "- II. A thin dusty disc and a polar outflow on parsec scales. Mon Not R Astron Soc. "
         "2019;484(3):3334-55.",
         {"title": "Dissecting the active galactic nucleus in Circinus - II. A thin dusty disc "
                   "and a polar outflow on parsec scales"}),
        ("Woosley SE. World War II. J Hist. 2018;3:1-9.",
         {"title": "World War II", "journal": "J Hist"}),
        # a title that opens with "The", or in capitals, is no list of names; "ten", "Å"
        ("Tody D. The IRAF Data Reduction and Analysis System. In: Instrumentation in astronomy "
         "VI. 1986. p. 733.",
         {"author": "Tody, D.", "title": "The IRAF Data Reduction and Analysis System"}),
        ("Kishimoto M, ten Brummelaar T, Nordlund Å. OCCASO. IV. Radial velocities. "
         "Astrophys J. 2022;940(1):28.",
         {"author": "Kishimoto, M. and ten Brummelaar, T. and Nordlund, Å.",
          "title": "OCCASO. IV. Radial velocities"}),
        # APA as written in Word manuscripts (Zenodo 23064837): "et al." after the last initials,
        # a name in brackets, a place written with a space before its colon
        ("Rüland, A.L., Andersen, L.H., Hassen, A. et al. (2025). Science Diplomacy: A "
         "Global Research Field? Scientometrics, 130, 4697-4722.",
         {"author": "Rüland, A.L. and Andersen, L.H. and Hassen, A. and others",
          "journal": "Scientometrics"}),
        ("Owusu-Kwarteng, A., Jack, S., Forson, C., Dada, O. (L.). (2025). In Pursuit of the "
         "Third Mission. Technovation, 141, 103188, 1-13.",
         {"author": "Owusu-Kwarteng, A. and Jack, S. and Forson, C. and Dada, O."}),
        ("Ball, C.E., Graban, T.S., & Sidler, M. (2021). The Boutique is Open: Data for Writing "
         "Studies. In: Licastro, A., & Miller, B. (eds.), Composition and Big Data. Pittsburgh, "
         "PA : University of Pittsburgh Press, pp. 196-211.",
         {"booktitle": "Composition and Big Data"}),
        # what APA adds in brackets after a title goes; what a magazine registers stays
        ("da Silva, A. P., & Mendes, P. P. (2006). Utilização da artêmia nacional [Brazilian "
         "artemia as feed for post-larvae]. Acta Scientiarum, 28(3), 345-351.",
         {"title": "Utilização da artêmia nacional"}),
        ("Smith, J. (2020). Shrimp growth data [Data set]. Zenodo.",
         {"title": "Shrimp growth data"}),
        ("AOAC International. (2023). Official methods of analysis of AOAC International (22nd "
         "ed.). AOAC International.",
         {"title": "Official methods of analysis of AOAC International"}),
        ("Grewal, M. S., & Andrews, A. P. (2010). Applications of Kalman filtering in aerospace "
         "1960 to the present [Historical Perspectives]. IEEE Control Systems Magazine, 30(3), "
         "69-78.",
         {"title": "Applications of Kalman filtering in aerospace 1960 to the present "
                   "[Historical Perspectives]"}),
        # GOST with a title of two sentences; an initial outside A-Z in MDPI's names
        ("Pohle J., Voelsen D. Centrality and power. The struggle over the global digital order "
         "// Policy & Internet. 2022. Vol. 14. P. 13-27.",
         {"title": "Centrality and power. The struggle over the global digital order",
          "journal": "Policy & Internet"}),
        ("Tuncer, S.; Demirci, M.; Uysal, Ö. The effect of a modeling resin. J. Esthet. "
         "Restor. Dent. 2013, 25, 404-419.",
         {"author": "Tuncer, S. and Demirci, M. and Uysal, Ö.",
          "title": "The effect of a modeling resin"}),
        # no venue, the year in brackets
        ("Ning, J., Li, X. & Ke, G. Closed-loop Auto Research for Molecular Property "
         "Prediction (2026).",
         {"title": "Closed-loop Auto Research for Molecular Property Prediction",
          "year": "2026"}),
    ],
)  # fmt: skip
def test_reference_styles(reference: str, expected: dict[str, str | None]) -> None:
    entry_type, fields = parse_reference(reference)
    for name, value in expected.items():
        if name == "type":
            assert entry_type == value
        else:
            assert fields.get(name) == value, name


LIST = """References

[1] K. He, X. Zhang, S. Ren, and J. Sun, “Deep residual learning for image recognition,” in
    Proc. CVPR, 2016, pp. 770–778.
[2] Lopez, P. (2009). GROBID: Combining Automatic Bibliographic Data Recognition and Term
    Extraction for Scholarship Publications. https://doi.org/10.1007/978-3-642-04346-8_62
"""


def test_a_list_becomes_derived_entries() -> None:
    bib = parse_plaintext(LIST, Path("refs.txt"))
    assert bib.derived
    assert [(e.key, e.line) for e in bib.entries] == [("ref1", 3), ("ref2", 5)]
    assert bib.entries[1].text("doi") == "10.1007/978-3-642-04346-8_62"
    assert bib.entries[0].fields["title"].line == 3


def test_the_same_authors_as_the_reference_before() -> None:
    text = (
        "[1] B. Adcock, N. Dexter, and S. Moraga, Optimal approximation of holomorphic functions,"
        " Calcolo, 61 (2024).\n"
        "[2] ———, Optimal approximation II: recovery from samples, J. Complexity, 89 (2025).\n"
    )
    second = parse_plaintext(text, Path("refs.txt")).entries[1]
    assert second.text("author") == "B. Adcock and N. Dexter and S. Moraga"
    assert second.text("title") == "Optimal approximation II: recovery from samples"


def test_identifiers_are_read_as_written() -> None:
    text = "[1] M. M. and M. O., “Inforex,” in RANLP, 2019. doi: 10.26615/978-954-452-056-4_083.\n"
    (entry,) = parse_plaintext(text, Path("refs.txt")).entries
    assert entry.fields["doi"].raw == "{10.26615/978-954-452-056-4_083}"
    assert check_identifier_syntax([entry]) == []  # no LaTeX escape to report (REF017)


def test_a_list_checked_on_its_own(tmp_path: Path) -> None:
    path = tmp_path / "refs.txt"
    path.write_text(LIST, encoding="utf-8")
    result = run_check(path)
    assert result.entries == 2
    assert plan(result.findings, result.bib_files, level="unsafe") == []  # never edited


def test_a_list_from_stdin() -> None:
    result = CliRunner().invoke(app, ["check", "-", "--offline", "-f", "json"], input=LIST)
    assert result.exit_code in {0, 2}, result.output
    assert '"entries": 2' in result.output.replace(" ", "").replace('"entries":2', '"entries": 2')


def test_a_name_with_a_lower_case_part_among_many() -> None:
    # PDFs and generated lists write "Yun chen Chen" or "Wei xin Zhao": among proper names, still
    # a name, so the list is read as authors and the title is found
    _, fields = parse_reference(
        "Anna Berg, Carl Dahl, Erik Fors, Wei xin Zhao, and Greta Holm. Learning to rank with "
        "sparse graphs. In Proceedings of the 30th Conference on Learning Theory, 2021."
    )
    assert fields["title"] == "Learning to rank with sparse graphs"
    assert fields["author"].startswith("Anna Berg and Carl Dahl")
    # a phrase is not: "Proceedings on" before a quoted workshop name (Badalova & Mayr P3R30)
    _, fields = parse_reference(
        "Anna Berg, Carl Dahl, and Erik Fors. Sparse graphs. In Ian Moss, Jon Lake (eds.), "
        "Proceedings on \u201cWhat Fails and Why\u201d at NeurIPS 2023 Workshops, 2023."
    )
    assert fields["title"] == "Sparse graphs"
