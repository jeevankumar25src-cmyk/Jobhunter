"""
JobHunter AI - API v14
Fixed: lazy loading, small batches, no startup blocking
"""
import requests, hashlib, time, os, threading, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, jsonify, request
from flask_cors import CORS
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0"}
ADZUNA_ID  = os.getenv("ADZUNA_ID",  "4793bcf6")
ADZUNA_KEY = os.getenv("ADZUNA_KEY", "3d8ba4f83a129b24c1edc6260b22099d")
JSEARCH_KEY = os.getenv("JSEARCH_KEY", "8acef9867emshf21b10c7e42b5acp1cc495jsn8a75d9eeeda7")

# ── CACHE ─────────────────────────────────────────────────────────────────
_cache = {"jobs": [], "time": 0, "loading": False}
_search_cache = {}
CACHE_TTL  = 1800   # 30 min full refresh
SEARCH_TTL = 600    # 10 min search cache

NON_USA = [
    "canada","toronto","vancouver","montreal","ontario",
    "uk","united kingdom","england","london","manchester",
    "india","bangalore","bengaluru","delhi","mumbai","hyderabad","pune","chennai","kolkata","noida","gurgaon",
    "germany","berlin","munich","france","paris",
    "australia","sydney","melbourne","singapore","japan","tokyo",
    "china","beijing","shanghai","brazil","mexico","ireland","dublin",
    "netherlands","amsterdam","sweden","spain","israel","poland","switzerland",
    "south korea","seoul","philippines","pakistan","nigeria","kenya",
    "south africa","egypt","uae","dubai","saudi arabia","russia","ukraine",
    "vietnam","indonesia","malaysia","europe","emea","apac","latam","worldwide","global",
]

def is_usa(loc):
    if not loc: return True
    return not any(c in loc.lower() for c in NON_USA)

def detect_sponsorship(text):
    t = text.lower()
    return any(k in t for k in ["h1b","h-1b","sponsorship","visa sponsor","will sponsor","work authorization","ead","opt"])

def detect_remote(text, loc=""):
    t = (text+" "+loc).lower()
    if any(x in t for x in ["fully remote","100% remote","work from home","remote first"]): return "Remote"
    if "hybrid" in t: return "Hybrid"
    if "remote" in t: return "Remote"
    return "On-site"

def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

def make_id(*parts):
    return hashlib.md5("".join(str(p) for p in parts).encode()).hexdigest()[:12]

def clean_text(html_or_text, limit=500):
    if not html_or_text: return ""
    if "<" in html_or_text:
        text = BeautifulSoup(html_or_text, "html.parser").get_text(separator=" ")
    else:
        text = html_or_text
    return " ".join(text.split())[:limit]

