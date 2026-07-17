{\rtf1\ansi\ansicpg1252\cocoartf2870
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\paperw11900\paperh16840\margl1440\margr1440\vieww11520\viewh8400\viewkind0
\pard\tx720\tx1440\tx2160\tx2880\tx3600\tx4320\tx5040\tx5760\tx6480\tx7200\tx7920\tx8640\pardirnatural\partightenfactor0

\f0\fs24 \cf0 import re\
import warnings\
from pathlib import Path\
\
import numpy as np\
import pandas as pd\
from scipy.stats import spearmanr\
import statsmodels.api as sm\
import statsmodels.formula.api as smf\
from statsmodels.tools.sm_exceptions import PerfectSeparationError\
\
warnings.filterwarnings("ignore", category=RuntimeWarning)\
warnings.filterwarnings("ignore", category=UserWarning)\
\
# =========================================================\
# 1. Load data\
# =========================================================\
CSV_PATH = "CookiesConsentDataset/cookie_consent_dataset_1000_audited.csv"\
df = pd.read_csv(CSV_PATH)\
df.columns = [c.strip() for c in df.columns]\
\
print("Loaded shape:", df.shape)\
\
\
# =========================================================\
# 2. Helper functions\
# =========================================================\
def find_col(df_cols, candidates):\
    df_map = \{c.lower(): c for c in df_cols\}\
    for cand in candidates:\
        if cand.lower() in df_map:\
            return df_map[cand.lower()]\
\
    norm = lambda s: re.sub(r"[^a-z0-9]+", "", s.lower())\
    norm_map = \{norm(c): c for c in df_cols\}\
    for cand in candidates:\
        if norm(cand) in norm_map:\
            return norm_map[norm(cand)]\
    return None\
\
\
def to_numeric(series):\
    return pd.to_numeric(series, errors="coerce")\
\
\
def to_binary_yes_no(series):\
    if series is None:\
        return pd.Series(dtype=float)\
\
    s = series.astype(str).str.strip().str.lower()\
    out = pd.Series(np.nan, index=series.index, dtype=float)\
\
    yes_vals = \{"1", "yes", "y", "true", "present", "available"\}\
    no_vals = \{"0", "no", "n", "false", "absent", "not available"\}\
\
    out[s.isin(yes_vals)] = 1\
    out[s.isin(no_vals)] = 0\
\
    num = pd.to_numeric(series, errors="coerce")\
    out[num == 1] = 1\
    out[num == 0] = 0\
    return out\
\
\
def fmt_num(x, nd=3):\
    if pd.isna(x):\
        return "NA"\
    return f"\{x:.\{nd\}f\}"\
\
\
def fmt_p(x):\
    if pd.isna(x):\
        return "NA"\
    if x < 0.001:\
        return "<0.001"\
    return f"\{x:.3f\}"\
\
\
def fmt_ci(lo, hi, nd=3):\
    if pd.isna(lo) or pd.isna(hi):\
        return "NA"\
    return f"[\{lo:.\{nd\}f\}, \{hi:.\{nd\}f\}]"\
\
\
def latex_escape(s):\
    return str(s).replace("_", r"\\_")\
\
\
# =========================================================\
# 3. Detect columns\
# =========================================================\
col_banner = find_col(df.columns, [\
    "Cookie_Banner_Present", "cookie_banner_present"\
])\
col_l2 = find_col(df.columns, [\
    "L2_Available", "l2_available", "Layer_2_Available"\
])\
\
col_accept_click = find_col(df.columns, [\
    "Accept_Click_Count", "accept_click_count"\
])\
col_reject_click = find_col(df.columns, [\
    "Reject_Click_Count", "reject_click_count"\
])\
col_hidden_reject = find_col(df.columns, [\
    "EE_Hidden_Reject_Path", "hidden_reject_path"\
])\
\
col_primary_accept = find_col(df.columns, [\
    "AE_Primary_Action_Is_Accept", "primary_action_is_accept"\
])\
col_accept_prom = find_col(df.columns, [\
    "AE_Accept_Button_Prominence_1to3", "AE_Accept_Button_Prominence", "accept_button_prominence"\
])\
col_reject_prom = find_col(df.columns, [\
    "AE_Reject_Button_Prominence_1to3", "AE_Reject_Button_Prominence", "reject_button_prominence"\
])\
\
col_complexity = find_col(df.columns, [\
    "CL_Toggle_Vendor_Complexity_Index", "complexity_index"\
])\
col_info_density = find_col(df.columns, [\
    "L2_Information_Density_Score_1to5", "L2_Information_Density_Score", "information_density_score"\
])\
col_toggle_count = find_col(df.columns, [\
    "L2_Toggle_Count", "toggle_count"\
])\
col_germane = find_col(df.columns, [\
    "CL_Germane_Suppression_Indicators", "germane_suppression_indicators"\
])\
\
col_cmp = find_col(df.columns, ["CMP_Vendor", "cmp_vendor", "CMP_Group"])\
col_sector = find_col(df.columns, ["Sector_Group", "sector_group"])\
\
print("\\nDetected columns:")\
for k, v in \{\
    "Cookie_Banner_Present": col_banner,\
    "L2_Available": col_l2,\
    "Accept_Click_Count": col_accept_click,\
    "Reject_Click_Count": col_reject_click,\
    "EE_Hidden_Reject_Path": col_hidden_reject,\
    "AE_Primary_Action_Is_Accept": col_primary_accept,\
    "AE_Accept_Button_Prominence": col_accept_prom,\
    "AE_Reject_Button_Prominence": col_reject_prom,\
    "CL_Toggle_Vendor_Complexity_Index": col_complexity,\
    "L2_Information_Density_Score": col_info_density,\
    "L2_Toggle_Count": col_toggle_count,\
    "CL_Germane_Suppression_Indicators": col_germane,\
    "CMP_Vendor": col_cmp,\
    "Sector_Group": col_sector,\
\}.items():\
    print(f"\{k\}: \{v\}")\
\
\
# =========================================================\
# 4. Restrict to the correct analytical subset\
#    Stage 1/2/3 main sample = observable consent interfaces\
# =========================================================\
if col_banner:\
    banner_flag = to_binary_yes_no(df[col_banner])\
    df_main = df[banner_flag == 1].copy()\
else:\
    # fallback: infer banner sample from presence of primary action / accept button / click count\
    inferred_banner = pd.Series(False, index=df.index)\
    if col_primary_accept:\
        inferred_banner |= to_binary_yes_no(df[col_primary_accept]).fillna(0).astype(int).eq(1)\
    if col_accept_click:\
        inferred_banner |= to_numeric(df[col_accept_click]).notna()\
    df_main = df[inferred_banner].copy()\
\
print("\\nMain analytical subset shape:", df_main.shape)\
\
# Layer-2 nested subset\
if col_l2:\
    l2_flag = to_binary_yes_no(df_main[col_l2])\
    df_l2 = df_main[l2_flag == 1].copy()\
else:\
    # infer from info density / toggle / complexity availability\
    inferred_l2 = pd.Series(False, index=df_main.index)\
    if col_info_density:\
        inferred_l2 |= to_numeric(df_main[col_info_density]).notna()\
    if col_toggle_count:\
        inferred_l2 |= to_numeric(df_main[col_toggle_count]).notna()\
    if col_complexity:\
        inferred_l2 |= to_numeric(df_main[col_complexity]).notna()\
    df_l2 = df_main[inferred_l2].copy()\
\
print("Layer-2 subset shape:", df_l2.shape)\
\
\
# =========================================================\
# 5. Build mechanism indicators on main sample\
# =========================================================\
accept_click = to_numeric(df_main[col_accept_click]) if col_accept_click else pd.Series(np.nan, index=df_main.index)\
reject_click = to_numeric(df_main[col_reject_click]) if col_reject_click else pd.Series(np.nan, index=df_main.index)\
\
# valid effort subset = interfaces with observable rejection pathway\
effort_valid = accept_click.notna() & reject_click.notna()\
df_main["EFFORT_VALID"] = effort_valid.astype(int)\
\
# Effort indicators\
df_main["MECH_EE_ClickAsymmetry"] = np.where(\
    effort_valid & (reject_click > accept_click), 1, 0\
)\
\
if col_hidden_reject:\
    df_main["MECH_EE_HiddenReject"] = to_binary_yes_no(df_main[col_hidden_reject]).fillna(0).astype(int)\
else:\
    df_main["MECH_EE_HiddenReject"] = 0\
\
# Attention indicators\
if col_primary_accept:\
    df_main["MECH_AE_PrimaryAccept"] = to_binary_yes_no(df_main[col_primary_accept]).fillna(0).astype(int)\
else:\
    df_main["MECH_AE_PrimaryAccept"] = 0\
\
if col_accept_prom and col_reject_prom:\
    accept_prom = to_numeric(df_main[col_accept_prom])\
    reject_prom = to_numeric(df_main[col_reject_prom])\
    df_main["MECH_AE_ProminenceAsymmetry"] = np.where(\
        accept_prom.notna() & reject_prom.notna() & (accept_prom > reject_prom), 1, 0\
    )\
else:\
    df_main["MECH_AE_ProminenceAsymmetry"] = 0\
\
# Cognitive-load indicators\
# IMPORTANT: compute on Layer-2 subset, then merge back to main as zeros for non-L2 interfaces\
df_main["MECH_CL_HighComplexity"] = 0\
df_main["MECH_CL_HighInfoDensity"] = 0\
df_main["MECH_CL_HighToggleVolume"] = 0\
df_main["MECH_CL_GermaneSuppression"] = 0\
\
if len(df_l2) > 0:\
    if col_complexity:\
        complexity = to_numeric(df_l2[col_complexity])\
        df_main.loc[df_l2.index, "MECH_CL_HighComplexity"] = np.where(complexity >= 20, 1, 0)\
\
    if col_info_density:\
        info_density = to_numeric(df_l2[col_info_density])\
        df_main.loc[df_l2.index, "MECH_CL_HighInfoDensity"] = np.where(info_density >= 4, 1, 0)\
\
    if col_toggle_count:\
        toggle_count = to_numeric(df_l2[col_toggle_count])\
        df_main.loc[df_l2.index, "MECH_CL_HighToggleVolume"] = np.where(toggle_count >= 10, 1, 0)\
\
    if col_germane:\
        germane = to_binary_yes_no(df_l2[col_germane]).fillna(0).astype(int)\
        df_main.loc[df_l2.index, "MECH_CL_GermaneSuppression"] = germane.values\
\
# =========================================================\
# 6. Composite scores\
#    Use the manuscript-consistent composite definition\
# =========================================================\
df_main["EFFORT_SCORE"] = df_main["MECH_EE_ClickAsymmetry"] + df_main["MECH_EE_HiddenReject"]\
df_main["ATTENTION_SCORE"] = df_main["MECH_AE_PrimaryAccept"] + df_main["MECH_AE_ProminenceAsymmetry"]\
\
# manuscript-consistent CL score:\
# if your paper excludes toggle volume from final CL score, keep it excluded here\
df_main["COGNITIVE_LOAD_SCORE"] = (\
    df_main["MECH_CL_HighComplexity"]\
    + df_main["MECH_CL_HighInfoDensity"]\
    + df_main["MECH_CL_GermaneSuppression"]\
)\
\
df_main["ACLDP_TOTAL_SCORE"] = (\
    df_main["EFFORT_SCORE"]\
    + df_main["ATTENTION_SCORE"]\
    + df_main["COGNITIVE_LOAD_SCORE"]\
)\
\
# derived non-tautological DV for OLS:\
# use standardized total score? no\
# use total score? still tautological if predictors are exact components\
# Better: use a structural outcome not mechanically identical to predictors\
# For publication-valid Stage 2, use ACLDP_TOTAL_SCORE descriptively + correlations,\
# and for OLS use a reduced-form target:\
#   "Manipulation intensity excluding the focal predictor family" is awkward.\
# A better practical choice is to model ACLDP_TOTAL_SCORE using *indicator-level controls*\
# OR present OLS as exploratory using standardized family scores but excluding direct sum relation.\
#\
# Here we compute an exploratory model of cognitive-load burden / interface burden, but\
# to stay close to your framing, we use:\
#   DV = ACLDP_TOTAL_SCORE\
#   predictors = ATTENTION_SCORE, EFFORT_SCORE, COGNITIVE_LOAD_SCORE\
# This remains mechanically related.\
#\
# Therefore, publication-valid recommendation:\
# do NOT use OLS on total score built from the same family scores unless you state it is descriptive.\
# Instead, model a structural outcome:\
#   DV = MECH_EE_HiddenReject\
#   and an ecosystem model on ACLDP_TOTAL_SCORE.\
#\
# If you still want an interaction model, use a continuous non-identical target if present.\
# Fallback target below:\
#   CL burden proxy if available.\
#\
# We'll implement:\
#   OLS exploratory ecosystem model on ACLDP_TOTAL_SCORE\
#   with CMP, sector, and Layer-2 info density (not the same as direct sum components)\
# and a Stage 2 correlation matrix on composite scores.\
#\
# For your requested OLS interaction table, we fit it but flag it as descriptive-only.}