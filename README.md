# ACL-DP
Adaptive Cognitive Load Dark Pattern (ACL-DP): A Computational Framework for Measuring Cognitive Manipulation in Cookie Consent Interfaces.
# ACL-DP Reproducibility Package

## Adaptive Cognitive Load Dark Pattern (ACL-DP) Framework

Version: 1.0.0

This repository contains the reproducibility package accompanying the research article:

Adaptive Cognitive Load Dark Pattern (ACL-DP): A Computational Framework for Measuring Cognitive Manipulation in Cookie Consent Interfaces.

---

# Repository Purpose

This repository provides the complete supplementary materials required to reproduce the computational auditing methodology, analytical procedures, and evaluation results presented in the ACL-DP framework.

The repository has four primary objectives:

- provide a transparent operational definition of the ACL-DP framework;
- enable independent replication of the computational audit;
- facilitate reuse of the anonymized research dataset for future studies;
- support methodological transparency and reproducible research in Human–Computer Interaction (HCI), usable privacy, and computational auditing.

The repository contains the operational codebook, computational audit protocol, analytical scripts, anonymized derived dataset, documentation, and benchmark materials used in the study.

---

# ACL-DP Framework Overview

The Adaptive Cognitive Load Dark Pattern (ACL-DP) framework is a computational measurement framework for assessing the structural characteristics of cookie consent interfaces.

Rather than inferring users' psychological states directly, ACL-DP operationalizes observable interface properties into measurable cognitive mechanisms that can be automatically extracted from consent interfaces.

The framework consists of four computational mechanisms:

- Effort Engineering (EE) – procedural effort required to exercise privacy choices.
- Attention Engineering (AE)– visual and interaction design strategies influencing user attention.
- Cognitive Load Amplification (CL)– interface complexity that increases cognitive processing demands.
- Adaptive Architecture (AA)– adaptive interface behaviors that modify consent interactions across sessions or environments.

These mechanisms are combined into the composite ACL-DP score used throughout the paper.

---

# Repository Contents

```
ACL-DP-Reproducibility/

├── README.md
├── LICENSE
├── CITATION.cff
├── requirements.txt
│
├── codebook/
│     ACLDP_Operational_Codebook.pdf
│
├── protocol/
│     Computational_Audit_Protocol.pdf
│
├── dataset/
│     acldp_dataset_anonymized.csv
│     data_dictionary.csv
│
├── scripts/
│     compute_acldp_scores.py
│     statistical_analysis.py
│     robustness_analysis.py
│
├── benchmark/
│     annotation_protocol.pdf
│     benchmark_labels.csv
│     reliability_results.csv
│
└── examples/
      example_consent_interfaces.pdf
```

---

# Dataset Description

The repository includes an anonymized derived dataset generated from the computational audit.

The dataset contains only derived analytical variables and does not include:

- website source code
- browser session data
- cookies
- personally identifiable information
- proprietary Consent Management Platform assets
- copyrighted website content

Each audited website is represented by an anonymous identifier (e.g., `Domain_001`).

Example variables include:

| Variable | Description |
|-----------|-------------|
| Domain_ID | Anonymous website identifier |
| Sector | Website sector/category |
| CMP | Consent Management Platform |
| Consent_Layer_Depth | Maximum consent depth |
| Reject_All | Presence of Reject All option |
| EE_SCORE | Effort Engineering score |
| AE_SCORE | Attention Engineering score |
| CL_SCORE | Cognitive Load Amplification score |
| AA_SCORE | Adaptive Architecture score |
| ACLDP_TOTAL_SCORE | Composite ACL-DP score |
| GDPR_SCORE | GDPR compliance indicator |
| RISK_LEVEL | Derived privacy risk classification |

Complete variable definitions are provided in `data_dictionary.csv` and the operational codebook.

---

# How to Reproduce the Results

The analyses reported in the manuscript can be reproduced using the supplied dataset and analytical scripts.

## Step 1

Clone the repository

```bash
git clone https://github.com/USERNAME/ACL-DP-Reproducibility.git

cd ACL-DP-Reproducibility
```

## Step 2

Create the Python environment

```bash
pip install -r requirements.txt
```

or

```bash
conda env create -f environment.yml
conda activate acldp
```

## Step 3

Compute ACL-DP scores

```bash
python scripts/compute_acldp_scores.py
```

## Step 4

Run the statistical analyses

```bash
python scripts/statistical_analysis.py
```

## Step 5

Run robustness analyses

```bash
python scripts/robustness_analysis.py
```

The scripts reproduce the principal descriptive statistics, correlation analyses, regression models, confidence intervals, and robustness evaluations reported in the manuscript.

---

# Software Requirements

The analyses were developed and tested using:

| Software | Version |
|----------|---------|
| Python | 3.12 |
| Playwright | 1.58.0 |
| Chromium | Stable Release |
| pandas | 2.x |
| NumPy | 2.x |
| SciPy | 1.x |
| statsmodels | 0.14.x |
| scikit-learn | 1.x |
| matplotlib | 3.x |

Complete package versions are listed in `requirements.txt`.

---

# Folder Descriptions

## codebook/

Contains the complete ACL-DP operational codebook, including variable definitions, scoring rules, thresholds, and coding examples.

---

## protocol/

Contains the computational audit protocol describing website sampling, browser automation, workflow reconstruction, backend verification, synchronization procedures, and quality-control measures.

---

## dataset/

Contains the anonymized derived research dataset and accompanying data dictionary.

---

## scripts/

Contains the Python scripts used to compute ACL-DP mechanism scores, perform statistical analyses, and evaluate robustness.

---

## benchmark/

Contains the human annotation protocol, benchmark labels, and inter-rater reliability results supporting validation of the ACL-DP framework.

---

## examples/

Provides representative examples of consent interfaces and reconstructed workflows where redistribution is legally and ethically permissible.

---

# Reproducibility Statement

This repository is intended to support computational reproducibility of the ACL-DP framework. All analyses reported in the associated publication can be reproduced using the provided scripts and anonymized derived dataset.

To protect legal, ethical, and copyright interests, website identifiers and proprietary interface assets have been removed or anonymized. The repository contains derived research data rather than raw website content.

---

# Citation

If you use this repository, please cite both the accompanying publication and this repository.

BibTeX and citation metadata are provided in `CITATION.cff`.

---

# License

- Code: MIT License
- Documentation:CC BY 4.0
- Dataset: CC BY 4.0 (derived anonymized data only)

---

# Contact

For questions regarding the ACL-DP framework or this repository, please contact the corresponding author listed in the associated publication.

---

# Acknowledgements

If you use this repository in academic research, please cite the accompanying article. Proper citation supports continued development of open, reproducible research resources for usable privacy, Human–Computer Interaction, and computational auditing.