# ── GREENHOUSE (batch of 60 companies) ────────────────────────────────────
GH = [
    ("airbnb","Airbnb","Big Tech"),("stripe","Stripe","Big Tech"),
    ("databricks","Databricks","Big Tech"),("figma","Figma","Big Tech"),
    ("reddit","Reddit","Big Tech"),("cloudflare","Cloudflare","Big Tech"),
    ("hubspot","HubSpot","Big Tech"),("datadog","Datadog","Big Tech"),
    ("mongodb","MongoDB","Big Tech"),("zoom","Zoom","Big Tech"),
    ("twilio","Twilio","Big Tech"),("okta","Okta","Big Tech"),
    ("squarespace","Squarespace","Big Tech"),("zendesk","Zendesk","Big Tech"),
    ("pagerduty","PagerDuty","Big Tech"),("snyk","Snyk","Big Tech"),
    ("toast","Toast","Big Tech"),("hashicorp","HashiCorp","Big Tech"),
    ("mixpanel","Mixpanel","Big Tech"),("amplitude","Amplitude","Big Tech"),
    ("elastic","Elastic","Big Tech"),("grafana","Grafana Labs","Big Tech"),
    ("confluent","Confluent","Big Tech"),("fivetran","Fivetran","Big Tech"),
    ("segment","Segment","Big Tech"),("intercom","Intercom","Big Tech"),
    ("klaviyo","Klaviyo","Big Tech"),("braze","Braze","Big Tech"),
    ("launchdarkly","LaunchDarkly","Big Tech"),("algolia","Algolia","Big Tech"),
    ("netlify","Netlify","Big Tech"),("thoughtspot","ThoughtSpot","Big Tech"),
    ("anthropic","Anthropic","Startups"),("gusto","Gusto","Startups"),
    ("airtable","Airtable","Startups"),("webflow","Webflow","Startups"),
    ("miro","Miro","Startups"),("lattice","Lattice","Startups"),
    ("vanta","Vanta","Startups"),("retool","Retool","Startups"),
    ("drata","Drata","Startups"),("rippling","Rippling","Startups"),
    ("deel","Deel","Startups"),("scale-ai","Scale AI","Startups"),
    ("cohere","Cohere","Startups"),("huggingface","Hugging Face","Startups"),
    ("chime","Chime","Finance"),("affirm","Affirm","Finance"),
    ("robinhood","Robinhood","Finance"),("coinbase","Coinbase","Finance"),
    ("marqeta","Marqeta","Finance"),("plaid","Plaid","Finance"),
    ("carta","Carta","Finance"),("brex","Brex","Finance"),
    ("ramp","Ramp","Finance"),("oscar","Oscar Health","Healthcare"),
    ("springhealth","Spring Health","Healthcare"),("commure","Commure","Healthcare"),
    ("crowdstrike","CrowdStrike","Enterprise"),("paloaltonetworks","Palo Alto Networks","Enterprise"),
    ("sentinelone","SentinelOne","Enterprise"),("rapid7","Rapid7","Enterprise"),
]

LV = [
    ("openai","OpenAI","Startups"),("notion","Notion","Startups"),
    ("mercury","Mercury","Finance"),("sentry","Sentry","Big Tech"),
    ("canva","Canva","Big Tech"),("airbyte","Airbyte","Startups"),
    ("prefect","Prefect","Startups"),("metabase","Metabase","Big Tech"),
    ("hightouch","Hightouch","Big Tech"),("census","Census","Big Tech"),
    ("samsara","Samsara","Big Tech"),("benchling","Benchling","Healthcare"),
    ("lattice","Lattice","Startups"),("culture-amp","Culture Amp","Startups"),
    ("gem","Gem","Startups"),("ashby","Ashby","Startups"),
]

def fetch_gh(cid, name, cat):
    try:
        r = requests.get(
            f"https://boards-api.greenhouse.io/v1/boards/{cid}/jobs",
            params={"content":"true"}, headers=HEADERS, timeout=6)
        if r.status_code != 200: return []
        jobs = []
        for item in r.json().get("jobs",[])[:20]:
            loc = item.get("location",{}).get("name","United States")
            if not is_usa(loc): continue
            desc = clean_text(item.get("content",""))
            posted = (item.get("updated_at") or now_iso())[:19]
            jobs.append({"id":make_id(item.get("id",""),cid),"title":item.get("title",""),
                "company":name,"location":loc,"salary":"Not listed","job_type":"Full-time",
                "remote_type":detect_remote(desc,loc),"sponsorship":detect_sponsorship(desc),
                "description":desc,"apply_url":item.get("absolute_url",""),
                "category":cat,"posted_at":posted})
        return jobs
    except: return []

