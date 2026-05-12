"""
JobHunter AI - Real-Time Job Scraper v2 (Fixed)
Uses Greenhouse + Lever APIs — both are free, public, no key needed
"""

import requests
import time
import hashlib
import logging
import schedule
from datetime import datetime
from bs4 import BeautifulSoup
from database import db, Job, init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

def make_job_id(title, company, location):
    raw = f"{title.lower().strip()}{company.lower().strip()}{location.lower().strip()}"
    return hashlib.md5(raw.encode()).hexdigest()

def detect_sponsorship(text):
    keywords = ["sponsorship","sponsor","h1b","h-1b","visa","work authorization",
                "authorize to work","green card","will not sponsor","must be authorized","security clearance"]
    t = text.lower()
    return any(k in t for k in keywords)

def detect_remote(text):
    t = text.lower()
    if "fully remote" in t or "100% remote" in t or "work from anywhere" in t:
        return "Remote"
    elif "hybrid" in t:
        return "Hybrid"
    elif "remote" in t:
        return "Remote"
    return "On-site"

def save_jobs(jobs, category):
    new_count = 0
    with db:
        for job in jobs:
            jid = make_job_id(job.get("title",""), job.get("company",""), job.get("location",""))
            if not Job.get_or_none(Job.job_id == jid):
                desc = job.get("description","")
                loc  = job.get("location","")
                Job.create(
                    job_id=jid, title=job.get("title","Unknown")[:255],
                    company=job.get("company","Unknown")[:255], location=loc[:255],
                    salary=job.get("salary","Not listed")[:128],
                    job_type=job.get("job_type","Full-time")[:64],
                    remote_type=detect_remote(desc+" "+loc),
                    sponsorship=detect_sponsorship(desc),
                    description=desc[:2000], apply_url=job.get("apply_url",""),
                    category=category, company_size=job.get("company_size","Unknown")[:64],
                    posted_at=datetime.utcnow(),
                )
                new_count += 1
    log.info(f"  +{new_count} new jobs [{category}]  ({len(jobs)-new_count} duplicates skipped)")
    return new_count

