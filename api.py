"""
JobHunter AI - API v8
Uses JSearch API (LinkedIn+Indeed+Glassdoor) for broad job coverage.
Falls back to Greenhouse/Lever for specific companies.
"""
import requests, hashlib, time, os
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, jsonify, request
from flask_cors import CORS
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0",
    "Accept": "application/json",
}

# JSearch API key - get free at rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
JSEARCH_KEY = os.getenv("JSEARCH_KEY", "")

_cache = {"jobs": [], "time": 0}
CACHE_TTL = 300  # 5 minutes

# Company job boards (fast, reliable)
COMPANIES = [
    ("gh","airbnb","Airbnb","Big Tech"),
    ("gh","stripe","Stripe","Big Tech"),
    ("gh","databricks","Databricks","Big Tech"),
    ("gh","figma","Figma","Big Tech"),
    ("gh","reddit","Reddit","Big Tech"),
    ("gh","cloudflare","Cloudflare","Big Tech"),
    ("gh","hubspot","HubSpot","Big Tech"),
    ("gh","datadog","Datadog","Big Tech"),
    ("gh","mongodb","MongoDB","Big Tech"),
    ("gh","zoom","Zoom","Big Tech"),
    ("gh","squarespace","Squarespace","Big Tech"),
    ("gh","toast","Toast","Big Tech"),
    ("gh","twilio","Twilio","Big Tech"),
    ("gh","okta","Okta","Big Tech"),
    ("gh","anthropic","Anthropic","Startups"),
    ("gh","gusto","Gusto","Startups"),
    ("gh","airtable","Airtable","Startups"),
    ("gh","webflow","Webflow","Startups"),
    ("gh","miro","Miro","Startups"),
    ("gh","chime","Chime","Finance"),
    ("gh","affirm","Affirm","Finance"),
    ("gh","robinhood","Robinhood","Finance"),
    ("gh","oscar","Oscar Health","Healthcare"),
    ("gh","springhealth","Spring Health","Healthcare"),
    ("lv","openai","OpenAI","Startups"),
    ("lv","notion","Notion","Startups"),
    ("lv","rippling","Rippling","Startups"),
    ("lv","scale-ai","Scale AI","Startups"),
    ("lv","mercury","Mercury","Finance"),
    ("lv","ramp","Ramp","Finance"),
    ("lv","brex","Brex","Finance"),
    ("lv","sentry","Sentry","Big Tech"),
    ("lv","drata","Drata","Startups"),
]

# Keywords to search via JSearch (LinkedIn/Indeed/Glassdoor)
JSEARCH_KEYWORDS = [
    ("Data Analyst", "Enterprise"),
    (".NET Developer", "Enterprise"),
    ("Java Developer", "Enterprise"),
    ("ServiceNow Developer", "Enterprise"),
    ("SAP Consultant", "Enterprise"),
    ("Salesforce Developer", "Enterprise"),
    ("Business Analyst", "Enterprise"),
    ("Python Developer", "Big Tech"),
    ("React Developer", "Big Tech"),
    ("DevOps Engineer", "Big Tech"),
    ("Machine Learning Engineer", "Big Tech"),
    ("Cloud Engineer", "Big Tech"),
    ("Full Stack Developer", "Big Tech"),
    ("Data Engineer", "Big Tech"),
    ("SQL Developer", "Enterprise"),
    ("Power BI Developer", "Enterprise"),
    ("Oracle Developer", "Enterprise"),
    ("Software Engineer", "Big Tech"),
    ("Product Manager", "Big Tech"),
    ("UX Designer", "Big Tech"),
]

NON_USA = ["canada","toronto","vancouver","uk","london","india","bangalore","delhi",
           "mumbai","germany","berlin","france","paris","australia","sydney",
           "singapore","japan","tokyo","europe","emea","apac","korea","seoul"]

def is_usa(loc):
    if not loc: return True
    return not any(c in loc.lower() for c in NON_USA)

def detect_sponsorship(text):
    return any(k in text.lower() for k in
        ["sponsorship","h1b","h-1b","visa","work authorization","will sponsor",
         "green card","authorize to work","immigration","ead","opt"])

def detect_remote(text, loc=""):
    t = (text+" "+loc).lower()
    if "fully remote" in t or "100% remote" in t or "work from home" in t: return "Remote"
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
            for item in r.json().get("jobs",[])[:15]:
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
                    "description": desc, "apply_url": item.get("absolute_url",""),
                    "category": cat, "company_size": "Tech Company",
                    "posted_at": updated, "source": "greenhouse",
                })
    except: pass
    return jobs

