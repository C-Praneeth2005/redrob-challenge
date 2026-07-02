# Intelligent Candidate Discovery & Ranking System — Redrob Hackathon

This repository contains the offline candidate ranking pipeline built for the **Intelligent Candidate Discovery & Ranking Challenge** by **team_antigravity**.

The goal is to select and rank the top 100 candidate profiles from a pool of 100,000 candidates for a hybrid **Senior AI Engineer — Founding Team** role at Redrob AI in Noida/Pune.

## 🚀 Setup & Installation

1. Clone this repository:
   ```bash
   git clone <your-repo-link>
   cd India_runs_data_and_ai_challenge
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Ensure you have the `candidates.jsonl` file in this directory.

---

## 🏃 Reproduction Command

To reproduce the submission CSV, run the following command:

```bash
python rank.py --candidates ./candidates.jsonl --out team_antigravity.csv
```

*   **Runtime:** ~5.9 seconds
*   **Memory:** < 100 MB RAM
*   **Environment:** CPU-only, offline, Python 3.13+

---

## 🛠️ Architecture & Methodology

Our ranking system uses a strict **hierarchical heuristic logic** built specifically to combat the traps in the challenge dataset (Honeypots and Keyword Stuffers) while remaining within the strict 5-minute CPU constraint.

### 1. Traps & Honeypot Filtering
*   **Company Founding Violations:** Filters out fake profiles stating experience at companies before they were founded (e.g., working at *CRED* in 2017 when founded in 2018, or *Sarvam AI* in 2020 when founded in 2023).
*   **Zero-Duration Skills:** Excludes candidates claiming "expert" or "advanced" proficiency in skills that have `duration_months == 0`.
*   **Consulting-Only Profiles:** Excludes candidates whose entire career history consists solely of service-based IT companies (e.g. TCS, Infosys, Wipro) without any product-company experience.

### 2. Multi-Factor Scoring Model
The scoring function calculates candidate fit as follows:
*   **Role Title Match (High Weight):** Maps titles to relevance tiers. AI/ML Engineering titles (Lead AI, ML Engineer, Applied Scientist) get a high base score; software engineering/backend get a moderate score; non-technical titles (Civil Engineer, HR, Graphic Design) receive a massive penalty to filter out keyword stuffers.
*   **Target YOE (Medium Weight):** Ideal experience is 5–9 years (scoring 1.0). Experience outside this range is given a scaled discount.
*   **Core Skill Match (Medium Weight):** Evaluates core vector search, embedding models, indexing (FAISS/Pinecone/Milvus), evaluation frameworks (NDCG/MRR/MAP), and Python, weighted by their stated proficiency level and months of usage.
*   **Location Fit:** Prioritizes Noida/Pune hybrid availability and checks relocation willingness.

### 3. Engagement Modifier (Multiplicative)
Multiplies the core fit score by platform active availability:
*   **Notice Period:** Sub-30 days notice gets a `1.0` multiplier; longer notices are penalized.
*   **Recency:** Active within last 30 days is prioritized; inactive profiles are down-weighted.
*   **Recruiter Response Rate:** Directly scales the candidate's responsiveness.

### 4. Dynamic Reasoning Engine
To fulfill the manual review criteria (Stage 4), our script generates natural, fact-based 1-2 sentence summaries by:
*   Extracting exact candidate facts (YoE, Title, Company).
*   Locating the exact sentence in their history description matching search/ranking keywords.
*   Formatting notice/availability details.
*   Cycling through multiple distinct syntactic layouts to ensure reasoning strings are varied and non-templated.
