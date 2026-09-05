# ACL-DP Reproducibility Package

## Adaptive Cognitive Load Dark Pattern (ACL-DP) Framework

Version: 1.0.0

This repository contains the reproducibility package accompanying the research article on the ACL-DP framework for computational auditing of cookie consent interfaces.

---

# Repository Purpose

This repository provides the materials required to reproduce the ACL-DP computational auditing and analysis workflow.

The package has four primary objectives:

- provide a transparent operational definition of the ACL-DP framework;
- enable replication of the executable computational audit workflow;
- provide the anonymized analytical dataset used for the reported analyses;
- support methodological transparency and reproducible research in Human-Computer Interaction (HCI), usable privacy, and computational auditing.

The package contains the executable ACL-DP audit and analysis pipeline, the operational codebook, the anonymized analytical dataset, supporting anonymization documentation, and representative interface examples.

---

# ACL-DP Framework Overview

ACL-DP is a computational measurement framework for examining observable structural characteristics of cookie consent interfaces.

The final framework contains three scored mechanism families:

- **Effort Engineering (EE)** — observable interaction effort associated with exercising privacy choices.
- **Attention Engineering (AE)** — observable differences in the prominence and presentation of consent actions.
- **Cognitive Load (CL) Amplification** — observable Layer-2 interface conditions associated with configuration complexity, information density, and reduced explanatory support.

ACL-DP does not directly measure users' cognition, attention, comprehension, cognitive workload, or behavioral responses. The framework operationalizes observable interface-level characteristics as computational indicators of consent-interface conditions.

The final composite score is defined as:

```text
ACLDP_TOTAL_SCORE =
    EFFORT_SCORE
    + ATTENTION_SCORE
    + COGNITIVE_LOAD_SCORE
```

The theoretical range of `ACLDP_TOTAL_SCORE` is **0-7**.

The final scored mechanism definitions are:

```text
EFFORT_SCORE =
    MECH_EE_ClickAsymmetry
    + MECH_EE_HiddenReject

ATTENTION_SCORE =
    MECH_AE_PrimaryAccept
    + MECH_AE_ProminenceAsymmetry

COGNITIVE_LOAD_SCORE =
    MECH_CL_HighComplexity
    + MECH_CL_HighInfoDensity
    + MECH_CL_GermaneSuppression
```

`MECH_CL_HighToggleVolume` may be retained for descriptive or sensitivity analysis but is not included in the final `COGNITIVE_LOAD_SCORE`.

---

# Files Included in the Package

```text
ACL-DP/

├── README.md
├── LICENSE.txt
├── ACLDP_code.py
├── CodeBook.txt
├── acldp_dataset_anonymized.csv
├── acldp_anonymization_report.txt
└── InterfaceSamples.zip
```

## `ACLDP_code.py`

`ACLDP_code.py` is the executable end-to-end computational audit and analysis pipeline.

It supports three modes:

```text
audit
analyze
all
```

The script includes:

- Playwright-based browser acquisition;
- iframe-aware inspection of observable consent controls;
- Layer-1 consent-banner detection;
- Accept, Reject, and Manage Preferences pathway reconstruction;
- interaction-click measurement;
- CMP and IAB TCF evidence detection;
- Layer-2 preference-panel inspection;
- extraction of toggle, vendor, text-density, and complexity variables;
- calculation of EE, AE, and CL indicators;
- calculation of mechanism-level scores;
- calculation of `ACLDP_TOTAL_SCORE`;
- descriptive statistical summaries;
- Spearman correlation analysis;
- threshold-sensitivity analysis;
- structured evidence and screenshot output for new audit runs.

The script also distinguishes between acquisition of new audit evidence and reproduction of the final scoring and statistical analyses from an existing analytical dataset.

---

## `CodeBook.txt`

`CodeBook.txt` contains the final ACL-DP operational definitions and scoring rules used by the executable code.

It documents:

- EE indicators and analytical scope;
- AE indicators;
- CL indicators and Layer-2 analytical scope;
- final mechanism-score definitions;
- final composite-score definition;
- threshold rules;
- exclusions from the final composite score;
- mechanism-specific denominators;
- interpretation of CL indicators as interface-level proxies rather than direct measures of experienced cognitive workload.

The codebook and executable code use the same final scoring definition.

---

## `acldp_dataset_anonymized.csv`

This file contains the anonymized analytical dataset used to reproduce the reported ACL-DP measurements and statistical analyses.

The dataset preserves the analytical schema and variables required for reproducibility while replacing website identifiers, domains, URLs, and other identifying fields with pseudonymous values.

The dataset contains observable audit variables relating to:

- audit status and collection configuration;
- consent-banner characteristics;
- CMP and TCF evidence;
- Layer-1 controls;
- Layer-2 configuration;
- EE variables;
- AE variables;
- CL variables;
- click counts;
- information-density measures;
- complexity measures;
- evidence and reference fields.

