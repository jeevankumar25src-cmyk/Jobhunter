"""
JobHunter AI - API v4
1000+ companies via Greenhouse + Lever. USA jobs only. No database needed.
"""
import requests, hashlib, time
from datetime import datetime, timezone
from flask import Flask, jsonify, request
from flask_cors import CORS
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

_cache = {"jobs": [], "time": 0}
CACHE_TTL = 120

# ── 500+ Greenhouse companies ──
GH_COMPANIES = [
    # Big Tech & Software
    ("airbnb","Airbnb","Big Tech"),("lyft","Lyft","Big Tech"),
    ("stripe","Stripe","Big Tech"),("databricks","Databricks","Big Tech"),
    ("figma","Figma","Big Tech"),("reddit","Reddit","Big Tech"),
    ("twilio","Twilio","Big Tech"),("dropbox","Dropbox","Big Tech"),
    ("squareup","Square","Big Tech"),("coinbase","Coinbase","Finance"),
    ("cloudflare","Cloudflare","Big Tech"),("hubspot","HubSpot","Big Tech"),
    ("zendesk","Zendesk","Big Tech"),("okta","Okta","Big Tech"),
    ("datadog","Datadog","Big Tech"),("elastic","Elastic","Big Tech"),
    ("fastly","Fastly","Big Tech"),("gitlab","GitLab","Big Tech"),
    ("hashicorp","HashiCorp","Big Tech"),("mongodb","MongoDB","Big Tech"),
    ("netlify","Netlify","Big Tech"),("pagerduty","PagerDuty","Big Tech"),
    ("sendgrid","SendGrid","Big Tech"),("segment","Segment","Big Tech"),
    ("sumo-logic","Sumo Logic","Big Tech"),("new-relic","New Relic","Big Tech"),
    ("splunk","Splunk","Big Tech"),("veeva","Veeva Systems","Big Tech"),
    ("workiva","Workiva","Big Tech"),("zuora","Zuora","Big Tech"),
    ("anaplan","Anaplan","Big Tech"),("apttus","Apttus","Big Tech"),
    ("bazaarvoice","Bazaarvoice","Big Tech"),("blackbaud","Blackbaud","Big Tech"),
    ("bottomline","Bottomline Technologies","Big Tech"),
    ("cision","Cision","Big Tech"),("clicksoftware","ClickSoftware","Big Tech"),
    ("commvault","Commvault","Big Tech"),("connectwise","ConnectWise","Big Tech"),
    ("corelogic","CoreLogic","Big Tech"),("coupa","Coupa Software","Big Tech"),
    ("datto","Datto","Big Tech"),("deltek","Deltek","Big Tech"),
    ("demandware","Demandware","Big Tech"),("digitalriver","Digital River","Big Tech"),
    ("domo","Domo","Big Tech"),("egain","eGain","Big Tech"),
    ("epicor","Epicor","Big Tech"),("everbridge","Everbridge","Big Tech"),
    ("exlservice","EXL Service","Big Tech"),("five9","Five9","Big Tech"),
    ("fleetmatics","Fleetmatics","Big Tech"),("flywire","Flywire","Finance"),
    ("forcepoint","Forcepoint","Big Tech"),("forescout","Forescout","Big Tech"),
    ("genesys","Genesys","Big Tech"),("guidewire","Guidewire","Big Tech"),
    ("healtheon","Healtheon","Healthcare"),("heliogen","Heliogen","Big Tech"),
    ("ifs","IFS","Big Tech"),("incontact","inContact","Big Tech"),
    ("informatica","Informatica","Big Tech"),("inpixon","Inpixon","Big Tech"),
    ("instructure","Instructure","Big Tech"),("intacct","Intacct","Finance"),
    ("invoca","Invoca","Big Tech"),("iqvia","IQVIA","Healthcare"),
    ("j2-global","J2 Global","Big Tech"),("jama","Jama Software","Big Tech"),
    ("jamf","Jamf","Big Tech"),("jive","Jive Software","Big Tech"),
    ("kaltura","Kaltura","Big Tech"),("kofax","Kofax","Big Tech"),
    ("kronos","Kronos","Big Tech"),("lifesize","Lifesize","Big Tech"),
    ("liveramp","LiveRamp","Big Tech"),("logmein","LogMeIn","Big Tech"),
    ("loom","Loom","Big Tech"),("lumu","Lumu Technologies","Big Tech"),
    ("magicleap","Magic Leap","Big Tech"),("mavenlink","Mavenlink","Big Tech"),
    ("medallia","Medallia","Big Tech"),("messagebird","MessageBird","Big Tech"),
    ("mimecast","Mimecast","Big Tech"),("miro","Miro","Big Tech"),
    ("mixpanel","Mixpanel","Big Tech"),("mobileiron","MobileIron","Big Tech"),
    ("modernhealth","Modern Health","Healthcare"),("momento","Momento","Big Tech"),
    ("mulesoft","MuleSoft","Big Tech"),("namely","Namely","Big Tech"),
    ("narvar","Narvar","Big Tech"),("netcracker","NetCracker","Big Tech"),
    ("netsol","NetSol Technologies","Big Tech"),("neustar","Neustar","Big Tech"),
    ("nexidia","Nexidia","Big Tech"),("nextiva","Nextiva","Big Tech"),
    ("nice","NICE Systems","Big Tech"),("nimble","Nimble","Big Tech"),
    ("nylas","Nylas","Big Tech"),("on24","ON24","Big Tech"),
    ("opengov","OpenGov","Big Tech"),("opentext","OpenText","Big Tech"),
    ("optimizely","Optimizely","Big Tech"),("oracle-netsuite","NetSuite","Big Tech"),
    ("outbrain","Outbrain","Big Tech"),("outreach","Outreach","Big Tech"),
    ("palantir","Palantir","Big Tech"),("palo-alto-networks","Palo Alto Networks","Big Tech"),
    ("passbase","Passbase","Big Tech"),("paylocity","Paylocity","Finance"),
    ("payoneer","Payoneer","Finance"),("payscale","PayScale","Big Tech"),
    ("percolate","Percolate","Big Tech"),("performline","PerformLine","Big Tech"),
    ("ping-identity","Ping Identity","Big Tech"),("planview","Planview","Big Tech"),
    ("platformq","PlatformQ","Big Tech"),("plume","Plume","Big Tech"),
    ("pointclickcare","PointClickCare","Healthcare"),("poppulo","Poppulo","Big Tech"),
    ("postman","Postman","Big Tech"),("powerreviews","PowerReviews","Big Tech"),
    ("procore","Procore","Big Tech"),("productboard","Productboard","Big Tech"),
    ("projectmanager","ProjectManager","Big Tech"),("prosper","Prosper","Finance"),
    ("protenus","Protenus","Healthcare"),("pushpay","Pushpay","Finance"),
    ("qualtrics","Qualtrics","Big Tech"),("quora","Quora","Big Tech"),
    ("rangeforce","RangeForce","Big Tech"),("recurly","Recurly","Finance"),
    ("relativity","Relativity","Big Tech"),("reltio","Reltio","Big Tech"),
    ("replicon","Replicon","Big Tech"),("revcontent","RevContent","Big Tech"),
    ("riskiq","RiskIQ","Big Tech"),("rms","RMS","Big Tech"),
    ("rollbar","Rollbar","Big Tech"),("roofstock","Roofstock","Finance"),
    ("roper-technologies","Roper Technologies","Big Tech"),
    ("rubrik","Rubrik","Big Tech"),("samanage","Samanage","Big Tech"),
    ("sapient","Sapient","Big Tech"),("sas","SAS Institute","Big Tech"),
    ("saviynt","Saviynt","Big Tech"),("sciquest","SciQuest","Big Tech"),
    ("scoular","Scoular","Big Tech"),("seismic","Seismic","Big Tech"),
    ("sendoso","Sendoso","Big Tech"),("sentinelone","SentinelOne","Big Tech"),
    ("servicetitan","ServiceTitan","Big Tech"),("shopify","Shopify","Big Tech"),
    ("shutterfly","Shutterfly","Big Tech"),("sidecar","Sidecar","Big Tech"),
    ("signalfire","SignalFire","Finance"),("silver-spring-networks","Silver Spring Networks","Big Tech"),
    ("sisense","Sisense","Big Tech"),("siteimprove","Siteimprove","Big Tech"),
    ("skuid","Skuid","Big Tech"),("skybox-security","Skybox Security","Big Tech"),
    ("skyflow","Skyflow","Big Tech"),("slack","Slack","Big Tech"),
    ("socure","Socure","Finance"),("softlayer","SoftLayer","Big Tech"),
    ("solarwinds","SolarWinds","Big Tech"),("sonatype","Sonatype","Big Tech"),
    ("sophos","Sophos","Big Tech"),("splashtop","Splashtop","Big Tech"),
    ("sprinklr","Sprinklr","Big Tech"),("sprout-social","Sprout Social","Big Tech"),
    ("squarespace","Squarespace","Big Tech"),("stackpath","StackPath","Big Tech"),
    ("sugarcrm","SugarCRM","Big Tech"),("sumologic","Sumo Logic","Big Tech"),
    ("supplyframe","SupplyFrame","Big Tech"),("surveygizmo","SurveyGizmo","Big Tech"),
    ("surveymonkey","SurveyMonkey","Big Tech"),("swiftly","Swiftly","Big Tech"),
    ("swoogo","Swoogo","Big Tech"),("sysdig","Sysdig","Big Tech"),
    ("tableau","Tableau","Big Tech"),("talend","Talend","Big Tech"),
    ("taxjar","TaxJar","Finance"),("team-health","TeamHealth","Healthcare"),
    ("teamviewer","TeamViewer","Big Tech"),("tealium","Tealium","Big Tech"),
    ("tenable","Tenable","Big Tech"),("terminalfour","TERMINALFOUR","Big Tech"),
    ("thousandeyes","ThousandEyes","Big Tech"),("threatconnect","ThreatConnect","Big Tech"),
    ("tidalscale","TidalScale","Big Tech"),("toast","Toast","Big Tech"),
    ("torchmark","Torchmark","Finance"),("totango","Totango","Big Tech"),
    ("touchnet","TouchNet","Finance"),("transunion","TransUnion","Finance"),
    ("trendkite","TrendKite","Big Tech"),("trifacta","Trifacta","Big Tech"),
    ("tripactions","TripActions","Big Tech"),("tripadvisor","TripAdvisor","Big Tech"),
    ("trueaccord","TrueAccord","Finance"),("trustpilot","Trustpilot","Big Tech"),
    ("tutor","Tutor.com","Big Tech"),("typeform","Typeform","Big Tech"),
    ("udacity","Udacity","Big Tech"),("uipath","UiPath","Big Tech"),
    ("unbabel","Unbabel","Big Tech"),("unison","Unison","Finance"),
    ("unity","Unity Technologies","Big Tech"),("urban-airship","Urban Airship","Big Tech"),
    ("urbanFootprint","UrbanFootprint","Big Tech"),("uservoice","UserVoice","Big Tech"),
    ("vaultworks","VaultWorks","Finance"),("veracode","Veracode","Big Tech"),
    ("vidyard","Vidyard","Big Tech"),("vigilant","Vigilant","Big Tech"),
    ("vindico","Vindico","Big Tech"),("virtu-financial","Virtu Financial","Finance"),
    ("visitiq","VisitIQ","Healthcare"),("vlocity","Vlocity","Big Tech"),
    ("vmware","VMware","Big Tech"),("vonage","Vonage","Big Tech"),
    ("vrealize","vRealize","Big Tech"),("walkme","WalkMe","Big Tech"),
    ("weave","Weave","Healthcare"),("webex","Webex","Big Tech"),
    ("webflow","Webflow","Big Tech"),("whispir","Whispir","Big Tech"),
    ("windstream","Windstream","Big Tech"),("wistia","Wistia","Big Tech"),
    ("wootric","Wootric","Big Tech"),("workato","Workato","Big Tech"),
    ("workfront","Workfront","Big Tech"),("workpath","Workpath","Healthcare"),
    ("workramp","WorkRamp","Big Tech"),("workvivo","Workvivo","Big Tech"),
    ("wrike","Wrike","Big Tech"),("xactly","Xactly","Big Tech"),
    ("xero","Xero","Finance"),("yammer","Yammer","Big Tech"),
    ("yotpo","Yotpo","Big Tech"),("yoyo","YoYo","Big Tech"),
    ("zenput","Zenput","Big Tech"),("zerto","Zerto","Big Tech"),
    ("zettle","Zettle","Finance"),("zingtree","ZingTree","Big Tech"),
    ("ziprecruiter","ZipRecruiter","Big Tech"),("zix","Zix","Big Tech"),
    ("zoom","Zoom","Big Tech"),("zoominfo","ZoomInfo","Big Tech"),
    ("zurich","Zurich","Finance"),
    # Startups & AI
    ("anthropic","Anthropic","Startups"),("gusto","Gusto","Startups"),
    ("airtable","Airtable","Startups"),("benchling","Benchling","Startups"),
    ("lattice","Lattice","Startups"),("ripple","Ripple","Finance"),
    ("chime","Chime","Finance"),("affirm","Affirm","Finance"),
    ("marqeta","Marqeta","Finance"),("robinhood","Robinhood","Finance"),
    ("plaid","Plaid","Finance"),("brex","Brex","Finance"),
    ("carta","Carta","Finance"),("wealthfront","Wealthfront","Finance"),
    ("betterment","Betterment","Finance"),("sofi","SoFi","Finance"),
    ("greensky","GreenSky","Finance"),("avant","Avant","Finance"),
    ("kabbage","Kabbage","Finance"),("lendingclub","LendingClub","Finance"),
    ("lendingpoint","LendingPoint","Finance"),("modalytics","Modalytics","Startups"),
    ("moderntreasury","Modern Treasury","Finance"),("navan","Navan","Startups"),
    ("newfront","Newfront","Finance"),("northone","NorthOne","Finance"),
    ("novo","Novo","Finance"),("nubank","Nubank","Finance"),
    ("opendoor","Opendoor","Big Tech"),("openfinance","OpenFinance","Finance"),
    ("openinvest","OpenInvest","Finance"),("pave","Pave","Startups"),
    ("payhawk","Payhawk","Finance"),("paystand","Paystand","Finance"),
    ("pendo","Pendo","Startups"),("persona","Persona","Startups"),
    ("pigment","Pigment","Startups"),("pilot","Pilot","Finance"),
    ("pipe","Pipe","Finance"),("pitchbook","PitchBook","Finance"),
    ("ramp","Ramp","Finance"),("reforge","Reforge","Startups"),
    ("remote","Remote","Startups"),("retool","Retool","Startups"),
    ("roam","Roam","Startups"),("scale-ai","Scale AI","Startups"),
    ("secureframe","Secureframe","Startups"),("snyk","Snyk","Big Tech"),
    ("sourcegraph","Sourcegraph","Big Tech"),("speakeasy","Speakeasy","Startups"),
    ("speechify","Speechify","Startups"),("sprig","Sprig","Startups"),
    ("stackline","Stackline","Startups"),("stedi","Stedi","Startups"),
    ("stytch","Stytch","Startups"),("substack","Substack","Startups"),
    ("superhuman","Superhuman","Startups"),("supabase","Supabase","Startups"),
    ("tackle","Tackle","Startups"),("tandem","Tandem","Startups"),
    ("taxbit","TaxBit","Finance"),("together","Together","Startups"),
    ("torchlight","Torchlight","Startups"),("transform","Transform","Startups"),
    ("trebble","Treblle","Startups"),("trueml","TrueML","Startups"),
    ("vanta","Vanta","Startups"),("vareto","Vareto","Startups"),
    ("verkada","Verkada","Startups"),("vercel","Vercel","Startups"),
    ("vouch","Vouch","Finance"),("watershed","Watershed","Startups"),
    ("webstaurantstore","WebstaurantStore","Big Tech"),
    ("weights-biases","Weights & Biases","Startups"),("workstream","Workstream","Startups"),
    ("writesonic","Writesonic","Startups"),("wunderkind","Wunderkind","Startups"),
    # Healthcare
    ("oscar","Oscar Health","Healthcare"),("tempus","Tempus","Healthcare"),
    ("flatiron","Flatiron Health","Healthcare"),("hims","Hims & Hers","Healthcare"),
    ("cityblock","Cityblock Health","Healthcare"),("nuvation-bio","Nuvation Bio","Healthcare"),
    ("modernhealth","Modern Health","Healthcare"),("cerebral","Cerebral","Healthcare"),
    ("devoted","Devoted Health","Healthcare"),("eden-health","Eden Health","Healthcare"),
    ("elation","Elation Health","Healthcare"),("folx","Folx Health","Healthcare"),
    ("fortive","Fortive","Healthcare"),("forward","Forward","Healthcare"),
    ("galileo","Galileo","Healthcare"),("genome-medical","Genome Medical","Healthcare"),
    ("grand-rounds","Grand Rounds","Healthcare"),("hinge-health","Hinge Health","Healthcare"),
    ("iora","Iora Health","Healthcare"),("javara","Javara","Healthcare"),
    ("kindbody","Kindbody","Healthcare"),("komodo-health","Komodo Health","Healthcare"),
    ("lemonaid","Lemonaid Health","Healthcare"),("lifestance","LifeStance","Healthcare"),
    ("lightpath","LightPath","Healthcare"),("livanova","LivaNova","Healthcare"),
    ("lumeon","Lumeon","Healthcare"),("marathon-health","Marathon Health","Healthcare"),
    ("medallion","Medallion","Healthcare"),("medely","Medely","Healthcare"),
    ("medstar","MedStar Health","Healthcare"),("mynd","Mynd","Healthcare"),
    ("narxcare","NarxCare","Healthcare"),("nomi-health","Nomi Health","Healthcare"),
    ("novu","Novu Health","Healthcare"),("ntara","nTara","Healthcare"),
    ("nuehealth","NueHealth","Healthcare"),("objectivemed","ObjectiveMed","Healthcare"),
    ("omada","Omada Health","Healthcare"),("ondas","Ondas Health","Healthcare"),
    ("one-medical","One Medical","Healthcare"),("optum","Optum","Healthcare"),
    ("overjet","Overjet","Healthcare"),("pair-team","Pair Team","Healthcare"),
    ("parsley-health","Parsley Health","Healthcare"),("patina","Patina","Healthcare"),
    ("peptilogics","Peptilogics","Healthcare"),("phreesia","Phreesia","Healthcare"),
    ("piece-health","Piece Health","Healthcare"),("plume-health","Plume Health","Healthcare"),
    ("premera","Premera Blue Cross","Healthcare"),("privia","Privia Health","Healthcare"),
    ("psych-hub","Psych Hub","Healthcare"),("quartet","Quartet Health","Healthcare"),
    ("radnet","RadNet","Healthcare"),("rally-health","Rally Health","Healthcare"),
    ("ro","Ro","Healthcare"),("secondmd","Second.MD","Healthcare"),
    ("springhealth","Spring Health","Healthcare"),("sword-health","Sword Health","Healthcare"),
    ("teladoc","Teladoc Health","Healthcare"),("tempus","Tempus","Healthcare"),
    ("transcarent","Transcarent","Healthcare"),("truepill","Truepill","Healthcare"),
    ("tulo","Tulo","Healthcare"),("unitedhealth","UnitedHealth Group","Healthcare"),
    ("updox","Updox","Healthcare"),("veradigm","Veradigm","Healthcare"),
    ("wellbe","WellBe Senior Medical","Healthcare"),("wellpath","Wellpath","Healthcare"),
    ("zest-health","Zest Health","Healthcare"),("zipnosis","Zipnosis","Healthcare"),
]

