"""
JobHunter AI - API v7
Includes enterprise companies for .NET, Java, ServiceNow, SAP etc.
Parallel fetching. No database needed.
"""
import requests, hashlib, time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, jsonify, request
from flask_cors import CORS
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0",
    "Accept": "application/json",
}

_cache = {"jobs": [], "time": 0}
CACHE_TTL = 120

# Mix of tech, enterprise, consulting companies
COMPANIES = [
    # Big Tech
    ("gh","airbnb","Airbnb","Big Tech"),
    ("gh","stripe","Stripe","Big Tech"),
    ("gh","databricks","Databricks","Big Tech"),
    ("gh","figma","Figma","Big Tech"),
    ("gh","reddit","Reddit","Big Tech"),
    ("gh","cloudflare","Cloudflare","Big Tech"),
    ("gh","hubspot","HubSpot","Big Tech"),
    ("gh","datadog","Datadog","Big Tech"),
    ("gh","mongodb","MongoDB","Big Tech"),
    ("gh","gitlab","GitLab","Big Tech"),
    ("gh","zoom","Zoom","Big Tech"),
    ("gh","squarespace","Squarespace","Big Tech"),
    ("gh","procore","Procore","Big Tech"),
    ("gh","toast","Toast","Big Tech"),
    ("gh","twilio","Twilio","Big Tech"),
    ("gh","okta","Okta","Big Tech"),
    ("gh","zendesk","Zendesk","Big Tech"),
    ("gh","dropbox","Dropbox","Big Tech"),
    ("gh","lyft","Lyft","Big Tech"),
    # Startups
    ("gh","anthropic","Anthropic","Startups"),
    ("gh","gusto","Gusto","Startups"),
    ("gh","airtable","Airtable","Startups"),
    ("gh","vanta","Vanta","Startups"),
    ("gh","webflow","Webflow","Startups"),
    ("gh","miro","Miro","Startups"),
    ("gh","loom","Loom","Startups"),
    ("gh","postman","Postman","Startups"),
    ("gh","lattice","Lattice","Startups"),
    # Finance
    ("gh","chime","Chime","Finance"),
    ("gh","affirm","Affirm","Finance"),
    ("gh","robinhood","Robinhood","Finance"),
    ("gh","coinbase","Coinbase","Finance"),
    ("gh","marqeta","Marqeta","Finance"),
    # Healthcare
    ("gh","oscar","Oscar Health","Healthcare"),
    ("gh","springhealth","Spring Health","Healthcare"),
    ("gh","modernhealth","Modern Health","Healthcare"),
    # Lever companies
    ("lv","openai","OpenAI","Startups"),
    ("lv","notion","Notion","Startups"),
    ("lv","rippling","Rippling","Startups"),
    ("lv","scale-ai","Scale AI","Startups"),
    ("lv","deel","Deel","Startups"),
    ("lv","mercury","Mercury","Finance"),
    ("lv","brex","Brex","Finance"),
    ("lv","ramp","Ramp","Finance"),
    ("lv","sentry","Sentry","Big Tech"),
    ("lv","drata","Drata","Startups"),
]

# Enterprise/consulting companies via direct job board APIs
ENTERPRISE_SEARCHES = [
    # These use Indeed-style keyword searches
    {"keyword": ".NET developer", "category": "Enterprise"},
    {"keyword": "Java developer", "category": "Enterprise"},
    {"keyword": "ServiceNow developer", "category": "Enterprise"},
    {"keyword": "SAP consultant", "category": "Enterprise"},
    {"keyword": "Data Analyst", "category": "Enterprise"},
    {"keyword": "Business Analyst", "category": "Enterprise"},
    {"keyword": "Salesforce developer", "category": "Enterprise"},
]

# Adzuna API for enterprise jobs (free tier)
ADZUNA_ID = ""   # Get free at developer.adzuna.com
ADZUNA_KEY = ""  # Get free at developer.adzuna.com

NON_USA = ["canada","toronto","vancouver","uk","london","india","bangalore","delhi",
           "mumbai","hyderabad","germany","berlin","france","paris","australia",
           "sydney","singapore","japan","tokyo","europe","emea","apac","korea","seoul"]