def fetch_lv(cid, name, cat):
    jobs = []
    try:
        r = requests.get(f"https://api.lever.co/v0/postings/{cid}",
            params={"mode":"json","limit":15}, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            for item in r.json()[:15]:
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
                    "description": desc, "apply_url": item.get("hostedUrl",""),
                    "category": cat, "company_size": "Tech Company",
                    "posted_at": posted, "source": "lever",
                })
    except: pass
    return jobs

def fetch_jsearch(keyword, category):
    """Fetch from JSearch API - pulls from LinkedIn, Indeed, Glassdoor."""
    jobs = []
    if not JSEARCH_KEY:
        return jobs
    try:
        r = requests.get(
            "https://jsearch.p.rapidapi.com/search",
            headers={
                "X-RapidAPI-Key": JSEARCH_KEY,
                "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
            },
            params={
                "query": f"{keyword} United States",
                "page": "1",
                "num_results": "10",
                "date_posted": "week",
                "country": "us",
            },
            timeout=10
        )
        if r.status_code == 200:
            for item in r.json().get("data", []):
                loc = f"{item.get('job_city','')}, {item.get('job_state','US')}".strip(", ")
                if not is_usa(loc): continue
                desc = item.get("job_description","")[:600]
                salary = ""
                if item.get("job_min_salary"):
                    salary = f"${item['job_min_salary']:,.0f} - ${item.get('job_max_salary', item['job_min_salary']):,.0f}/yr"
                # Parse posted date
                posted_ts = item.get("job_posted_at_timestamp")
                if posted_ts:
                    posted = datetime.fromtimestamp(posted_ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
                else:
                    posted = now_iso()
                jobs.append({
                    "id": hashlib.md5(f"{item.get('job_id','')}{keyword}".encode()).hexdigest()[:12],
                    "title": item.get("job_title",""),
                    "company": item.get("employer_name",""),
                    "location": loc or "United States",
                    "salary": salary or "Not listed",
                    "job_type": item.get("job_employment_type","Full-time"),
                    "remote_type": "Remote" if item.get("job_is_remote") else detect_remote(desc, loc),
                    "sponsorship": detect_sponsorship(desc),
                    "description": " ".join(desc.split()),
                    "apply_url": item.get("job_apply_link",""),
                    "category": category,
                    "company_size": "Unknown",
                    "posted_at": posted,
                    "source": item.get("job_publisher","LinkedIn"),
                })
    except Exception as e:
        print(f"JSearch error for {keyword}: {e}")
    return jobs

def get_all_jobs():
    now = time.time()
    if _cache["jobs"] and (now - _cache["time"]) < CACHE_TTL:
        return _cache["jobs"]

    all_jobs = []

    # Fetch company boards in parallel
    with ThreadPoolExecutor(max_workers=10) as ex:
        for result in ex.map(lambda c: fetch_gh(c[1],c[2],c[3]) if c[0]=="gh" else fetch_lv(c[1],c[2],c[3]), COMPANIES):
            all_jobs.extend(result)

    # Fetch keyword searches in parallel (only if JSearch key available)
    if JSEARCH_KEY:
        with ThreadPoolExecutor(max_workers=5) as ex:
            for result in ex.map(lambda k: fetch_jsearch(k[0],k[1]), JSEARCH_KEYWORDS):
                all_jobs.extend(result)

    # Remove duplicates
    seen = set()
    unique = []
    for j in all_jobs:
        key = f"{j['title'].lower()}{j['company'].lower()}"
        if key not in seen:
            seen.add(key)
            unique.append(j)

    unique.sort(key=lambda j: j.get("posted_at",""), reverse=True)
    _cache["jobs"] = unique
    _cache["time"] = now
    print(f"Cached {len(unique)} unique jobs")
    return unique

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
        jobs = [j for j in jobs if keyword in j["title"].lower()
                or keyword in j["company"].lower()
                or keyword in j["description"].lower()]
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
            jobs = [j for j in jobs
                    if datetime.fromisoformat(j["posted_at"])
                    .replace(tzinfo=timezone.utc).timestamp() >= cutoff]
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
            "total_jobs": len(jobs),
            "remote_jobs": len([j for j in jobs if "Remote" in j["remote_type"]]),
            "sponsorship_jobs": len([j for j in jobs if j["sponsorship"]]),
            "by_category": cats,
        })
    except Exception as e:
        return jsonify({"total_jobs":0,"remote_jobs":0,"sponsorship_jobs":0,"by_category":{},"error":str(e)})

@app.route("/api/health",methods=["GET"])
def health():
    return jsonify({"status":"ok","cached":len(_cache["jobs"]),"jsearch":bool(JSEARCH_KEY)})

@app.route("/",methods=["GET"])
def home():
    return jsonify({"message":"JobHunter AI","cached":len(_cache["jobs"])})

if __name__ == "__main__":
    app.run(debug=True,host="0.0.0.0",port=5000)
