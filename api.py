"""
JobHunter AI - API v10
USA only. Big companies. JSearch for Data Analyst, Java, .NET etc.
Background loading. No timeout.
"""
import requests, hashlib, time, os, threading
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

JSEARCH_KEY = os.getenv("JSEARCH_KEY", "8acef9867emshf21b10c7e42b5acp1cc495jsn8a75d9eeeda7")

_cache = {"jobs": [], "time": 0, "loading": False}
CACHE_TTL = 300

# USA states list for verification
USA_STATES = [
    "alabama","alaska","arizona","arkansas","california","colorado","connecticut",
    "delaware","florida","georgia","hawaii","idaho","illinois","indiana","iowa",
    "kansas","kentucky","louisiana","maine","maryland","massachusetts","michigan",
    "minnesota","mississippi","missouri","montana","nebraska","nevada","new hampshire",
    "new jersey","new mexico","new york","north carolina","north dakota","ohio",
    "oklahoma","oregon","pennsylvania","rhode island","south carolina","south dakota",
    "tennessee","texas","utah","vermont","virginia","washington","west virginia",
    "wisconsin","wyoming","district of columbia","remote","united states","usa",
    # State codes
    "al","ak","az","ar","ca","co","ct","de","fl","ga","hi","id","il","in","ia",
    "ks","ky","la","me","md","ma","mi","mn","ms","mo","mt","ne","nv","nh","nj",
    "nm","ny","nc","nd","oh","ok","or","pa","ri","sc","sd","tn","tx","ut","vt",
    "va","wa","wv","wi","wy","dc",
    # Major US cities
    "new york","los angeles","chicago","houston","phoenix","philadelphia","san antonio",
    "san diego","dallas","san jose","austin","jacksonville","fort worth","columbus",
    "charlotte","indianapolis","san francisco","seattle","denver","washington",
    "nashville","oklahoma","boston","portland","las vegas","memphis","louisville",
    "baltimore","milwaukee","albuquerque","tucson","fresno","sacramento","mesa",
    "kansas city","atlanta","omaha","colorado springs","raleigh","miami","minneapolis",
    "cleveland","wichita","tampa","new orleans","pittsburgh","cincinnati","anaheim",
    "lexington","stockton","st louis","saint louis","riverside","irvine","orlando",
]

NON_USA = [
    "canada","ontario","british columbia","alberta","toronto","vancouver","montreal","calgary","ottawa",
    "united kingdom","uk","england","london","manchester","birmingham","edinburgh",
    "india","bangalore","bengaluru","delhi","new delhi","mumbai","hyderabad","pune","chennai","kolkata","noida","gurgaon","gurugram",
    "germany","berlin","munich","hamburg","frankfurt",
    "france","paris","lyon","marseille",
    "australia","sydney","melbourne","brisbane","perth","canberra",
    "singapore","japan","tokyo","osaka","china","beijing","shanghai","shenzhen",
    "brazil","sao paulo","rio de janeiro","mexico","mexico city","guadalajara",
    "ireland","dublin","netherlands","amsterdam","sweden","stockholm",
    "spain","madrid","barcelona","israel","tel aviv","poland","warsaw",
    "switzerland","zurich","geneva","denmark","copenhagen","finland","helsinki",
    "south korea","korea","seoul","busan",
    "philippines","manila","pakistan","karachi","lahore","bangladesh","dhaka",
    "sri lanka","colombo","nigeria","lagos","kenya","nairobi","south africa","johannesburg",
    "egypt","cairo","uae","dubai","abu dhabi","saudi arabia","riyadh",
    "europe","emea","apac","latam","worldwide","global","anywhere",
    "iran","iraq","syria","russia","ukraine","belarus","vietnam","indonesia","malaysia","thailand",
]

def is_usa(loc):
    if not loc or loc.strip() == "": return True
    loc_lower = loc.lower().strip()
    # If it's just "Remote" or "United States" - accept
    if loc_lower in ["remote","united states","usa","us","anywhere"]: return True
    # Check if it contains a non-USA location
    for bad in NON_USA:
        if bad in loc_lower: return False
    # Check if it contains a USA indicator
    for good in USA_STATES:
        if good in loc_lower: return True
    # Default: if no clear indicator, include it (better to include than exclude)
    return True

