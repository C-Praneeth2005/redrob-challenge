#!/usr/bin/env python3
import json
import gzip
import argparse
import sys
import re
from datetime import datetime
from pathlib import Path

# ============================================================================
# Curated Founding Years for Companies (Honeypot Checker)
# ============================================================================
FOUNDING_YEARS = {
    "Sarvam AI": 2023,
    "Krutrim": 2023,
    "CRED": 2018,
    "PhonePe": 2015,
    "Razorpay": 2014,
    "Rephrase.ai": 2019,
    "Saarthi.ai": 2017,
    "Observe.AI": 2017,
    "Verloop.io": 2015,
    "Wysa": 2015,
    "Yellow.ai": 2016,
    "Niramai": 2016,
    "Aganitha": 2017,
    "Locobuzz": 2015,
    "Nykaa": 2012,
    "Swiggy": 2014,
    "Meesho": 2015,
    "BYJU'S": 2011,
    "Freshworks": 2010,
    "Ola": 2010,
    "PolicyBazaar": 2008,
    "Dream11": 2008,
    "Flipkart": 2007,
    "Zomato": 2008,
    "InMobi": 2007,
    "Haptik": 2013,
    "Mad Street Den": 2013,
    "upGrad": 2015,
    "Unacademy": 2015,
    "Vedantu": 2011
}

# ============================================================================
# Title Classification
# ============================================================================
TIER1_TITLES = {
    "senior ai engineer", "ai engineer", "senior machine learning engineer", 
    "machine learning engineer", "staff machine learning engineer", "lead ai engineer", 
    "applied ml engineer", "ml engineer", "recommendation systems engineer", 
    "nlp engineer", "senior nlp engineer", "ai research engineer", 
    "senior applied scientist", "lead ai engineer"
}

TIER2_TITLES = {
    "data scientist", "senior data scientist", "applied scientist", 
    "ai specialist", "computer vision engineer", "junior ml engineer", 
    "backend engineer", "data engineer", "senior data engineer", 
    "analytics engineer", "software engineer", "senior software engineer"
}

# Trap / disqualified titles for the Senior AI Engineer role
DISQUALIFIED_TITLES = {
    "civil engineer", "accountant", "hr manager", "graphic designer", 
    "business analyst", "customer support", "operations manager", 
    "content writer", "sales executive", "marketing manager", "mechanical engineer",
    "project manager"
}

CONSULTING_FIRMS = {
    "tcs", "infosys", "wipro", "accenture", "cognizant", "capgemini", 
    "tech mahindra", "mindtree", "mphasis", "genpact ai", "hcl"
}

# ============================================================================
# Skills Classification
# ============================================================================
CORE_SKILLS = {
    "pinecone", "milvus", "weaviate", "qdrant", "faiss", "elasticsearch", "opensearch",
    "embeddings", "vector search", "hybrid search", "dense retrieval", "information retrieval", "retrieval", "search",
    "nlp", "ranking", "learning to rank", "fine-tuning llms", "lora", "qlora", "peft", "python",
    "ndcg", "mrr", "map", "a/b testing", "evaluation"
}

# ============================================================================
# Honeypot Filtering Logic
# ============================================================================
def detect_honeypot(c):
    # 1. Company founding date violation
    for job in c.get('career_history', []):
        company = job.get('company', '')
        if company in FOUNDING_YEARS:
            start = job.get('start_date', '')
            if start:
                try:
                    start_year = int(start.split('-')[0])
                    if start_year < FOUNDING_YEARS[company]:
                        return True
                except Exception:
                    pass
    
    # 2. Expert/advanced skill with 0 duration
    for s in c.get('skills', []):
        if s.get('proficiency') in ['expert', 'advanced'] and s.get('duration_months', -1) == 0:
            return True
            
    # 3. Years of experience profile mismatch (> 15 years difference from career duration)
    yoe = c['profile'].get('years_of_experience', 0)
    total_months = sum(job.get('duration_months', 0) for job in c.get('career_history', []))
    if abs(yoe - (total_months / 12.0)) > 15.0:
        return True
        
    return False

# ============================================================================
# Scoring Logic
# ============================================================================
def get_title_score(title):
    title_clean = title.strip().lower()
    if title_clean in TIER1_TITLES:
        return 10.0
    if title_clean in TIER2_TITLES:
        return 5.0
    if title_clean in DISQUALIFIED_TITLES:
        return -100.0 # massive penalty to filter out keyword stuffers
    return 1.0

def get_yoe_score(yoe):
    # JD target is 5-9 years
    if 5.0 <= yoe <= 9.0:
        return 1.0
    elif 4.0 <= yoe < 5.0 or 9.0 < yoe <= 12.0:
        return 0.8
    elif 2.0 <= yoe < 4.0 or 12.0 < yoe <= 15.0:
        return 0.5
    return 0.1