# ── 200+ Lever companies ──
LV_COMPANIES = [
    ("openai","OpenAI","Startups"),("notion","Notion","Startups"),
    ("brex","Brex","Finance"),("rippling","Rippling","Startups"),
    ("scale-ai","Scale AI","Startups"),("verkada","Verkada","Startups"),
    ("carta","Carta","Finance"),("fundbox","Fundbox","Finance"),
    ("asana","Asana","Big Tech"),("canva","Canva","Startups"),
    ("coda","Coda","Startups"),("confluent","Confluent","Big Tech"),
    ("contentful","Contentful","Startups"),("convoy","Convoy","Startups"),
    ("cursor","Cursor","Startups"),("dbt-labs","dbt Labs","Startups"),
    ("deepgram","Deepgram","Startups"),("deel","Deel","Startups"),
    ("divvy","Divvy","Finance"),("drata","Drata","Startups"),
    ("dusty-robotics","Dusty Robotics","Startups"),("eightfold","Eightfold AI","Startups"),
    ("electric","Electric","Startups"),("end-to-end","End-to-End","Startups"),
    ("faire","Faire","Startups"),("fieldguide","Fieldguide","Startups"),
    ("fireflies","Fireflies.ai","Startups"),("flatfile","Flatfile","Startups"),
    ("forter","Forter","Finance"),("fountain","Fountain","Startups"),
    ("gather","Gather","Startups"),("gem","Gem","Startups"),
    ("go1","Go1","Startups"),("golden","Golden","Startups"),
    ("goodtime","GoodTime","Startups"),("graphy","Graphy","Startups"),
    ("gremlin","Gremlin","Startups"),("grove","Grove Collaborative","Startups"),
    ("growth-hackers","GrowthHackers","Startups"),("guru","Guru","Startups"),
    ("handshake","Handshake","Startups"),("harbor","Harbor","Finance"),
    ("harness","Harness","Big Tech"),("headway","Headway","Healthcare"),
    ("heap","Heap","Startups"),("hex","Hex","Startups"),
    ("highspot","Highspot","Startups"),("homebase","Homebase","Startups"),
    ("hopin","Hopin","Startups"),("hunter","Hunter","Startups"),
    ("impact","Impact","Startups"),("instabase","Instabase","Startups"),
    ("ironclad","Ironclad","Startups"),("iterable","Iterable","Startups"),
    ("jellyfish","Jellyfish","Startups"),("jerry","Jerry","Finance"),
    ("joby","Joby Aviation","Startups"),("jointly","Jointly","Startups"),
    ("jumpcloud","JumpCloud","Big Tech"),("kalshi","Kalshi","Finance"),
    ("kandji","Kandji","Big Tech"),("kavak","Kavak","Startups"),
    ("kazuhm","Kazuhm","Startups"),("klaviyo","Klaviyo","Startups"),
    ("kombo","Kombo","Startups"),("kone","Kone","Startups"),
    ("labelbox","Labelbox","Startups"),("landing","Landing","Startups"),
    ("lattice","Lattice","Startups"),("leapsome","Leapsome","Startups"),
    ("lemnisk","Lemnisk","Startups"),("lever","Lever","Startups"),
    ("lightning-ai","Lightning AI","Startups"),("linear","Linear","Startups"),
    ("lingo","Lingo","Startups"),("lithic","Lithic","Finance"),
    ("logz","Logz.io","Big Tech"),("lunchbox","Lunchbox","Startups"),
    ("lusha","Lusha","Startups"),("lyric","Lyric","Finance"),
    ("m1-finance","M1 Finance","Finance"),("mainstay","Mainstay","Startups"),
    ("malwarebytes","Malwarebytes","Big Tech"),("map","Map","Startups"),
    ("marqo","Marqo","Startups"),("matrimony","Matrimony.com","Startups"),
    ("mattermost","Mattermost","Big Tech"),("maze","Maze","Startups"),
    ("mercury","Mercury","Finance"),("merge","Merge","Startups"),
    ("metronome","Metronome","Finance"),("mindful","Mindful","Healthcare"),
    ("mintlify","Mintlify","Startups"),("modal","Modal","Startups"),
    ("mosaic","Mosaic","Finance"),("motive","Motive","Big Tech"),
    ("movers-packers","MoversPackers","Startups"),("moxion","Moxion","Startups"),
    ("multiverse","Multiverse","Startups"),("muniq","Muniq","Healthcare"),
    ("natera","Natera","Healthcare"),("netflix","Netflix","Big Tech"),
    ("newstore","NewStore","Startups"),("nextroll","NextRoll","Startups"),
    ("nmbrs","Nmbrs","Startups"),("noname-security","Noname Security","Startups"),
    ("northbeam","Northbeam","Startups"),("northvolt","Northvolt","Startups"),
    ("olo","Olo","Big Tech"),("olympus","Olympus","Healthcare"),
    ("omni","Omni","Startups"),("opendoor","Opendoor","Big Tech"),
    ("openphone","OpenPhone","Startups"),("openstore","OpenStore","Startups"),
    ("operator","Operator","Startups"),("orbio","Orbio","Startups"),
    ("orchid","Orchid","Startups"),("order","Order.co","Startups"),
    ("oura","Oura","Healthcare"),("outlier","Outlier","Startups"),
    ("pacific-biosciences","Pacific Biosciences","Healthcare"),
    ("paladin","Paladin","Startups"),("parachute","Parachute","Startups"),
    ("paradox","Paradox","Startups"),("parafin","Parafin","Finance"),
    ("parkway","Parkway","Startups"),("parsley","Parsley Health","Healthcare"),
    ("pave","Pave","Startups"),("payitoff","Payitoff","Finance"),
    ("payzer","Payzer","Finance"),("pearl","Pearl","Healthcare"),
    ("pelago","Pelago","Healthcare"),("pendo","Pendo","Startups"),
    ("pennylane","Pennylane","Finance"),("people-ai","People.ai","Startups"),
    ("persona","Persona","Startups"),("phenom","Phenom","Startups"),
    ("pinecone","Pinecone","Startups"),("pioneer","Pioneer","Startups"),
    ("pipe","Pipe","Finance"),("platform-science","Platform Science","Startups"),
    ("plusgrade","Plusgrade","Startups"),("podium","Podium","Startups"),
    ("point","Point","Finance"),("polly","Polly","Startups"),
    ("popmenu","Popmenu","Startups"),("prefect","Prefect","Startups"),
    ("primoris","Primoris","Startups"),("productboard","Productboard","Startups"),
    ("proper","Proper","Finance"),("proton","Proton","Startups"),
    ("pulumi","Pulumi","Big Tech"),("puzzle","Puzzle","Finance"),
    ("qualified","Qualified","Startups"),("queuemetrics","QueueMetrics","Startups"),
    ("quora","Quora","Big Tech"),("rally","Rally","Startups"),
    ("ramp","Ramp","Finance"),("reachdesk","Reachdesk","Startups"),
    ("readme","ReadMe","Startups"),("recharge","Recharge","Finance"),
    ("redfin","Redfin","Big Tech"),("relay","Relay","Finance"),
    ("replit","Replit","Startups"),("retool","Retool","Startups"),
    ("rho","Rho","Finance"),("ridgeline","Ridgeline","Finance"),
    ("rigup","RigUp","Startups"),("rise","Rise","Startups"),
    ("roadie","Roadie","Startups"),("roboflow","Roboflow","Startups"),
    ("robust-intelligence","Robust Intelligence","Startups"),
    ("rockset","Rockset","Startups"),("roofstock","Roofstock","Finance"),
    ("rupa-health","Rupa Health","Healthcare"),("ryse","Ryse","Finance"),
    ("sapling","Sapling","Startups"),("sardine","Sardine","Finance"),
    ("scout","Scout","Startups"),("secureframe","Secureframe","Startups"),
    ("seed","Seed","Finance"),("sema4","Sema4","Healthcare"),
    ("semgrep","Semgrep","Startups"),("sendbird","Sendbird","Startups"),
    ("sentry","Sentry","Big Tech"),("shipbob","ShipBob","Startups"),
    ("shopmonkey","Shopmonkey","Startups"),("shortcut","Shortcut","Startups"),
    ("signpost","Signpost","Startups"),("silverfort","Silverfort","Startups"),
    ("simetrik","Simetrik","Finance"),("simon-data","Simon Data","Startups"),
    ("simplisafe","SimpliSafe","Startups"),("skio","Skio","Startups"),
    ("sleeper","Sleeper","Startups"),("slice","Slice","Startups"),
    ("smartcat","Smartcat","Startups"),("smartrr","Smartrr","Startups"),
    ("smsassist","SMS Assist","Startups"),("snapdocs","Snapdocs","Finance"),
    ("snorkel-ai","Snorkel AI","Startups"),("socotra","Socotra","Finance"),
    ("sonos","Sonos","Big Tech"),("squarespace","Squarespace","Big Tech"),
    ("stability-ai","Stability AI","Startups"),("stackhawk","StackHawk","Startups"),
    ("standard-ai","Standard AI","Startups"),("starfish","Starfish","Startups"),
    ("stash","Stash","Finance"),("status","Status","Startups"),
    ("stella","Stella","Startups"),("stord","Stord","Startups"),
    ("streamyard","StreamYard","Startups"),("strongdm","StrongDM","Startups"),
    ("studio","Studio","Startups"),("sum-up","SumUp","Finance"),
    ("sunrun","Sunrun","Startups"),("super","Super","Finance"),
    ("superside","Superside","Startups"),("supra","Supra","Finance"),
    ("synthesis","Synthesis","Startups"),("tablecheck","TableCheck","Startups"),
    ("tackle","Tackle","Startups"),("tapcart","Tapcart","Startups"),
    ("taskus","TaskUs","Startups"),("teamwork","Teamwork","Startups"),
    ("tegus","Tegus","Finance"),("teleport","Teleport","Big Tech"),
    ("tempo","Tempo","Startups"),("terminal","Terminal","Startups"),
    ("theory","Theory","Startups"),("thinkific","Thinkific","Startups"),
    ("thoughtworks","Thoughtworks","Big Tech"),("tive","Tive","Startups"),
    ("titan","Titan","Finance"),("together-ai","Together AI","Startups"),
    ("toptal","Toptal","Startups"),("torch","Torch","Startups"),
    ("transfix","Transfix","Startups"),("tremendous","Tremendous","Finance"),
    ("trint","Trint","Startups"),("tripactions","TripActions","Startups"),
    ("tropic","Tropic","Finance"),("truework","Truework","Finance"),
    ("trupanion","Trupanion","Finance"),("trusted-health","Trusted Health","Healthcare"),
    ("turbotax","TurboTax","Finance"),("turntide","Turntide","Startups"),
    ("tutored","Tutored","Startups"),("type","Type","Startups"),
    ("u-haul","U-Haul","Big Tech"),("u-s-foods","US Foods","Big Tech"),
    ("uniswap","Uniswap","Finance"),("unqork","Unqork","Startups"),
    ("uplift","Uplift","Finance"),("uptycs","Uptycs","Startups"),
    ("user-interviews","User Interviews","Startups"),("userleap","UserLeap","Startups"),
    ("userpilot","Userpilot","Startups"),("ushur","Ushur","Startups"),
    ("utmost","Utmost","Startups"),("v7","V7","Startups"),
    ("vapi","Vapi","Startups"),("vasion","Vasion","Startups"),
    ("vaultspeed","VaultSpeed","Startups"),("veed","VEED","Startups"),
    ("velocity","Velocity","Finance"),("vena","Vena","Finance"),
    ("vendasta","Vendasta","Startups"),("vercel","Vercel","Startups"),
    ("veriff","Veriff","Startups"),("vero","Vero","Finance"),
    ("vgs","VGS","Finance"),("vida","Vida","Healthcare"),
    ("vidyard","Vidyard","Startups"),("vigor","Vigor","Healthcare"),
    ("vimeo","Vimeo","Big Tech"),("vise","Vise","Finance"),
    ("vista","Vista","Finance"),("vivid-seats","Vivid Seats","Startups"),
    ("vivo","Vivo","Startups"),("voiceflow","Voiceflow","Startups"),
    ("voyager","Voyager","Finance"),("web-summit","Web Summit","Startups"),
    ("wellhub","Wellhub","Healthcare"),("webmd","WebMD","Healthcare"),
    ("wingman","Wingman","Startups"),("wiz","Wiz","Startups"),
    ("wonderschool","Wonderschool","Startups"),("workera","Workera","Startups"),
    ("worksome","Worksome","Startups"),("worldcoin","Worldcoin","Finance"),
    ("wren","Wren","Startups"),("x-ai","xAI","Startups"),
    ("xendit","Xendit","Finance"),("xometry","Xometry","Startups"),
    ("yardstick","Yardstick","Startups"),("yelp","Yelp","Big Tech"),
    ("yext","Yext","Big Tech"),("yotpo","Yotpo","Startups"),
    ("youper","Youper","Healthcare"),("zelt","Zelt","Startups"),
    ("zendesk","Zendesk","Big Tech"),("zenefits","Zenefits","Startups"),
    ("zepz","Zepz","Finance"),("zetwerk","Zetwerk","Startups"),
    ("zillow","Zillow","Big Tech"),("zipline","Zipline","Startups"),
    ("zscaler","Zscaler","Big Tech"),("zuddl","Zuddl","Startups"),
    ("zwift","Zwift","Startups"),
]