def detect_sponsorship(text):
    text_lower = text.lower()
    # Strong positive signals
    positive = ["will sponsor","sponsorship available","h1b sponsor","visa sponsor",
                "h-1b sponsor","immigration sponsor","work visa sponsor",
                "sponsor work authorization","h1b transfer","h1b accepted"]
    if any(k in text_lower for k in positive): return True
    # General keywords that suggest sponsorship is mentioned
    general = ["h1b","h-1b","visa sponsorship","work authorization","ead","opt","stem opt",
               "green card sponsor","authorized to work","sponsorship considered"]
    return any(k in text_lower for k in general)

def detect_remote(text, loc=""):
    t = (text+" "+loc).lower()
    if any(x in t for x in ["fully remote","100% remote","work from home","wfh","remote first","remote-first"]): return "Remote"
    if "hybrid" in t: return "Hybrid"
    if "remote" in t: return "Remote"
    return "On-site"

def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

# ── GREENHOUSE companies (includes major US companies) ──
GH_COMPANIES = [
    # Big Tech
    ("airbnb","Airbnb","Big Tech"),
    ("stripe","Stripe","Big Tech"),
    ("databricks","Databricks","Big Tech"),
    ("figma","Figma","Big Tech"),
    ("reddit","Reddit","Big Tech"),
    ("cloudflare","Cloudflare","Big Tech"),
    ("hubspot","HubSpot","Big Tech"),
    ("datadog","Datadog","Big Tech"),
    ("mongodb","MongoDB","Big Tech"),
    ("zoom","Zoom","Big Tech"),
    ("toast","Toast","Big Tech"),
    ("twilio","Twilio","Big Tech"),
    ("okta","Okta","Big Tech"),
    ("squarespace","Squarespace","Big Tech"),
    ("procore","Procore","Big Tech"),
    ("pagerduty","PagerDuty","Big Tech"),
    ("zendesk","Zendesk","Big Tech"),
    ("dropbox","Dropbox","Big Tech"),
    ("lyft","Lyft","Big Tech"),
    # Startups/Growth
    ("anthropic","Anthropic","Startups"),
    ("gusto","Gusto","Startups"),
    ("airtable","Airtable","Startups"),
    ("webflow","Webflow","Startups"),
    ("miro","Miro","Startups"),
    ("loom","Loom","Startups"),
    ("lattice","Lattice","Startups"),
    ("snyk","Snyk","Big Tech"),
    ("vanta","Vanta","Startups"),
    # Finance
    ("chime","Chime","Finance"),
    ("affirm","Affirm","Finance"),
    ("robinhood","Robinhood","Finance"),
    ("coinbase","Coinbase","Finance"),
    ("marqeta","Marqeta","Finance"),
    # Healthcare
    ("oscar","Oscar Health","Healthcare"),
    ("springhealth","Spring Health","Healthcare"),
    ("modernhealth","Modern Health","Healthcare"),
    ("hims","Hims & Hers","Healthcare"),
]

# ── LEVER companies ──
LV_COMPANIES = [
    ("openai","OpenAI","Startups"),
    ("notion","Notion","Startups"),
    ("rippling","Rippling","Startups"),
    ("scale-ai","Scale AI","Startups"),
    ("mercury","Mercury","Finance"),
    ("ramp","Ramp","Finance"),
    ("brex","Brex","Finance"),
    ("sentry","Sentry","Big Tech"),
    ("drata","Drata","Startups"),
    ("deel","Deel","Startups"),
]

