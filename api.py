"""
JobHunter AI - Standalone API
Fetches jobs directly from Greenhouse + Lever APIs.
No database needed - works immediately on any server.
"""
import requests
import hashlib
import time
from flask import Flask, jsonify, request
from flask_cors import CORS
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

# Cache jobs in memory for 2 minutes
_cache = {"jobs": [], "time": 0}
CACHE_TTL = 120  # 2 minutes

COMPANIES = [
    # (api_type, company_id, company_name, category, size)
    ("gh", "airbnb",     "Airbnb",      "Big Tech",   "Big Tech (5k+)"),
    ("gh", "lyft",       "Lyft",        "Big Tech",   "Big Tech (5k+)"),
    ("gh", "stripe",     "Stripe",      "Big Tech",   "Big Tech (8k+)"),
    ("gh", "databricks", "Databricks",  "Big Tech",   "Tech (5k+)"),
    ("gh", "figma",      "Figma",       "Big Tech",   "Tech (1k+)"),
    ("gh", "reddit",     "Reddit",      "Big Tech",   "Big Tech (2k+)"),
    ("gh", "twilio",     "Twilio",      "Big Tech",   "Tech (5k+)"),
    ("gh", "dropbox",    "Dropbox",     "Big Tech",   "Big Tech (3k+)"),
    ("gh", "anthropic",  "Anthropic",   "Startups",   "AI Startup"),
    ("gh", "gusto",      "Gusto",       "Startups",   "HR Startup"),
    ("gh", "airtable",   "Airtable",    "Startups",   "Startup"),
    ("gh", "chime",      "Chime",       "Finance",    "Fintech (1k+)"),
    ("gh", "affirm",     "Affirm",      "Finance",    "Fintech (1k+)"),
    ("gh", "marqeta",    "Marqeta",     "Finance",    "Fintech (500+)"),
    ("gh", "robinhood",  "Robinhood",   "Finance",    "Fintech (1k+)"),
    ("gh", "oscar",      "Oscar Health","Healthcare", "Health Startup"),
    ("lv", "openai",     "OpenAI",      "Startups",   "AI Startup"),
    ("lv", "notion",     "Notion",      "Startups",   "Startup"),
    ("lv", "brex",       "Brex",        "Finance",    "Fintech"),
    ("lv", "rippling",   "Rippling",    "Startups",   "HR Startup"),
]

def detect_sponsorship(text):
    keywords = ["sponsorship","h1b","h-1b","visa","work authorization","will sponsor","green card"]
    return any(k in text.lower() for k in keywords)

def detect_remote(text, location=""):
    t = (text + " " + location).lower()
    if "fully remote" in t or "100% remote" in t: return "Remote"
    if "hybrid" in t: return "Hybrid"
    if "remote" in t: return "Remote"
    return "On-site"

def fetch_greenhouse(company_id, company_name, category, size):
    jobs = []
    try:
        r = requests.get(
            f"https://boards-api.greenhouse.io/v1/boards/{company_id}/jobs",
            params={"content": "true"}, headers=HEADERS, timeout=10
        )
        if r.status_code == 200:
            for item in r.json().get("jobs", [])[:20]:
                loc = item.get("location", {}).get("name", "United States")
                desc = BeautifulSoup(item.get("content", ""), "html.parser").get_text()[:500]
                jobs.append({
                    "id": hashlib.md5(f"{item.get('title')}{company_name}{loc}".encode()).hexdigest()[:12],
                    "title": item.get("title", ""),
                    "company": company_name,
                    "location": loc,
                    "salary": "Not listed",
                    "job_type": "Full-time",
                    "remote_type": detect_remote(desc, loc),
                    "sponsorship": detect_sponsorship(desc),
                    "description": desc,
                    "apply_url": item.get("absolute_url", ""),
                    "category": category,
                    "company_size": size,
                    "posted_at": "2026-05-12T00:00:00",
                })
    except: pass
    return jobs

def fetch_lever(company_id, company_name, category, size):
    jobs = []
    try:
        r = requests.get(
            f"https://api.lever.co/v0/postings/{company_id}",
            params={"mode": "json", "limit": 20}, headers=HEADERS, timeout=10
        )
        if r.status_code == 200:
            for item in r.json()[:20]:
                cats = item.get("categories", {})
                loc = cats.get("location", "United States")
                desc = item.get("descriptionPlain", "")[:500]
                jobs.append({
                    "id": hashlib.md5(f"{item.get('text')}{company_name}{loc}".encode()).hexdigest()[:12],
                    "title": item.get("text", ""),
                    "company": company_name,
                    "location": loc,
                    "salary": "Not listed",
                    "job_type": "Full-time",
                    "remote_type": detect_remote(desc, loc),
                    "sponsorship": detect_sponsorship(desc),
                    "description": desc,
                    "apply_url": item.get("hostedUrl", ""),
                    "category": category,
                    "company_size": size,
                    "posted_at": "2026-05-12T00:00:00",
                })
    except: pass
    return jobs

def get_all_jobs():
    now = time.time()
    if _cache["jobs"] and (now - _cache["time"]) < CACHE_TTL:
        return _cache["jobs"]
    
    all_jobs = []
    for api_type, cid, name, cat, size in COMPANIES:
        if api_type == "gh":
            all_jobs.extend(fetch_greenhouse(cid, name, cat, size))
        else:
            all_jobs.extend(fetch_lever(cid, name, cat, size))
        time.sleep(0.3)
    
    _cache["jobs"] = all_jobs
    _cache["time"] = now
    return all_jobs

@app.route("/api/jobs", methods=["GET"])
def search_jobs():
    keyword     = request.args.get("keyword", "").lower()
    location    = request.args.get("location", "").lower()
    remote      = request.args.get("remote", "").lower()
    category    = request.args.get("category", "")
    sponsor     = request.args.get("sponsorship", "")
    page        = int(request.args.get("page", 1))
    per_page    = int(request.args.get("per_page", 20))

    jobs = get_all_jobs()

    if keyword:
        jobs = [j for j in jobs if keyword in j["title"].lower() or keyword in j["company"].lower() or keyword in j["description"].lower()]
    if location:
        jobs = [j for j in jobs if location in j["location"].lower()]
    if remote:
        jobs = [j for j in jobs if remote.lower() in j["remote_type"].lower()]
    if category:
        jobs = [j for j in jobs if j["category"] == category]
    if sponsor == "true":
        jobs = [j for j in jobs if j["sponsorship"]]

    total = len(jobs)
    start = (page - 1) * per_page
    return jsonify({"total": total, "page": page, "per_page": per_page, "jobs": jobs[start:start+per_page]})

@app.route("/api/stats", methods=["GET"])
def stats():
    try:
        jobs = get_all_jobs()
        cats = {}
        for cat in ["Big Tech", "Startups", "Healthcare", "Finance"]:
            cats[cat] = len([j for j in jobs if j["category"] == cat])
        return jsonify({
            "total_jobs": len(jobs),
            "remote_jobs": len([j for j in jobs if "Remote" in j["remote_type"]]),
            "sponsorship_jobs": len([j for j in jobs if j["sponsorship"]]),
            "by_category": cats,
        })
    except Exception as e:
        return jsonify({"total_jobs": 0, "remote_jobs": 0, "sponsorship_jobs": 0, "by_category": {}, "error": str(e)})

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "JobHunter AI API is running!", "jobs_cached": len(_cache["jobs"])})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