def is_usa(loc):
    return not any(c in loc.lower() for c in NON_USA)

def detect_sponsorship(text):
    return any(k in text.lower() for k in
        ["sponsorship","h1b","h-1b","visa","work authorization","will sponsor",
         "green card","authorize to work","immigration"])

def detect_remote(text, loc=""):
    t = (text+" "+loc).lower()
    if "fully remote" in t or "100% remote" in t: return "Remote"
    if "hybrid" in t: return "Hybrid"
    if "remote" in t: return "Remote"
    return "On-site"

def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

def fetch_gh(cid, name, cat):
    jobs = []
    try:
        r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{cid}/jobs",
            params={"content":"true"}, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            for item in r.json().get("jobs",[])[:20]:
                loc = item.get("location",{}).get("name","United States")
                if not is_usa(loc): continue
                desc = BeautifulSoup(item.get("content",""),"html.parser").get_text(separator=" ")
                desc = " ".join(desc.split())[:600]
                updated = (item.get("updated_at") or now_iso())[:19]
                jobs.append({
                    "id": hashlib.md5(f"{item.get('id')}{cid}".encode()).hexdigest()[:12],
                    "title": item.get("title",""), "company": name, "location": loc,
                    "salary": "Not listed", "job_type": "Full-time",
                    "remote_type": detect_remote(desc, loc),
                    "sponsorship": detect_sponsorship(desc),
                    "description": desc,
                    "apply_url": item.get("absolute_url",""),
                    "category": cat, "company_size": "Tech Company",
                    "posted_at": updated,
                })
    except: pass
    return jobs