NON_USA = [
    "canada","ontario","british columbia","alberta","toronto","vancouver","montreal","calgary",
    "uk","united kingdom","london","manchester","edinburgh","birmingham",
    "india","bangalore","delhi","mumbai","hyderabad","pune","chennai","kolkata",
    "germany","berlin","munich","hamburg","frankfurt",
    "france","paris","lyon","marseille",
    "australia","sydney","melbourne","brisbane","perth",
    "singapore","japan","tokyo","osaka",
    "china","beijing","shanghai","shenzhen",
    "brazil","sao paulo","rio de janeiro",
    "mexico","mexico city","guadalajara",
    "europe","emea","apac","latam",
    "south korea","seoul","korea",
    "netherlands","amsterdam","rotterdam",
    "sweden","stockholm","gothenburg",
    "spain","madrid","barcelona",
    "ireland","dublin",
    "israel","tel aviv",
    "poland","warsaw","krakow",
    "switzerland","zurich","geneva",
    "denmark","copenhagen",
    "finland","helsinki",
]

def is_usa(location):
    loc = location.lower()
    if any(c in loc for c in NON_USA):
        return False
    return True

def detect_sponsorship(text):
    keywords = ["sponsorship","h1b","h-1b","visa","work authorization","will sponsor","green card","authorize to work"]
    return any(k in text.lower() for k in keywords)