# ── JSEARCH keywords - covers enterprise + big company jobs ──
# These pull from LinkedIn, Indeed, Glassdoor for companies like
# Amazon, JPMorgan, Bank of America, IBM, Accenture etc.
JSEARCH_KEYWORDS = [
    # Tech roles that big companies hire for
    ("Data Analyst USA","Enterprise"),
    ("Senior Data Analyst USA","Enterprise"),
    ("Business Analyst USA","Enterprise"),
    (".NET Developer USA","Enterprise"),
    ("C# Developer USA","Enterprise"),
    ("Java Developer USA","Enterprise"),
    ("Senior Java Developer USA","Enterprise"),
    ("ServiceNow Developer USA","Enterprise"),
    ("ServiceNow Administrator USA","Enterprise"),
    ("SAP Consultant USA","Enterprise"),
    ("SAP ABAP Developer USA","Enterprise"),
    ("Salesforce Developer USA","Enterprise"),
    ("Salesforce Administrator USA","Enterprise"),
    ("Power BI Developer USA","Enterprise"),
    ("SQL Developer USA","Enterprise"),
    ("Data Engineer USA","Enterprise"),
    ("ETL Developer USA","Enterprise"),
    # Big company specific
    ("Software Engineer Amazon USA","Big Tech"),
    ("Software Engineer JPMorgan USA","Finance"),
    ("Data Analyst Bank of America USA","Finance"),
    ("Software Engineer Microsoft USA","Big Tech"),
    ("DevOps Engineer USA","Big Tech"),
    ("Cloud Engineer AWS Azure USA","Big Tech"),
    ("Full Stack Developer USA","Big Tech"),
    ("React Developer USA","Big Tech"),
    ("Python Developer USA","Big Tech"),
    ("Machine Learning Engineer USA","Big Tech"),
    ("Cybersecurity Analyst USA","Enterprise"),
    ("Network Engineer USA","Enterprise"),
    ("Systems Administrator USA","Enterprise"),
    ("Product Manager USA","Big Tech"),
    ("UX Designer USA","Big Tech"),
    ("H1B sponsorship Software Engineer USA","Big Tech"),
    ("H1B sponsor Data Analyst USA","Enterprise"),
]

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
                    "id": hashlib.md5(f"{item.get('id','')}{cid}".encode()).hexdigest()[:12],
                    "title": item.get("title",""), "company": name, "location": loc,
                    "salary": "Not listed", "job_type": "Full-time",
                    "remote_type": detect_remote(desc, loc),
                    "sponsorship": detect_sponsorship(desc),
                    "description": desc, "apply_url": item.get("absolute_url",""),
                    "category": cat, "company_size": "Tech Company", "posted_at": updated,
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
                    "id": hashlib.md5(f"{item.get('id','')}{cid}".encode()).hexdigest()[:12],
                    "title": item.get("text",""), "company": name, "location": loc,
                    "salary": "Not listed", "job_type": "Full-time",
                    "remote_type": detect_remote(desc, loc),
                    "sponsorship": detect_sponsorship(desc),
                    "description": desc, "apply_url": item.get("hostedUrl",""),
                    "category": cat, "company_size": "Tech Company", "posted_at": posted,
                })
    except: pass
    return jobs

