# Evidence Platform
Run tests: `bash run_tests.sh`   Demo: `python3 -m core.cli demo`

## Module B (Cybersecurity)
Answer a questionnaire:
`python3 -m modules.cybersecurity.cli run CLIENT POLICY_FOLDER questions.csv answers.csv`
Review: `... review CLIENT` then `approve|reject|edit CLIENT ID`; export: `... finalize CLIENT answers.csv final.csv`
Accuracy check (weekly): `python3 -m modules.cybersecurity.cli eval --log`

## Module A (Healthcare) - SYNTHETIC data only
Draft an appeal: `python3 -m modules.healthcare.cli appeal CLIENT POLICY_FOLDER denial.txt [--facts facts.txt]`
Accuracy check: `python3 -m modules.healthcare.cli eval --log`
Review queue: `python3 -m modules.cybersecurity.cli review CLIENT`

## Module C (Energy / CloseLoop Pro)
Quote from a bill: `python3 -m modules.energy.cli quote CLIENT "Smith house" --bill-file bill.txt --state AZ --pdf quote.pdf`
Quote from usage: `... quote CLIENT NAME --kwh-year 10800 --psh 5 --rate 0.15 [--battery-kw 2 --battery-hours 10]`
Projects: `... projects CLIENT` | `... show CLIENT P-0001` | `... status CLIENT P-0001 sent|won|lost`
Accuracy check: `python3 -m modules.energy.cli eval --log`
Default prices, sun hours and rates are APPROXIMATE samples: set your own before quoting real customers.

## Module D (Biotech research evidence finder)
Finds and cites published research. Never gives medical, dosing or treatment advice.
Ask: `python3 -m modules.biotech.cli ask CLIENT PAPERS_FOLDER "your question"`
Fetch open-access papers: `python3 -m modules.biotech.cli fetch "kinase inhibitor" ~/papers --max 5`
Accuracy check: `python3 -m modules.biotech.cli eval --log`
