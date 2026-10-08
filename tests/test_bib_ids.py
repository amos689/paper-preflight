from pathlib import Path

import pytest

from paper_preflight.bib.ids import extract_identifiers, normalize_doi
from paper_preflight.bib.parse import parse_bib_text


def ids(bib: str) -> list[str]:
    (entry,) = parse_bib_text(bib, Path("x.bib")).entries
    return [str(i) for i in extract_identifiers(entry)]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("10.1109/CVPR.2016.90", "10.1109/cvpr.2016.90"),
        ("https://doi.org/10.1109/CVPR.2016.90", "10.1109/cvpr.2016.90"),
        ("http://dx.doi.org/10.1109/CVPR.2016.90.", "10.1109/cvpr.2016.90"),
        ("doi:10.1016/S0140-6736(97)11096-0", "10.1016/s0140-6736(97)11096-0"),
        ("not a doi", None),
        # arXiv DOIs carry no version: doi.org answers 404 for the versioned form
        ("10.48550/arXiv.2602.12139v1", "10.48550/arxiv.2602.12139"),
        ("10.1234/sample.v2", "10.1234/sample.v2"),  # other DOIs are left alone
        # Wiley's SICI DOIs keep their bracketed part (2607.13343v1, kerawala2001relocating)
        (
            "10.1002/1097-0347(200103)23:3<230::AID-HED1023>3.0.CO;2-V",
            "10.1002/1097-0347(200103)23:3<230::aid-hed1023>3.0.co;2-v",
        ),
        (
            "<https://doi.org/10.1109/CVPR.2016.90>",
            "10.1109/cvpr.2016.90",
        ),  # a lone bracket ends it
    ],
)
def test_normalize_doi(raw: str, expected: str | None) -> None:
    assert normalize_doi(raw) == expected


def test_escaped_doi_field() -> None:
    assert ids(r"@article{a, doi = {10.1162/tacl\_a\_00276}}") == ["doi:10.1162/tacl_a_00276"]


def test_arxiv_from_eprint_journal_url_and_datacite_doi() -> None:
    assert ids("@misc{a, eprint={1706.03762v5}, archivePrefix={arXiv}}") == ["arxiv:1706.03762v5"]
    assert ids("@article{a, journal={arXiv preprint arXiv:1810.04805}}") == ["arxiv:1810.04805"]
    assert ids("@misc{a, url={https://arxiv.org/abs/2106.09685v2}}") == ["arxiv:2106.09685v2"]
    assert ids("@misc{a, doi={10.48550/arXiv.1706.03762}}") == [
        "doi:10.48550/arxiv.1706.03762",
        "arxiv:1706.03762",
    ]
    assert ids("@misc{a, eprint={hep-th/9901001}}") == ["arxiv:hep-th/9901001"]


def test_numbers_without_arxiv_context_are_not_arxiv_ids() -> None:
    assert ids("@article{a, journal={Proceedings 2017}, note={pages 1234.5678}}") == []
    assert ids("@misc{a, eprint={12345}, eprinttype={pubmed}}") == ["pmid:12345"]


def test_doi_in_url_field() -> None:
    assert ids("@misc{a, url={https://doi.org/10.18653/v1/N19-1423}}") == [
        "doi:10.18653/v1/n19-1423"
    ]


def test_acm_digital_library_numbers_in_a_link_are_not_dois() -> None:
    # QLoRA's ACM DL page (2609.09569v1): 10.5555 is registered with no agency, the page works
    assert ids("@misc{a, url={https://dl.acm.org/doi/10.5555/3666122.3666563}}") == []
    assert ids("@misc{a, url={https://dl.acm.org/doi/10.1145/3219819.3220064}}") == [
        "doi:10.1145/3219819.3220064"
    ]
    # a doi field holding one is still checked (it is not a DOI)
    assert ids("@misc{a, doi={10.5555/3045390.3045531}}") == ["doi:10.5555/3045390.3045531"]


def test_a_publishers_page_for_the_doi_is_not_another_doi() -> None:
    # deep-review's CSL-JSON: OUP's page adds an article number and a slug after the DOI
    entry = (
        "@article{a, doi={10.1093/bib/bbw110}, url={https://academic.oup.com/bib/article/doi/"
        "10.1093/bib/bbw110/2562646/A-review-of-validation-strategies-for}}"
    )
    assert ids(entry) == ["doi:10.1093/bib/bbw110"]


def test_isbn_and_issn_checksums() -> None:
    assert ids("@book{a, isbn={978-0-262-03561-3}}") == ["isbn:9780262035613"]
    assert ids("@book{a, isbn={978-0-262-03561-4}}") == []  # bad checksum
    assert ids("@book{a, isbn={0-262-03384-4}}") == ["isbn:0262033844"]
    assert ids("@article{a, issn={0028-0836}}") == ["issn:0028-0836"]
    assert ids("@article{a, issn={0028-0837}}") == []


def test_pmid_and_pmcid() -> None:
    assert ids("@article{a, pmid={9500320}, pmcid={pmc1234567}}") == [
        "pmid:9500320",
        "pmcid:PMC1234567",
    ]


def test_versioned_arxiv_doi_keeps_the_version_on_the_arxiv_id() -> None:
    assert ids("@misc{a, doi={10.48550/arXiv.2602.12139v1}}") == [
        "doi:10.48550/arxiv.2602.12139",
        "arxiv:2602.12139v1",
    ]