def fetch_jsearch(keyword, category):
    jobs = []
    try:
        r = requests.get(
            "https://jsearch.p.rapidapi.com/search",
            headers={"X-RapidAPI-Key": JSEARCH_KEY, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"},
            params={
                "query": keyword,
                "page": "1",
                "num_results": "10",
                "date_posted": "week",
                "country": "us",
                "language": "en",
            },
            timeout=10
        )
        if r.status_code == 200:
            for item in r.json().get("data",[]):
                # Only include US jobs
                country = item.get("job_country","").upper()
                if country and country not in ["US","USA",""]: continue
                state = item.get("job_state","")
                city = item.get("job_city","")
                loc = f"{city}, {state}".strip(", ") if city or state else "United States"
                if not is_usa(loc) and not is_usa(item.get("job_country","")): continue
                desc = " ".join(item.get("job_description","").split())[:600]
                salary = ""
                if item.get("job_min_salary"):
                    mn = item["job_min_salary"]
                    mx = item.get("job_max_salary", mn)
                    period = item.get("job_salary_period","YEAR")
                    if period == "HOUR":
                        salary = f"${mn:.0f} - ${mx:.0f}/hr"
                    else:
                        salary = f"${mn:,.0f} - ${mx:,.0f}/yr"
                ts = item.get("job_posted_at_timestamp")
                posted = datetime.fromtimestamp(ts,tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") if ts else now_iso()
                jobs.append({
                    "id": hashlib.md5(f"{item.get('job_id','')}{keyword}".encode()).hexdigest()[:12],
                    "title": item.get("job_title",""),
                    "company": item.get("employer_name",""),
                    "location": loc or "United States",
                    "salary": salary or "Not listed",
                    "job_type": item.get("job_employment_type","Full-time"),
                    "remote_type": "Remote" if item.get("job_is_remote") else detect_remote(desc, loc),
                    "sponsorship": detect_sponsorship(desc),
                    "description": desc,
                    "apply_url": item.get("job_apply_link",""),
                    "category": category,
                    "company_size": "Unknown",
                    "posted_at": posted,
                })
        elif r.status_code == 429:
            print(f"JSearch rate limit hit for: {keyword}")
        else:
            print(f"JSearch {keyword}: HTTP {r.status_code}")
    except Exception as e:
        print(f"JSearch error {keyword}: {e}")
    return jobs

def dedupe(jobs):
    seen, out = set(), []
    for j in jobs:
        key = f"{j['title'].lower()[:25]}{j['company'].lower()[:15]}"
        if key not in seen:
            seen.add(key)
            out.append(j)
    return out

def load_company_jobs():
    jobs = []
    def fetch(c):
        api, cid, name, cat = c
        return fetch_gh(cid, name, cat) if api=="gh" else fetch_lv(cid, name, cat)
    companies = [("gh",)+c for c in GH_COMPANIES] + [("lv",)+c for c in LV_COMPANIES]
    with ThreadPoolExecutor(max_workers=10) as ex:
        for r in ex.map(fetch, companies):
            jobs.extend(r)
    return jobs

def load_jsearch_background():
    """Load JSearch jobs in background — doesn't block API responses."""
    if not JSEARCH_KEY: return
    print(f"Background: loading {len(JSEARCH_KEYWORDS)} keyword searches from JSearch...")
    jobs = []
    # Load in batches with small delay to avoid rate limiting
    with ThreadPoolExecutor(max_workers=3) as ex:
        for result in ex.map(lambda k: fetch_jsearch(k[0],k[1]), JSEARCH_KEYWORDS):
            jobs.extend(result)
            time.sleep(0.1)
    if jobs:
        existing = _cache.get("company_jobs",[])
        merged = dedupe(existing + jobs)
        merged.sort(key=lambda j: j.get("posted_at",""), reverse=True)
        _cache["jobs"] = merged
        _cache["time"] = time.time()
        print(f"Background complete: {len(jobs)} JSearch jobs added. Total: {len(merged)}")

def get_all_jobs():
    now = time.time()
    if _cache["jobs"] and (now - _cache["time"]) < CACHE_TTL:
        return _cache["jobs"]
    if _cache["loading"]:
        return _cache["jobs"]

    _cache["loading"] = True
    try:
        # Step 1: Load company jobs fast (synchronous)
        company_jobs = load_company_jobs()
        company_jobs.sort(key=lambda j: j.get("posted_at",""), reverse=True)
        _cache["company_jobs"] = company_jobs
        _cache["jobs"] = company_jobs
        _cache["time"] = now

        # Step 2: Load JSearch in background (async)
        t = threading.Thread(target=load_jsearch_background, daemon=True)
        t.start()
    finally:
        _cache["loading"] = False

    return _cache["jobs"]

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
        jobs = [j for j in jobs if
                keyword in j["title"].lower() or
                keyword in j["company"].lower() or
                keyword in j["description"].lower()]
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
            jobs = [j for j in jobs if
                    datetime.fromisoformat(j["posted_at"])
                    .replace(tzinfo=timezone.utc).timestamp()>=cutoff]
        except: pass

    total = len(jobs)
    start = (page-1)*per_page
    return jsonify({"total":total,"page":page,"per_page":per_page,"jobs":jobs[start:start+per_page]})

@app.route("/api/stats", methods=["GET"])
def stats():
    try:
        jobs = get_all_jobs()
        cats = {c: len([j for j in jobs if j["category"]==c])
                for c in ["Big Tech","Startups","Healthcare","Finance","Enterprise"]}
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
    return jsonify({"status":"ok","total_jobs":len(_cache["jobs"]),"jsearch_key":bool(JSEARCH_KEY)})

@app.route("/",methods=["GET"])
def home():
    return jsonify({"message":"JobHunter AI — USA Jobs Only","total_jobs":len(_cache["jobs"])})

if __name__ == "__main__":
    app.run(debug=True,host="0.0.0.0",port=5000)