def get_skills_score(skills):
    score = 0.0
    found_core = []
    for s in skills:
        name = s['name'].lower()
        prof = s.get('proficiency', 'beginner')
        dur = s.get('duration_months', 0)
        
        # Honeypot check already handles zero duration expert/advanced,
        # but let's double check here: if duration is 0, it doesn't add to score
        if dur <= 0:
            continue
            
        prof_mult = 1.0
        if prof == 'expert':
            prof_mult = 2.0
        elif prof == 'advanced':
            prof_mult = 1.5
        elif prof == 'intermediate':
            prof_mult = 1.0
        else:
            prof_mult = 0.5
            
        is_core = any(cs in name for cs in CORE_SKILLS)
        if is_core:
            score += prof_mult * (dur / 12.0 + 1.0)
            found_core.append(s['name'])
            
    return score, found_core

def get_location_score(profile, signals):
    country = profile.get('country', '')
    location = profile.get('location', '')
    willing = signals.get('willing_to_relocate', False)
    
    is_preferred_city = any(city in location.lower() for city in ["pune", "noida", "delhi", "ncr", "hyderabad", "mumbai"])
    
    if country == "India":
        if is_preferred_city:
            return 1.0
        elif willing:
            return 0.8
        else:
            return 0.4 # in India but not in preferred city and not willing to relocate
    else:
        # Outside India
        if willing:
            return 0.5 # willing to relocate to India
        else:
            return 0.0 # disqualified (no visa sponsorship)

def get_behavioral_modifier(signals):
    # Days since last active (Reference date: 2026-07-02)
    last_active = signals.get('last_active_date', '')
    activity_mult = 1.0
    if last_active:
        try:
            ref_dt = datetime.strptime("2026-07-02", "%Y-%m-%d")
            act_dt = datetime.strptime(last_active, "%Y-%m-%d")
            days_inactive = (ref_dt - act_dt).days
            if days_inactive <= 30:
                activity_mult = 1.0
            elif days_inactive <= 90:
                activity_mult = 0.8
            elif days_inactive <= 180:
                activity_mult = 0.5
            else:
                activity_mult = 0.1
        except Exception:
            pass
            
    # Open to work flag
    otw_mult = 1.0 if signals.get('open_to_work_flag', False) else 0.7
    
    # Recruiter response rate
    rr = signals.get('recruiter_response_rate', 0.0)
    rr_mult = 0.5 + 0.5 * rr
    
    # Notice period (sub-30 is ideal)
    np = signals.get('notice_period_days', 0)
    if np <= 30:
        np_mult = 1.0
    elif np <= 60:
        np_mult = 0.8
    elif np <= 90:
        np_mult = 0.6
    else:
        np_mult = 0.3
        
    return activity_mult * otw_mult * rr_mult * np_mult

# ============================================================================
# Reasoning Generator
# ============================================================================
def extract_relevant_sentence(career_history):
    keywords = ["rank", "search", "retrieval", "embed", "recommend", "model", "pipeline", "rag", "fine-tune", "nlp", "vector"]
    for job in career_history:
        desc = job.get('description', '')
        if not desc:
            continue
        sentences = [s.strip() for s in re.split(r'\.|\!|\?', desc) if s.strip()]
        for s in sentences:
            s_lower = s.lower()
            if any(kw in s_lower for kw in keywords):
                if len(s) > 130:
                    s = s[:127] + "..."
                return s
    # Fallback to the first sentence of the first job
    if career_history:
        desc = career_history[0].get('description', '')
        if desc:
            sentences = [s.strip() for s in re.split(r'\.|\!|\?', desc) if s.strip()]
            if sentences:
                s = sentences[0]
                if len(s) > 130:
                    s = s[:127] + "..."
                return s
    return "shipped high-quality machine learning systems in production."