The anonymized dataset should be used with the `analyze` mode of `ACLDP_code.py`.

---

## `acldp_anonymization_report.txt`

This file documents the anonymization procedure applied to the analytical dataset.

It reports the retained schema and analytical values, describes the fields that were pseudonymized, and records verification checks confirming removal of original website identifiers and domains.

The anonymization key linking original websites to pseudonymous identifiers is not included in the public package.

---

## `InterfaceSamples.zip`

This archive contains representative interface examples retained to support interpretation of the computational audit process.

The examples are supplementary materials and are not required for execution of the statistical analysis pipeline.

---

## `LICENSE.txt`

The code is distributed under the MIT License.

---

# Software Requirements

The executable pipeline requires Python and the following principal packages:

```text
Python 3.12
pandas
NumPy
SciPy
Playwright
```

Install the Python dependencies using:

```bash
pip install pandas numpy scipy playwright
```

Install the Chromium browser required by Playwright:

```bash
playwright install chromium
```

---

# How to Reproduce the Reported Analysis

## 1. Clone or download the repository

```bash
git clone https://github.com/DrMaysoonAbulkhair/ACL-DP.git
cd ACL-DP
```

## 2. Install the required software

```bash
pip install pandas numpy scipy playwright
playwright install chromium
```

## 3. Reproduce the final ACL-DP scoring and statistical outputs

Run:

```bash
python ACLDP_code.py analyze     --input acldp_dataset_anonymized.csv     --results results
```

The analysis mode applies the final deterministic ACL-DP scoring definition and generates the analytical outputs.

The resulting files include:

```text
results/
├── acldp_scored_interfaces.csv
├── descriptive_summary.csv
├── spearman_correlations.csv
├── threshold_sensitivity.csv
└── analysis_metadata.json
```

The analysis metadata records the scoring definition used for the run, including the exclusion of non-final indicators from the composite score.

---

# How to Run a New Computational Audit

A text or CSV file containing domains or URLs can be supplied to the audit mode.

Example:

```bash
python ACLDP_code.py audit     --input domains.txt     --output acldp_audit_raw.csv     --screenshots artifacts/screenshots     --evidence artifacts/evidence     --headless
```

To run acquisition followed immediately by ACL-DP scoring and analysis:

```bash
python ACLDP_code.py all     --input domains.txt     --output acldp_audit_raw.csv     --results results     --headless
```

For a new acquisition run, the pipeline records the configured browser environment and produces raw audit evidence before applying the final ACL-DP scoring rules.

---

# Analytical Scope

The valid denominator differs by mechanism.

- **AE and general interface-level analyses** are evaluated across observable consent interfaces.
- **EE analyses requiring rejection-path evidence** are restricted to interfaces with observable Accept and Reject click paths.
- **CL analyses** are restricted to interfaces with an accessible Layer-2 preference panel.

Accordingly, percentages generated from these subsets should be interpreted as descriptive findings for the analyzed interfaces and not as population-level prevalence estimates for the broader web ecosystem.

---

# Construct Interpretation

ACL-DP quantifies observable interface properties.

In particular, CL indicators are interface-level proxies representing observable complexity, information density, and explanatory-support conditions. They do not constitute direct measurements of users' experienced cognitive load.

Behavioral, attentional, comprehension, or cognitive-workload effects require separate participant-based validation.

---

# Reproducibility Statement

The repository provides the executable computational audit and analysis pipeline, the anonymized analytical dataset, and the ACL-DP operational codebook required to reproduce the reported mechanism-level measurements and statistical analyses.

The final scoring model consists of EE, AE, and CL only:

```text
ACLDP_TOTAL_SCORE =
    EFFORT_SCORE
    + ATTENTION_SCORE
    + COGNITIVE_LOAD_SCORE
```

The codebook and executable code use the same scoring definition.

The anonymized dataset supports reproduction of the reported analytical results without disclosing the identities of audited websites.

For provenance, the executable acquisition component provides a documented implementation for replicating the computational audit workflow. If the historical manuscript dataset was collected using an earlier crawler implementation, the acquisition component should be described as a reproducible implementation of the documented audit procedure rather than as the original historical source code unless source-code provenance has been independently verified.

---

# Data Protection and Ethical Use

The public analytical dataset is anonymized to reduce disclosure risks.

Original website identifiers, domains, URLs, and pseudonymization keys are not included in the public dataset.

Users of the repository should avoid attempting to re-identify audited websites from anonymized evidence.

---

# Citation

If you use this repository, please cite the accompanying publication and the repository.

---

# License

Code: MIT License.

Use of the anonymized research dataset and supporting documentation should follow the conditions specified in the repository and accompanying publication.

---

# Contact

For questions regarding the ACL-DP framework or this reproducibility package, please contact the corresponding author of the associated publication.
