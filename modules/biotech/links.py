import re

CHEMBL = re.compile(r"\bCHEMBL\d+\b")
UNIPROT = re.compile(r"UniProt(?:KB)?\s*[:=]?\s*([OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})\b")


def paper_links(meta):
    out = []
    if meta.get("pmcid"):
        out.append(("Paper (PMC)", f"https://pmc.ncbi.nlm.nih.gov/articles/{meta['pmcid']}/"))
    if meta.get("doi"):
        out.append(("Paper (DOI)", f"https://doi.org/{meta['doi']}"))
    if meta.get("pmid") and meta["pmid"].isdigit():
        out.append(("PubMed", f"https://pubmed.ncbi.nlm.nih.gov/{meta['pmid']}/"))
    return out


def data_links(text):
    """Database links for identifiers explicitly written in the cited passage."""
    out = []
    for cid in dict.fromkeys(CHEMBL.findall(text)):
        out.append((f"ChEMBL {cid}", f"https://www.ebi.ac.uk/chembl/compound_report_card/{cid}/"))
    for acc in dict.fromkeys(UNIPROT.findall(text)):
        out.append((f"AlphaFold {acc}", f"https://alphafold.ebi.ac.uk/entry/{acc}"))
        out.append((f"UniProt {acc}", f"https://www.uniprot.org/uniprotkb/{acc}/entry"))
    return out