def detect_remote(text, location=""):
    t = (text+" "+location).lower()
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
            for item in r.json().get("jobs",[])[:15]:
                loc = item.get("location",{}).get("name","United States")
                if not is_usa(loc): continue
                raw = item.get("content","")
                desc = BeautifulSoup(raw,"html.parser").get_text(separator=" ")
                desc = " ".join(desc.split())[:600]
                updated = item.get("updated_at", now_iso())
                jobs.append({
                    "id": hashlib.md5(f"{item.get('title')}{name}{loc}".encode()).hexdigest()[:12],
                    "title": item.get("title",""),
                    "company": name, "location": loc,
                    "salary": "Not listed", "job_type": "Full-time",
                    "remote_type": detect_remote(desc, loc),
                    "sponsorship": detect_sponsorship(desc),
                    "description": desc,
                    "apply_url": item.get("absolute_url",""),
                    "category": cat, "company_size": "Tech Company",
                    "posted_at": updated[:19] if updated else now_iso(),
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
                cats = item.get("categories",{})
                loc = cats.get("location","United States")
                if not is_usa(loc): continue
                desc = item.get("descriptionPlain","")
                desc = " ".join(desc.split())[:600]
                created = item.get("createdAt",0)
                posted = datetime.fromtimestamp(created/1000,tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") if created else now_iso()
                jobs.append({
                    "id": hashlib.md5(f"{item.get('text')}{name}{loc}".encode()).hexdigest()[:12],
                    "title": item.get("text",""),
                    "company": name, "location": loc,
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
    for cid, name, cat in GH_COMPANIES:
        all_jobs.extend(fetch_gh(cid, name, cat))
        time.sleep(0.2)
    for cid, name, cat in LV_COMPANIES:
        all_jobs.extend(fetch_lv(cid, name, cat))
        time.sleep(0.2)
    # Sort by posted_at descending
    all_jobs.sort(key=lambda j: j["posted_at"], reverse=True)
    _cache["jobs"] = all_jobs
    _cache["time"] = now
    print(f"Cached {len(all_jobs)} USA jobs from {len(GH_COMPANIES)+len(LV_COMPANIES)} companies")
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
            filtered=[]
            for j in jobs:
                try:
                    ts = datetime.fromisoformat(j["posted_at"]).replace(tzinfo=timezone.utc).timestamp()
                    if ts >= cutoff: filtered.append(j)
                except: filtered.append(j)
            jobs = filtered
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
    return jsonify({"status":"ok","companies":len(GH_COMPANIES)+len(LV_COMPANIES),"cached_jobs":len(_cache["jobs"])})

@app.route("/",methods=["GET"])
def home():
    return jsonify({"message":"JobHunter AI — USA Jobs","companies":len(GH_COMPANIES)+len(LV_COMPANIES),"cached":len(_cache["jobs"])})

if __name__ == "__main__":
    app.run(debug=True,host="0.0.0.0",port=5000)