def fetch_lv(cid, name, cat):
    try:
        r = requests.get(f"https://api.lever.co/v0/postings/{cid}?mode=json",
            headers=HEADERS, timeout=6)
        if r.status_code != 200: return []
        jobs = []
        for item in r.json()[:20]:
            loc = item.get("categories",{}).get("location","United States")
            if not is_usa(loc): continue
            desc = clean_text(item.get("descriptionPlain","") or item.get("description",""))
            ts = item.get("createdAt",0)
            posted = datetime.fromtimestamp(ts/1000,tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") if ts else now_iso()
            jobs.append({"id":make_id(item.get("id",""),cid),"title":item.get("text",""),
                "company":name,"location":loc,"salary":"Not listed","job_type":"Full-time",
                "remote_type":detect_remote(desc,loc),"sponsorship":detect_sponsorship(desc),
                "description":desc,"apply_url":item.get("hostedUrl",""),
                "category":cat,"posted_at":posted})
        return jobs
    except: return []

# ── INDEED RSS ────────────────────────────────────────────────────────────
INDEED_KWS = [
    ("data analyst","Enterprise"),("data engineer","Big Tech"),
    ("business analyst","Enterprise"),("software engineer","Big Tech"),
    ("power bi developer","Enterprise"),("machine learning engineer","Big Tech"),
    ("devops engineer","Big Tech"),("sql developer","Enterprise"),
    ("python developer","Big Tech"),("cloud engineer","Big Tech"),
    (".net developer","Enterprise"),("java developer","Enterprise"),
    ("tableau developer","Enterprise"),("salesforce developer","Enterprise"),
    ("data scientist","Big Tech"),
]

def fetch_indeed(query, category):
    try:
        q = query.replace(" ","+")
        r = requests.get(
            f"https://www.indeed.com/rss?q={q}&l=United+States&sort=date&limit=25",
            headers={"User-Agent":"Mozilla/5.0"}, timeout=8)
        if r.status_code != 200: return []
        root = ET.fromstring(r.content)
        jobs = []
        for item in root.findall(".//item"):
            raw_title = item.findtext("title","")
            parts = raw_title.rsplit(" - ",1)
            title = parts[0].strip()
            company = parts[1].strip() if len(parts)>1 else ""
            link = item.findtext("link","")
            desc = clean_text(item.findtext("description",""))
            location = "United States"
            for tag in item:
                if "location" in tag.tag.lower() and tag.text:
                    location = tag.text; break
            if not is_usa(location): continue
            pub = item.findtext("pubDate","")
            try:
                from email.utils import parsedate_to_datetime
                posted = parsedate_to_datetime(pub).strftime("%Y-%m-%dT%H:%M:%S") if pub else now_iso()
            except: posted = now_iso()
            jobs.append({"id":make_id(link,query),"title":title,"company":company,
                "location":location,"salary":"Not listed","job_type":"Full-time",
                "remote_type":detect_remote(desc,location),"sponsorship":detect_sponsorship(desc),
                "description":desc,"apply_url":link,"category":category,"posted_at":posted})
        return jobs
    except: return []

# ── REMOTIVE ──────────────────────────────────────────────────────────────
def fetch_remotive():
    try:
        r = requests.get("https://remotive.com/api/remote-jobs?limit=100",
            headers=HEADERS, timeout=8)
        if r.status_code != 200: return []
        jobs = []
        for item in r.json().get("jobs",[]):
            region = item.get("candidate_required_location","")
            if region and not any(x in region.lower() for x in
                ["usa","us only","united states","worldwide","anywhere","north america",""]):
                continue
            desc = clean_text(item.get("description",""))
            cat_slug = item.get("category","")
            cat = "Enterprise" if any(x in cat_slug.lower() for x in ["data","analyst","bi"]) else "Big Tech"
            pub = item.get("publication_date","")
            try: posted = datetime.strptime(pub[:19],"%Y-%m-%dT%H:%M:%S").strftime("%Y-%m-%dT%H:%M:%S") if pub else now_iso()
            except: posted = now_iso()
            sal = item.get("salary","") or "Not listed"
            jobs.append({"id":make_id(item.get("id",""),"rem"),"title":item.get("title",""),
                "company":item.get("company_name",""),"location":"Remote","salary":sal,
                "job_type":"Full-time","remote_type":"Remote","sponsorship":detect_sponsorship(desc),
                "description":desc,"apply_url":item.get("url",""),"category":cat,"posted_at":posted})
        return jobs
    except: return []

# ── ADZUNA ────────────────────────────────────────────────────────────────
def search_adzuna(keyword, category):
    key = f"az_{keyword}"
    now = time.time()
    if key in _search_cache and (now-_search_cache[key]["time"])<SEARCH_TTL:
        return _search_cache[key]["jobs"]
    jobs = []
    try:
        r = requests.get("https://api.adzuna.com/v1/api/jobs/us/search/1",
            params={"app_id":ADZUNA_ID,"app_key":ADZUNA_KEY,"what":keyword,
                "content-type":"application/json","results_per_page":"20",
                "sort_by":"date","max_days_old":"30"},timeout=10)
        if r.status_code==200:
            for item in r.json().get("results",[]):
                area = item.get("location",{}).get("area",[])
                loc = area[-1] if area else "United States"
                if not is_usa(loc): continue
                desc = clean_text(item.get("description",""))
                mn=item.get("salary_min"); mx=item.get("salary_max",mn)
                salary=f"${mn:,.0f}–${mx:,.0f}/yr" if mn else "Not listed"
                posted=(item.get("created","") or now_iso())[:19]
                jobs.append({"id":make_id(item.get("id",""),keyword),"title":item.get("title",""),
                    "company":item.get("company",{}).get("display_name",""),
                    "location":loc,"salary":salary,"job_type":"Full-time",
                    "remote_type":detect_remote(desc,loc),"sponsorship":detect_sponsorship(desc),
                    "description":desc,"apply_url":item.get("redirect_url",""),
                    "category":category,"posted_at":posted})
    except Exception as e: print(f"Adzuna: {e}")
    _search_cache[key]={"jobs":jobs,"time":now}
    return jobs

# ── JSEARCH ───────────────────────────────────────────────────────────────
def search_jsearch(keyword, category):
    key = f"js_{keyword}"
    now = time.time()
    if key in _search_cache and (now-_search_cache[key]["time"])<SEARCH_TTL:
        return _search_cache[key]["jobs"]
    jobs = []
    try:
        r = requests.get("https://jsearch.p.rapidapi.com/search",
            headers={"X-RapidAPI-Key":JSEARCH_KEY,"X-RapidAPI-Host":"jsearch.p.rapidapi.com"},
            params={"query":f"{keyword} USA","page":"1","num_results":"20","date_posted":"month"},
            timeout=10)
        if r.status_code==200:
            for item in r.json().get("data",[]):
                city=item.get("job_city",""); state=item.get("job_state","")
                loc=f"{city}, {state}".strip(", ") or "United States"
                if not is_usa(loc): continue
                desc=clean_text(item.get("job_description",""))
                mn=item.get("job_min_salary"); mx=item.get("job_max_salary",mn)
                period=item.get("job_salary_period","YEAR")
                salary=f"${mn:.0f}–${mx:.0f}/{'hr' if period=='HOUR' else 'yr'}" if mn else "Not listed"
                ts=item.get("job_posted_at_timestamp")
                posted=datetime.fromtimestamp(ts,tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") if ts else now_iso()
                jobs.append({"id":make_id(item.get("job_id",""),keyword),"title":item.get("job_title",""),
                    "company":item.get("employer_name",""),"location":loc,"salary":salary,
                    "job_type":item.get("job_employment_type","Full-time"),
                    "remote_type":"Remote" if item.get("job_is_remote") else detect_remote(desc,loc),
                    "sponsorship":detect_sponsorship(desc),"description":desc,
                    "apply_url":item.get("job_apply_link",""),"category":category,"posted_at":posted})
    except Exception as e: print(f"JSearch: {e}")
    _search_cache[key]={"jobs":jobs,"time":now}
    return jobs

KEYWORD_MAP = {
    "data analyst":("Data Analyst","Enterprise"),
    "business analyst":("Business Analyst","Enterprise"),
    ".net":(".NET Developer","Enterprise"),
    "c#":("C# Developer","Enterprise"),
    "java":("Java Developer","Enterprise"),
    "servicenow":("ServiceNow Developer","Enterprise"),
    "sap":("SAP Consultant","Enterprise"),
    "salesforce":("Salesforce Developer","Enterprise"),
    "power bi":("Power BI Developer","Enterprise"),
    "tableau":("Tableau Developer","Enterprise"),
    "sql":("SQL Developer","Enterprise"),
    "python":("Python Developer","Big Tech"),
    "react":("React Developer","Big Tech"),
    "devops":("DevOps Engineer","Big Tech"),
    "cloud":("Cloud Engineer","Big Tech"),
    "aws":("AWS Engineer","Big Tech"),
    "azure":("Azure Developer","Big Tech"),
    "machine learning":("ML Engineer","Big Tech"),
    "data engineer":("Data Engineer","Big Tech"),
    "data scientist":("Data Scientist","Big Tech"),
    "software engineer":("Software Engineer","Big Tech"),
    "cybersecurity":("Cybersecurity Analyst","Enterprise"),
    "snowflake":("Snowflake Engineer","Enterprise"),
    "databricks":("Databricks Engineer","Big Tech"),
}

# ── MAIN CACHE BUILDER (runs in background thread) ────────────────────────
def build_cache():
    if _cache["loading"]: return
    _cache["loading"] = True
    print("Building job cache...")
    all_jobs = []

    # Batch 1: Greenhouse — 10 at a time to avoid timeout
    gh_batches = [GH[i:i+10] for i in range(0,len(GH),10)]
    for batch in gh_batches:
        with ThreadPoolExecutor(max_workers=10) as ex:
            futs = [ex.submit(fetch_gh,cid,name,cat) for cid,name,cat in batch]
            for f in as_completed(futs):
                try: all_jobs.extend(f.result())
                except: pass
        time.sleep(0.3)  # small pause between batches

    # Batch 2: Lever
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(fetch_lv,cid,name,cat) for cid,name,cat in LV]
        for f in as_completed(futs):
            try: all_jobs.extend(f.result())
            except: pass

    # Batch 3: Indeed RSS — 5 at a time
    indeed_batches = [INDEED_KWS[i:i+5] for i in range(0,len(INDEED_KWS),5)]
    for batch in indeed_batches:
        with ThreadPoolExecutor(max_workers=5) as ex:
            futs = [ex.submit(fetch_indeed,kw,cat) for kw,cat in batch]
            for f in as_completed(futs):
                try: all_jobs.extend(f.result())
                except: pass
        time.sleep(0.5)

    # Batch 4: Remotive
    all_jobs.extend(fetch_remotive())

    # Dedupe
    seen, jobs = set(), []
    for j in all_jobs:
        key = f"{j['title'].lower()[:20]}_{j['company'].lower()[:12]}"
        if key not in seen:
            seen.add(key); jobs.append(j)

    jobs.sort(key=lambda j: j.get("posted_at",""), reverse=True)
    _cache["jobs"] = jobs
    _cache["time"] = time.time()
    _cache["loading"] = False
    print(f"Cache built: {len(jobs)} jobs")

def ensure_cache():
    now = time.time()
    if not _cache["jobs"] or (now - _cache["time"]) > CACHE_TTL:
        if not _cache["loading"]:
            t = threading.Thread(target=build_cache, daemon=True)
            t.start()

# Start background cache on first request
_started = False

# ── API ROUTES ─────────────────────────────────────────────────────────────
@app.route("/api/jobs", methods=["GET"])
def search_jobs():
    global _started
    if not _started:
        _started = True
        ensure_cache()

    keyword  = request.args.get("keyword","").lower().strip()
    location = request.args.get("location","").lower()
    remote   = request.args.get("remote","").lower()
    category = request.args.get("category","")
    sponsor  = request.args.get("sponsorship","")
    hours    = request.args.get("hours","")
    page     = int(request.args.get("page",1))
    per_page = int(request.args.get("per_page",20))

    base_jobs = list(_cache["jobs"])

    # Live search from Adzuna/JSearch when keyword given
    extra = []
    if keyword:
        query, cat = keyword, "Enterprise"
        for kw,(q,c) in KEYWORD_MAP.items():
            if kw in keyword: query,cat=q,c; break
        extra = search_adzuna(query, cat)
        if not extra: extra = search_jsearch(query, cat)
        # Also Indeed live
        extra += fetch_indeed(keyword, cat)

    all_jobs = base_jobs + extra

    # Dedupe
    seen, jobs = set(), []
    for j in all_jobs:
        key = f"{j.get('title','').lower()[:20]}_{j.get('company','').lower()[:12]}"
        if key not in seen:
            seen.add(key); jobs.append(j)

    # Filter
    result = []
    for j in jobs:
        if keyword:
            txt = f"{j.get('title','')} {j.get('company','')} {j.get('description','')}".lower()
            if not any(w in txt for w in keyword.split()): continue
        if location and location not in j.get("location","").lower(): continue
        if remote and j.get("remote_type","").lower() != remote.lower(): continue
        if category and j.get("category","") != category: continue
        if sponsor=="true" and not j.get("sponsorship"): continue
        if hours:
            try:
                h = float(hours)
                p = datetime.fromisoformat(j.get("posted_at","").replace("Z","")).replace(tzinfo=timezone.utc)
                if (datetime.now(timezone.utc)-p).total_seconds() > h*3600: continue
            except: pass
        result.append(j)

    result.sort(key=lambda j: j.get("posted_at",""), reverse=True)
    total = len(result)
    start = (page-1)*per_page
    by_cat = {}
    for j in result:
        c=j.get("category","Other"); by_cat[c]=by_cat.get(c,0)+1

    return jsonify({"jobs":result[start:start+per_page],"total":total,
        "page":page,"per_page":per_page,"by_category":by_cat,
        "cache_size":len(_cache["jobs"]),"loading":_cache["loading"]})

@app.route("/api/stats", methods=["GET"])
def stats():
    global _started
    if not _started:
        _started = True
        ensure_cache()
    jobs = _cache["jobs"]
    by_cat,remote_c,sponsor_c={},0,0
    for j in jobs:
        c=j.get("category","Other"); by_cat[c]=by_cat.get(c,0)+1
        if j.get("remote_type")=="Remote": remote_c+=1
        if j.get("sponsorship"): sponsor_c+=1
    return jsonify({"total_jobs":len(jobs),"remote_jobs":remote_c,
        "sponsorship_jobs":sponsor_c,"by_category":by_cat,"loading":_cache["loading"]})

@app.route("/api/health",methods=["GET"])
def health():
    return jsonify({"status":"ok","jobs":len(_cache["jobs"]),"loading":_cache["loading"]})

@app.route("/",methods=["GET"])
def home():
    return jsonify({"message":"JobHunter AI v14","jobs":len(_cache["jobs"])})

@app.route("/api/optimize-resume",methods=["POST","OPTIONS"])
def optimize_resume():
    if request.method=="OPTIONS":
        resp=jsonify({})
        resp.headers.add("Access-Control-Allow-Origin","*")
        resp.headers.add("Access-Control-Allow-Headers","Content-Type")
        resp.headers.add("Access-Control-Allow-Methods","POST,OPTIONS")
        return resp,200
    try:
        body=request.get_json(force=True)
        if not body: return jsonify({"error":"Invalid JSON"}),400
        resume=body.get("resume","").strip()
        jd=body.get("jd","").strip()
        if not resume or len(resume)<50: return jsonify({"error":"Resume too short"}),400
        if not jd or len(jd)<30: return jsonify({"error":"JD too short"}),400
        api_key=os.getenv("ANTHROPIC_API_KEY","")
        if not api_key: return jsonify({"error":"ANTHROPIC_API_KEY not set"}),500

        prompt=f"""You are an expert ATS resume writer. Generate a perfectly tailored 100% ATS-optimized resume.

SOURCE RESUME:
{resume[:3000]}

TARGET JOB DESCRIPTION:
{jd[:2000]}

STRICT RULES:
1. Name: JEEVAN KUMAR N (never change)
2. Contact: Denton, Texas | (940) 595-8405 | jeevankumar25src@gmail.com | LinkedIn | GitHub
3. Keep Vanguard, Bank of America, LatentView Analytics with exact original dates
4. Location: Remote=Denton Texas | On-site/Hybrid=city from JD
5. Summary: 3 sentences, first opens with EXACT job title from JD
6. Tech pivot: if JD needs different stack, pivot summary+skills+ALL bullets
7. Vanguard=6-8 bullets | Bank of America=5-6 | LatentView=5-6
8. Bold JD keywords in bullets using **keyword** markers
9. Skills format: **Category:** skill1, skill2 (no bullet, bold category only)
10. Certs: Google Data Analytics Professional Certificate + Microsoft Certified: Power BI Data Analyst Associate only
11. Education: University of North Texas — M.S. Information Systems & Technology | May 2025
12. ONE PAGE — be concise

EXACT OUTPUT FORMAT:
SCORE: XX%

JEEVAN KUMAR N
Denton, Texas | (940) 595-8405 | jeevankumar25src@gmail.com | LinkedIn | GitHub

PROFESSIONAL SUMMARY
[3 sentences here]

TECHNICAL SKILLS
**Category:** skill1, skill2, skill3
**Category:** skill1, skill2

PROFESSIONAL EXPERIENCE

Vanguard | Aug 2025 – Present
Senior Data Analyst / BI Engineer
• Bullet with **bold keywords** here
[6-8 bullets]

Bank of America | Dec 2024 – Aug 2025
Business Data Analyst
• Bullet
[5-6 bullets]

LatentView Analytics | Nov 2020 – Jul 2023
Data Analyst
• Bullet
[5-6 bullets]

EDUCATION & CERTIFICATIONS
• University of North Texas — M.S. Information Systems & Technology | May 2025
• Google Data Analytics Professional Certificate
• Microsoft Certified: Power BI Data Analyst Associate

Plain text only. No HTML. No markdown except **bold**."""

        models=["claude-haiku-4-5-20251001","claude-sonnet-4-5-20250929"]
        result_text=None; last_err=None
        for model in models:
            try:
                resp=requests.post("https://api.anthropic.com/v1/messages",
                    headers={"x-api-key":api_key,"anthropic-version":"2023-06-01","content-type":"application/json"},
                    json={"model":model,"max_tokens":4000,"messages":[{"role":"user","content":prompt}]},
                    timeout=120)
                if resp.status_code==200:
                    result_text=resp.json()["content"][0]["text"]
                    print(f"Resume OK with {model}")
                    break
                else:
                    last_err=resp.json().get("error",{}).get("message","")[:100]
                    print(f"{model} failed: {last_err}")
                    if resp.status_code not in [404,400]: break
            except Exception as e:
                last_err=str(e); print(f"{model} error: {e}")
        if not result_text:
            return jsonify({"error":f"Failed: {last_err}"}),500
        return jsonify({"result":result_text})
    except Exception as e:
        print(f"Resume error: {e}")
        return jsonify({"error":str(e)}),500

if __name__=="__main__":
    app.run(debug=True,host="0.0.0.0",port=5000)
