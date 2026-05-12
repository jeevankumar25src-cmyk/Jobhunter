"""
JobHunter AI - Indeed + Dice scraper addon
Adds technology-specific jobs: .NET, Python, React, Java, DevOps, etc.
Run alongside scraper.py
"""
import requests, time, hashlib, logging, schedule
from datetime import datetime
from database import db, Job, init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

def make_job_id(title, company, location):
    return hashlib.md5(f"{title.lower()}{company.lower()}{location.lower()}".encode()).hexdigest()

def detect_sponsorship(text):
    keywords = ["sponsorship","h1b","h-1b","visa","work authorization","will sponsor","green card","authorize to work"]
    return any(k in text.lower() for k in keywords)

def detect_remote(text):
    t = text.lower()
    if "fully remote" in t or "100% remote" in t: return "Remote"
    if "hybrid" in t: return "Hybrid"
    if "remote" in t: return "Remote"
    return "On-site"

def save_jobs(jobs, category):
    new_count = 0
    with db:
        for job in jobs:
            jid = make_job_id(job.get("title",""), job.get("company",""), job.get("location",""))
            if not Job.get_or_none(Job.job_id == jid):
                desc = job.get("description","")
                loc = job.get("location","")
                Job.create(
                    job_id=jid, title=job.get("title","")[:255],
                    company=job.get("company","")[:255], location=loc[:255],
                    salary=job.get("salary","Not listed")[:128],
                    job_type=job.get("job_type","Full-time")[:64],
                    remote_type=detect_remote(desc+" "+loc),
                    sponsorship=detect_sponsorship(desc),
                    description=desc[:2000], apply_url=job.get("apply_url",""),
                    category=job.get("category","Tech"), company_size=job.get("company_size","Unknown")[:64],
                    posted_at=datetime.utcnow(),
                )
                new_count += 1
    log.info(f"  +{new_count} new [{category}] ({len(jobs)-new_count} dupes skipped)")
    return new_count

# ─── JSEARCH API (free tier via RapidAPI - 500 calls/month free) ───
# Sign up free at: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
# Then paste your key below
JSEARCH_KEY = "YOUR_RAPIDAPI_KEY_HERE"  # <-- replace this

TECH_KEYWORDS = [
    ".net developer", "python developer", "react developer",
    "java developer", "devops engineer", "data engineer",
    "machine learning engineer", "frontend developer", "backend developer",
    "full stack developer", "cloud engineer", "ios developer",
    "android developer", "nodejs developer", "angular developer",
]

def scrape_jsearch(keyword):
    """JSearch API - pulls from LinkedIn, Indeed, Glassdoor. Free 500 calls/month."""
    jobs = []
    if JSEARCH_KEY == "YOUR_RAPIDAPI_KEY_HERE":
        return jobs  # skip if no key set
    try:
        url = "https://jsearch.p.rapidapi.com/search"
        headers = {
            **HEADERS,
            "X-RapidAPI-Key": JSEARCH_KEY,
            "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
        }
        params = {"query": f"{keyword} United States", "page": "1", "num_results": "10", "country": "us"}
        r = requests.get(url, headers=headers, params=params, timeout=15)
        if r.status_code == 200:
            for item in r.json().get("data", []):
                salary = ""
                if item.get("job_min_salary"):
                    salary = f"${item['job_min_salary']:,.0f} - ${item.get('job_max_salary', item['job_min_salary']):,.0f}"
                jobs.append({
                    "title": item.get("job_title",""),
                    "company": item.get("employer_name",""),
                    "location": f"{item.get('job_city','')}, {item.get('job_state','US')}".strip(", "),
                    "description": item.get("job_description","")[:2000],
                    "salary": salary or "Not listed",
                    "apply_url": item.get("job_apply_link",""),
                    "job_type": item.get("job_employment_type","Full-time"),
                    "category": "Tech",
                    "company_size": "Unknown",
                })
        else:
            log.warning(f"JSearch {keyword}: HTTP {r.status_code}")
    except Exception as e:
        log.error(f"JSearch error for {keyword}: {e}")
    return jobs

# ─── ADZUNA API (free 250 calls/day) ───
# Sign up free at: https://developer.adzuna.com/
ADZUNA_APP_ID = "YOUR_APP_ID"    # <-- replace
ADZUNA_APP_KEY = "YOUR_APP_KEY"  # <-- replace

def scrape_adzuna(keyword):
    """Adzuna API - free 250 calls/day, includes salary data."""
    jobs = []
    if "YOUR_APP" in ADZUNA_APP_ID:
        return jobs  # skip if no key
    try:
        url = f"https://api.adzuna.com/v1/api/jobs/us/search/1"
        params = {
            "app_id": ADZUNA_APP_ID,
            "app_key": ADZUNA_APP_KEY,
            "what": keyword,
            "where": "United States",
            "results_per_page": 10,
            "content-type": "application/json",
        }
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            for item in r.json().get("results", []):
                salary_min = item.get("salary_min", 0)
                salary_max = item.get("salary_max", 0)
                salary = f"${salary_min:,.0f} - ${salary_max:,.0f}" if salary_min else "Not listed"
                jobs.append({
                    "title": item.get("title",""),
                    "company": item.get("company",{}).get("display_name",""),
                    "location": item.get("location",{}).get("display_name","United States"),
                    "description": item.get("description","")[:2000],
                    "salary": salary,
                    "apply_url": item.get("redirect_url",""),
                    "job_type": "Full-time",
                    "category": "Tech",
                    "company_size": "Unknown",
                })
        else:
            log.warning(f"Adzuna {keyword}: HTTP {r.status_code}")
    except Exception as e:
        log.error(f"Adzuna error: {e}")
    return jobs

def run_tech_scrapers():
    log.info("="*50)
    log.info("Running tech keyword scrapers...")
    total = 0
    for kw in TECH_KEYWORDS:
        # Try JSearch first
        jobs = scrape_jsearch(kw)
        if jobs:
            total += save_jobs(jobs, "Tech")
        # Try Adzuna
        jobs2 = scrape_adzuna(kw)
        if jobs2:
            total += save_jobs(jobs2, "Tech")
        time.sleep(1)
    log.info(f"Tech scrape done: {total} new jobs")

if __name__ == "__main__":
    init_db()
    run_tech_scrapers()
    schedule.every(30).minutes.do(run_tech_scrapers)
    log.info("Tech scraper running every 30 min. Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(60)
