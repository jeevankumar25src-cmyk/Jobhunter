"""
JobHunter AI - API v5
Fast parallel fetching. Loads in under 10 seconds.
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
    ("gh","gitlab","GitLab","Big Tech"),
    ("gh","zoom","Zoom","Big Tech"),
    ("gh","squarespace","Squarespace","Big Tech"),
    ("gh","procore","Procore","Big Tech"),
    ("gh","toast","Toast","Big Tech"),
    ("gh","snyk","Snyk","Big Tech"),
    ("gh","anthropic","Anthropic","Startups"),
    ("gh","gusto","Gusto","Startups"),
    ("gh","airtable","Airtable","Startups"),
    ("gh","vanta","Vanta","Startups"),
    ("gh","webflow","Webflow","Startups"),
    ("gh","miro","Miro","Startups"),
    ("gh","loom","Loom","Startups"),
    ("gh","postman","Postman","Startups"),
    ("gh","chime","Chime","Finance"),
    ("gh","affirm","Affirm","Finance"),
    ("gh","robinhood","Robinhood","Finance"),
    ("gh","coinbase","Coinbase","Finance"),
    ("gh","oscar","Oscar Health","Healthcare"),
    ("gh","springhealth","Spring Health","Healthcare"),
    ("gh","modernhealth","Modern Health","Healthcare"),
    ("lv","openai","OpenAI","Startups"),
    ("lv","notion","Notion","Startups"),
    ("lv","rippling","Rippling","Startups"),
    ("lv","scale-ai","Scale AI","Startups"),
    ("lv","deel","Deel","Startups"),
    ("lv","drata","Drata","Startups"),
    ("lv","ramp","Ramp","Finance"),
    ("lv","mercury","Mercury","Finance"),
    ("lv","brex","Brex","Finance"),
    ("lv","sentry","Sentry","Big Tech"),
]

NON_USA = ["canada","toronto","vancouver","uk","london","india","bangalore","delhi","germany","berlin",
           "france","paris","australia","sydney","singapore","japan","tokyo","china","brazil","mexico",
           "europe","emea","apac","korea","seoul","netherlands","amsterdam","ireland","dublin","israel"]

def is_usa(loc):
    return not any(c in loc.lower() for c in NON_USA)

def detect_sponsorship(text):
    return any(k in text.lower() for k in ["sponsorship","h1b","h-1b","visa","work authorization","will sponsor","green card"])

def detect_remote(text, loc=""):
    t = (text+" "+loc).lower()
    if "fully remote" in t or "100% remote" in t: return "Remote"
    if "hybrid" in t: return "Hybrid"
    if "remote" in t: return "Remote"
    return "On-site"

def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

def fetch_one(company):
    api, cid, name, cat = company
    jobs = []
    try:
        if api == "gh":
            r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{cid}/jobs",
                params={"content":"true"}, headers=HEADERS, timeout=8)
            if r.status_code == 200:
                for item in r.json().get("jobs",[])[:20]:
                    loc = item.get("location",{}).get("name","United States")
                    if not is_usa(loc): continue
                    desc = BeautifulSoup(item.get("content",""),"html.parser").get_text(separator=" ")
                    desc = " ".join(desc.split())[:500]
                    updated = (item.get("updated_at") or now_iso())[:19]
                    jobs.append({
                        "id": hashlib.md5(f"{item.get('title')}{name}{loc}".encode()).hexdigest()[:12],
                        "title": item.get("title",""), "company": name, "location": loc,
                        "salary": "Not listed", "job_type": "Full-time",
                        "remote_type": detect_remote(desc, loc),
                        "sponsorship": detect_sponsorship(desc),
                        "description": desc,
                        "apply_url": item.get("absolute_url",""),
                        "category": cat, "company_size": "Tech Company",
                        "posted_at": updated,
                    })
        else:
            r = requests.get(f"https://api.lever.co/v0/postings/{cid}",
                params={"mode":"json","limit":20}, headers=HEADERS, timeout=8)
            if r.status_code == 200:
                for item in r.json()[:20]:
                    loc = item.get("categories",{}).get("location","United States")
                    if not is_usa(loc): continue
                    desc = " ".join(item.get("descriptionPlain","").split())[:500]
                    created = item.get("createdAt",0)
                    posted = datetime.fromtimestamp(created/1000,tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") if created else now_iso()
                    jobs.append({
                        "id": hashlib.md5(f"{item.get('text')}{name}{loc}".encode()).hexdigest()[:12],
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

def get_all_jobs():
    now = time.time()
    if _cache["jobs"] and (now - _cache["time"]) < CACHE_TTL:
        return _cache["jobs"]
    all_jobs = []
    # Fetch all companies IN PARALLEL — much faster
    with ThreadPoolExecutor(max_workers=10) as ex:
        results = ex.map(fetch_one, COMPANIES)
        for r in results:
            all_jobs.extend(r)
    all_jobs.sort(key=lambda j: j["posted_at"], reverse=True)
    _cache["jobs"] = all_jobs
    _cache["time"] = now
    print(f"Loaded {len(all_jobs)} jobs from {len(COMPANIES)} companies")
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
        for cat in ["Big Tech","Startups","Healthcare","Finance"]:
            cats[cat] = len([j for j in jobs if j["category"]==cat])
        return jsonify({"total_jobs":len(jobs),"remote_jobs":len([j for j in jobs if "Remote" in j["remote_type"]]),"sponsorship_jobs":len([j for j in jobs if j["sponsorship"]]),"by_category":cats})
    except Exception as e:
        return jsonify({"total_jobs":0,"remote_jobs":0,"sponsorship_jobs":0,"by_category":{},"error":str(e)})

@app.route("/api/health",methods=["GET"])
def health():
    return jsonify({"status":"ok","cached_jobs":len(_cache["jobs"])})

@app.route("/",methods=["GET"])
def home():
    return jsonify({"message":"JobHunter AI","companies":len(COMPANIES),"cached":len(_cache["jobs"])})

if __name__ == "__main__":
    app.run(debug=True,host="0.0.0.0",port=5000)