def scrape_greenhouse(company_id, company_name, size="Tech"):
    jobs = []
    try:
        url = f"https://boards-api.greenhouse.io/v1/boards/{company_id}/jobs"
        r = requests.get(url, params={"content":"true"}, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            for item in r.json().get("jobs", [])[:30]:
                loc = item.get("location", {}).get("name", "United States")
                jobs.append({
                    "title": item.get("title",""), "company": company_name, "location": loc,
                    "description": BeautifulSoup(item.get("content",""), "html.parser").get_text()[:1000],
                    "apply_url": item.get("absolute_url",""), "company_size": size, "job_type": "Full-time",
                })
        else:
            log.warning(f"  {company_name} (Greenhouse): HTTP {r.status_code}")
    except Exception as e:
        log.error(f"  {company_name} Greenhouse error: {e}")
    return jobs

def scrape_lever(company_id, company_name, size="Startup"):
    jobs = []
    try:
        url = f"https://api.lever.co/v0/postings/{company_id}"
        r = requests.get(url, params={"mode":"json","limit":30}, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            for item in r.json():
                cats = item.get("categories", {})
                jobs.append({
                    "title": item.get("text",""), "company": company_name,
                    "location": cats.get("location","United States"),
                    "description": item.get("descriptionPlain","")[:1000],
                    "apply_url": item.get("hostedUrl",""), "company_size": size, "job_type": "Full-time",
                })
        else:
            log.warning(f"  {company_name} (Lever): HTTP {r.status_code}")
    except Exception as e:
        log.error(f"  {company_name} Lever error: {e}")
    return jobs

def scrape_amazon():
    log.info("Scraping Amazon...")
    jobs = []
    try:
        r = requests.get("https://www.amazon.jobs/en/search.json",
            params={"country":"US","result_limit":20,"sort":"recent"},
            headers=HEADERS, timeout=15)
        if r.status_code == 200:
            for item in r.json().get("jobs",[]):
                jobs.append({
                    "title": item.get("title",""), "company": "Amazon",
                    "location": item.get("location","United States"),
                    "description": item.get("description","")[:1000],
                    "salary": item.get("base_pay_range","Not listed"),
                    "apply_url": "https://www.amazon.jobs" + item.get("job_path",""),
                    "company_size": "Big Tech (100k+)", "job_type": "Full-time",
                })
        else:
            log.warning(f"  Amazon: HTTP {r.status_code}")
    except Exception as e:
        log.error(f"  Amazon error: {e}")
    return jobs

def scrape_big_tech():
    log.info("Scraping Big Tech (Greenhouse)...")
    jobs = []
    companies = [
        ("airbnb","Airbnb","Big Tech (5k+)"), ("lyft","Lyft","Big Tech (5k+)"),
        ("dropbox","Dropbox","Big Tech (3k+)"), ("stripe","Stripe","Big Tech (8k+)"),
        ("databricks","Databricks","Tech (5k+)"), ("figma","Figma","Tech (1k+)"),
        ("coinbase","Coinbase","Fintech (5k+)"), ("reddit","Reddit","Big Tech (2k+)"),
        ("squareup","Square/Block","Big Tech (8k+)"), ("twilio","Twilio","Tech (5k+)"),
    ]
    for cid, name, size in companies:
        result = scrape_greenhouse(cid, name, size)
        if result:
            log.info(f"    {name}: {len(result)} jobs")
        jobs.extend(result)
        time.sleep(0.8)
    return jobs

def scrape_yc_startups():
    log.info("Scraping YC Startups...")
    jobs = []
    lever_cos = [
        ("openai","OpenAI","AI Startup (1k+)"), ("notion","Notion","Startup (500+)"),
        ("brex","Brex","Fintech Startup"), ("rippling","Rippling","HR Startup"),
        ("scale-ai","Scale AI","AI Startup"), ("verkada","Verkada","Security Tech"),
    ]
    gh_cos = [
        ("anthropic","Anthropic","AI Startup"), ("gusto","Gusto","HR Startup (2k+)"),
        ("airtable","Airtable","Startup (500+)"), ("benchling","Benchling","Biotech Startup"),
    ]
    for cid, name, size in lever_cos:
        result = scrape_lever(cid, name, size)
        if result: log.info(f"    {name}: {len(result)} jobs")
        jobs.extend(result)
        time.sleep(0.8)
    for cid, name, size in gh_cos:
        result = scrape_greenhouse(cid, name, size)
        if result: log.info(f"    {name}: {len(result)} jobs")
        jobs.extend(result)
        time.sleep(0.8)
    return jobs

def scrape_healthcare():
    log.info("Scraping Healthcare...")
    jobs = []
    companies = [
        ("oscar","Oscar Health","Health Startup"), ("tempus","Tempus","Health Tech"),
        ("flatiron","Flatiron Health","Health Tech"), ("hims","Hims & Hers","Health Startup"),
        ("cityblock","Cityblock Health","Health Startup"), ("nuvation-bio","Nuvation Bio","Biotech"),
    ]
    for cid, name, size in companies:
        result = scrape_greenhouse(cid, name, size)
        if result: log.info(f"    {name}: {len(result)} jobs")
        jobs.extend(result)
        time.sleep(0.8)
    return jobs

def scrape_finance():
    log.info("Scraping Finance & Fintech...")
    jobs = []
    gh_cos = [
        ("plaid","Plaid","Fintech (500+)"), ("chime","Chime","Fintech (1k+)"),
        ("affirm","Affirm","Fintech (1k+)"), ("marqeta","Marqeta","Fintech (500+)"),
        ("wise","Wise","Fintech (5k+)"), ("robinhood","Robinhood","Fintech (1k+)"),
    ]
    lev_cos = [
        ("carta","Carta","Fintech (1k+)"),
    ]
    for cid, name, size in gh_cos:
        result = scrape_greenhouse(cid, name, size)
        if result: log.info(f"    {name}: {len(result)} jobs")
        jobs.extend(result)
        time.sleep(0.8)
    for cid, name, size in lev_cos:
        result = scrape_lever(cid, name, size)
        if result: log.info(f"    {name}: {len(result)} jobs")
        jobs.extend(result)
        time.sleep(0.8)
    return jobs

def run_all_scrapers():
    log.info("=" * 55)
    log.info("Starting scrape cycle...")
    start = time.time()
    total = 0
    for fn, cat in [
        (scrape_big_tech,"Big Tech"), (scrape_amazon,"Big Tech"),
        (scrape_yc_startups,"Startups"), (scrape_healthcare,"Healthcare"),
        (scrape_finance,"Finance"),
    ]:
        try:
            total += save_jobs(fn(), cat)
        except Exception as e:
            log.error(f"{fn.__name__} crashed: {e}")
        time.sleep(2)
    log.info(f"Done: {total} new jobs in {round(time.time()-start,1)}s")
    log.info("=" * 55)

if __name__ == "__main__":
    log.info("JobHunter AI Scraper v2 starting...")
    init_db()
    run_all_scrapers()
    schedule.every(2).minutes.do(run_all_scrapers)
    log.info("Scraping every 2 min. Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(30)