def fetch_lv(cid, name, cat):
    jobs = []
    try:
        r = requests.get(f"https://api.lever.co/v0/postings/{cid}",
            params={"mode":"json","limit":20}, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            for item in r.json()[:20]:
                loc = item.get("categories",{}).get("location","United States")
                if not is_usa(loc): continue
                desc = " ".join(item.get("descriptionPlain","").split())[:600]
                created = item.get("createdAt",0)
                posted = datetime.fromtimestamp(created/1000,tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") if created else now_iso()
                jobs.append({
                    "id": hashlib.md5(f"{item.get('id')}{cid}".encode()).hexdigest()[:12],
                    "title": item.get("text",""), "company": name, "location": loc,
                    "salary": "Not listed", "job_type": "Full-time",
                    "remote_type": detect_remote(desc, loc),
                    "sponsorship": detect_sponsorship(desc),
                    "description": desc,
                    "apply_url": item.get("hostedUrl",""),
                    "category": cat, "company_size": "Tech Company",
                    "posted_at": posted,
                })
    except: pass
    return jobs

def fetch_usajobs(keyword, cat):
    """Fetch from USAJobs API - free, no key needed for basic search."""
    jobs = []
    try:
        r = requests.get("https://data.usajobs.gov/api/Search",
            params={"Keyword": keyword, "LocationName": "United States", "ResultsPerPage": 10},
            headers={**HEADERS, "Host":"data.usajobs.gov", "User-Agent":"jobhunter/1.0"},
            timeout=8)
        if r.status_code == 200:
            items = r.json().get("SearchResult",{}).get("SearchResultItems",[])
            for item in items:
                pos = item.get("MatchedObjectDescriptor",{})
                sal = pos.get("PositionRemuneration",[{}])[0]
                loc_data = pos.get("PositionLocation",[{}])[0]
                loc = loc_data.get("LocationName","United States")
                salary = f"${sal.get('MinimumRange','?')} - ${sal.get('MaximumRange','?')}" if sal.get("MinimumRange") else "Not listed"
                jobs.append({
                    "id": hashlib.md5(f"{pos.get('PositionID','')}".encode()).hexdigest()[:12],
                    "title": pos.get("PositionTitle",""),
                    "company": pos.get("OrganizationName","US Government"),
                    "location": loc,
                    "salary": salary,
                    "job_type": "Full-time",
                    "remote_type": detect_remote(pos.get("QualificationSummary","")),
                    "sponsorship": False,
                    "description": pos.get("QualificationSummary","")[:600],
                    "apply_url": pos.get("ApplyURI",[""])[0] if pos.get("ApplyURI") else "",
                    "category": cat,
                    "company_size": "Government",
                    "posted_at": now_iso(),
                })
    except: pass
    return jobs

def get_all_jobs():
    now = time.time()
    if _cache["jobs"] and (now - _cache["time"]) < CACHE_TTL:
        return _cache["jobs"]

    all_jobs = []

    # Fetch startup/tech companies in parallel
    def fetch_company(c):
        api, cid, name, cat = c
        if api == "gh": return fetch_gh(cid, name, cat)
        return fetch_lv(cid, name, cat)

    with ThreadPoolExecutor(max_workers=10) as ex:
        for result in ex.map(fetch_company, COMPANIES):
            all_jobs.extend(result)

    # Fetch enterprise/government jobs for .NET, Java, ServiceNow etc
    enterprise_keywords = [".NET", "Java Developer", "ServiceNow", "SAP", "Data Analyst",
                          "Business Analyst", "Salesforce", "Oracle", "PowerBI", "Tableau"]
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(fetch_usajobs, kw, "Enterprise") for kw in enterprise_keywords]
        for f in futures:
            try: all_jobs.extend(f.result())
            except: pass

    all_jobs.sort(key=lambda j: j.get("posted_at",""), reverse=True)
    _cache["jobs"] = all_jobs
    _cache["time"] = now
    print(f"Cached {len(all_jobs)} jobs")
    return all_jobs

@app.route("/api/jobs", methods=["GET"])
def search_jobs():
    keyword  = request.args.get("keyword","").lower()
    location = request.args.get("location","").lower()
    remote   = request.args.get("remote","").lower()
    category = request.args.get("category","")
    sponsor  = request.args.get("sponsorship","")
    hours    = request.args.get("hours","")
    page     = int(request.args.get("page",1))
    per_page = int(request.args.get("per_page",20))
    jobs = get_all_jobs()
    if keyword:
        jobs = [j for j in jobs if keyword in j["title"].lower() or keyword in j["company"].lower() or keyword in j["description"].lower()]
    if location:
        jobs = [j for j in jobs if location in j["location"].lower()]
    if remote:
        jobs = [j for j in jobs if remote in j["remote_type"].lower()]
    if category:
        jobs = [j for j in jobs if j["category"]==category]
    if sponsor=="true":
        jobs = [j for j in jobs if j["sponsorship"]]
    if hours:
        try:
            cutoff = time.time()-(int(hours)*3600)
            jobs = [j for j in jobs if datetime.fromisoformat(j["posted_at"]).replace(tzinfo=timezone.utc).timestamp()>=cutoff]
        except: pass
    total = len(jobs)
    start = (page-1)*per_page
    return jsonify({"total":total,"page":page,"per_page":per_page,"jobs":jobs[start:start+per_page]})

@app.route("/api/stats", methods=["GET"])
def stats():
    try:
        jobs = get_all_jobs()
        cats = {}
        for cat in ["Big Tech","Startups","Healthcare","Finance","Enterprise"]:
            cats[cat] = len([j for j in jobs if j["category"]==cat])
        return jsonify({
            "total_jobs":len(jobs),
            "remote_jobs":len([j for j in jobs if "Remote" in j["remote_type"]]),
            "sponsorship_jobs":len([j for j in jobs if j["sponsorship"]]),
            "by_category":cats,
        })
    except Exception as e:
        return jsonify({"total_jobs":0,"remote_jobs":0,"sponsorship_jobs":0,"by_category":{},"error":str(e)})

@app.route("/api/health",methods=["GET"])
def health():
    return jsonify({"status":"ok","cached":len(_cache["jobs"])})

@app.route("/",methods=["GET"])
def home():
    return jsonify({"message":"JobHunter AI","cached":len(_cache["jobs"])})

if __name__ == "__main__":
    app.run(debug=True,host="0.0.0.0",port=5000)