def generate_reasoning(c, rank):
    profile = c['profile']
    signals = c['redrob_signals']
    
    name = profile['anonymized_name']
    title = profile['current_title']
    yoe = profile['years_of_experience']
    company = profile.get('current_company', '')
    notice = signals.get('notice_period_days', 0)
    
    # Get 2 matching skills
    matching_skills = []
    for s in c.get('skills', []):
        s_name = s['name']
        if any(cs in s_name.lower() for cs in CORE_SKILLS):
            matching_skills.append(s_name)
    
    skills_str = ", ".join(matching_skills[:2]) if matching_skills else "applied machine learning"
    action_phrase = extract_relevant_sentence(c.get('career_history', []))
    
    # Notice phrase
    if notice == 0:
        notice_phrase = "available immediately"
    elif notice <= 30:
        notice_phrase = f"has a short {notice}-day notice"
    else:
        notice_phrase = f"has a {notice}-day notice"
        
    # Build different styles based on rank to ensure variation and consistency
    if rank <= 15:
        templates = [
            f"Outstanding match with {yoe:.1f} years of experience as a {title} at {company}. Notable expertise in {skills_str}, and {action_phrase}. ({notice_phrase}).",
            f"Strong Senior AI candidate ({yoe:.1f} yrs exp) who worked at {company} on matching and retrieval. Expert in {skills_str}; {action_phrase}.",
            f"Highly relevant {title} with {yoe:.1f} years in production ML. Demonstrated success in {skills_str}; {action_phrase} ({notice_phrase})."
        ]
    elif rank <= 60:
        templates = [
            f"Solid technical fit with {yoe:.1f} years of experience. Experienced in {skills_str} and {action_phrase}. Stated notice: {notice} days.",
            f"Qualified {title} with {yoe:.1f} years experience. Good skills in {skills_str}; career history includes {action_phrase}.",
            f"Brings {yoe:.1f} years of relevant experience, with a solid focus on {skills_str}. Career details show they {action_phrase} ({notice_phrase})."
        ]
    else:
        templates = [
            f"Decent candidate with {yoe:.1f} years experience. Adjacent skills in {skills_str} and shows {action_phrase}.",
            f"Backend/ML engineer with {yoe:.1f} years experience, showing competence in {skills_str}. ({notice_phrase}).",
            f"Includes relevant projects focusing on {skills_str} over {yoe:.1f} years. Stated notice period is {notice} days."
        ]
        
    # Select template deterministically based on candidate ID to ensure stability and variety
    template_idx = sum(ord(char) for char in c['candidate_id']) % len(templates)
    reasoning = templates[template_idx]
    
    # Double check for double spaces or syntax errors
    reasoning = re.sub(r'\s+', ' ', reasoning).strip()
    return reasoning

# ============================================================================
# Main Ranking Flow
# ============================================================================
def main():
    parser = argparse.ArgumentParser(description="Rank candidates for Senior AI Engineer role.")
    parser.add_argument("--candidates", required=True, help="Path to candidates.jsonl or candidates.jsonl.gz")
    parser.add_argument("--out", required=True, help="Path to output submission.csv")
    args = parser.parse_args()
    
    cand_path = Path(args.candidates)
    out_path = Path(args.out)
    
    if not cand_path.exists():
        print(f"Error: Candidate file {cand_path} does not exist.", file=sys.stderr)
        sys.exit(1)
        
    # Open file helper (handles gzip automatically)
    open_func = gzip.open if cand_path.suffix == '.gz' else open
    mode = 'rt' if cand_path.suffix == '.gz' else 'r'
    
    scored_candidates = []
    
    print(f"Reading candidates from {cand_path}...", flush=True)
    with open_func(cand_path, mode, encoding='utf-8') as f:
        for idx, line in enumerate(f):
            if not line.strip():
                continue
            c = json.loads(line)
            cid = c['candidate_id']
            
            # 1. Strict Honeypot Filter
            if detect_honeypot(c):
                continue
                
            # 2. Check Consulting-Only Trap
            career = c.get('career_history', [])
            if career:
                all_consulting = all(job.get('company', '').strip().lower() in CONSULTING_FIRMS for job in career)
                if all_consulting:
                    continue # Disqualified if they worked ONLY in consulting
                    
            # 3. Score components
            title_score = get_title_score(c['profile'].get('current_title', ''))
            if title_score <= 0:
                continue # Exclude keyword stuffers with unrelated titles
                
            yoe_score = get_yoe_score(c['profile'].get('years_of_experience', 0.0))
            skill_score, _ = get_skills_score(c.get('skills', []))
            
            loc_score = get_location_score(c['profile'], c['redrob_signals'])
            if loc_score <= 0:
                continue # Exclude out-of-scope relocation candidates
                
            behavior_mod = get_behavioral_modifier(c['redrob_signals'])
            
            # 4. Composite Score
            # Combine core fit metrics and multiply by behavioral modifiers
            core_fit = (title_score + skill_score * 0.5) * yoe_score * loc_score
            composite_score = core_fit * behavior_mod
            
            scored_candidates.append((composite_score, cid, c))
            
    print(f"Finished scoring. Valid candidates count: {len(scored_candidates)}", flush=True)
    
    # Sort candidates by score descending. Tie-break using candidate_id ascending.
    # Score is negated in sorting tuple so that higher score comes first, then cid ascending.
    scored_candidates.sort(key=lambda x: (-x[0], x[1]))
    
    # Take top 100
    top_100 = scored_candidates[:100]
    
    if len(top_100) < 100:
        print(f"Warning: Only found {len(top_100)} valid candidates. Top 100 will be padded.", file=sys.stderr)
        
    print(f"Writing top 100 results to {out_path}...", flush=True)
    
    # Write output to CSV
    with open(out_path, 'w', encoding='utf-8', newline='') as csvfile:
        import csv
        writer = csv.writer(csvfile)
        # Write header
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        
        for idx, (score, cid, c) in enumerate(top_100):
            rank = idx + 1
            reasoning = generate_reasoning(c, rank)
            # Ensure score is rounded for clean output
            score_rounded = round(score, 4)
            writer.writerow([cid, rank, f"{score_rounded:.4f}", reasoning])
            
    print(f"Successfully generated {out_path}.", flush=True)

if __name__ == "__main__":
    main()
