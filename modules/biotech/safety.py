import re

MEDICAL = re.compile(r"\b(take|taking|dose|dosage|dosing|medicat\w*|medicine|drug|treat\w*|symptom\w*|supplement\w*|safe|inject\w*|"
                     r"prescri\w*|diagnos\w*|therap\w*|cure|pregnan\w*|side effects?)\b", re.I)
FIRST_PERSON_MODAL = re.compile(r"\b(should|can|could|may|would|do|am)\s+i\b", re.I)
PERSONAL = [
    re.compile(r"\bwhat\s+(dose|dosage|amount)\s+(should|do|can)\s+(i|we|you)\b", re.I),
    re.compile(r"\bmy\s+(dose|dosage|symptom\w*|medication|medicine|doctor|child|son|daughter|baby|dog|cat|pet|mother|father|"
               r"wife|husband|condition|diagnosis|treatment|cancer|pain)\b", re.I),
    re.compile(r"\bi\s+(have|had)\s+(a\s+|an\s+)?(symptom\w*|pain|cancer|disease|condition|infection|diagnos\w*)", re.I),
    re.compile(r"\bi\s+(am|was)\s+(taking|diagnosed|prescribed|pregnant)\b", re.I),
    re.compile(r"\b(safe|okay|ok)\s+(for|to give)\s+(me|my|him|her|children|kids|a child|a baby)\b", re.I),
    re.compile(r"\bgive\s+(it\s+)?to\s+my\b", re.I),
]
DUAL_AGENT = re.compile(r"\b(bioweapon\w*|bioterror\w*|nerve agent\w*|sarin|novichok|ricin|anthrax|botulinum|smallpox)\b", re.I)
DUAL_ACTION = re.compile(r"\b(synthesi[sz]\w*|produc\w*|manufactur\w*|culture|cultivat\w*|extract\w*|weaponi[sz]\w*|aerosol\w*|"
                         r"disperse\w*|deliver\w*|make|making)\b", re.I)
DUAL_ENHANCE = re.compile(r"\b(increase|enhance|boost|improve)\w*\s+(the\s+)?(transmissib\w*|lethal\w*|virulen\w*|infectiv\w*)", re.I)

MEDICAL_MSG = ("This tool finds and cites published research. It cannot give medical, dosing or treatment advice. "
               "Please ask a doctor or pharmacist.")
DUAL_MSG = "This tool will not help with making, producing or enhancing dangerous biological or chemical agents."


def check_question(q):
    """Returns (refused: bool, message)."""
    if (DUAL_AGENT.search(q) and DUAL_ACTION.search(q)) or DUAL_ENHANCE.search(q):
        return True, DUAL_MSG
    if any(p.search(q) for p in PERSONAL):
        return True, MEDICAL_MSG
    if FIRST_PERSON_MODAL.search(q) and MEDICAL.search(q):
        return True, MEDICAL_MSG
    return False, ""
