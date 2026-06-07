#!/usr/bin/env python3
"""
persona_factory.py  v0.8 — occupation-tier psychology + education-occupation gate.

Fixes the "graduate-degree mason with corporate imposter-syndrome" contamination
by binding all psychology/vocabulary/style to the OCCUPATION TIER, not the
socioeconomic latent, and by reconciling education with occupation:

  * Education-occupation gate : a graduate/PG is never a manual labourer — the
    occupation pivots to clerical / teaching / skilled self-employment; a
    corporate role never has below-Class-12 education.
  * Occupation tiers : manual / skilled / officer / corporate. Corporate
    psychology (imposter syndrome, north-star metrics, intellectual mastery) is
    confined to the corporate tier; manual roles get security/tangible/asset-
    defence motivation only.
  * Trade vocabulary bound to occupation nodes (mason -> dihaadi/thekedar/naka/
    karni/radda; tailor -> silai/kapda/naap; merchant -> vyapaar/grahak/udhaari;
    corporate -> target/scope/alignment).

Plus the v0.7 interlocking dependencies (trade-schedule matrix, region x caste
surnames, NCCS-scaled loss aversion, lajja/conformity deference loop, dialects,
age/trade/region-anchored memory). Self-contained (stdlib). Flagged interim.
Usage: python3 persona_factory.py --count 100000 --out personas
"""
import argparse, json, os, random, time, uuid, signal
from datetime import datetime, timezone

STATES = {
 "Uttar Pradesh":dict(w=.166,region="North",rural=.78,langs={"Hindi":.80,"Urdu":.10,"Bhojpuri":.10}),
 "Maharashtra":dict(w=.092,region="West",rural=.55,langs={"Marathi":.70,"Hindi":.20,"Urdu":.10}),
 "Bihar":dict(w=.086,region="East",rural=.88,langs={"Hindi":.50,"Maithili":.20,"Bhojpuri":.20,"Urdu":.10}),
 "West Bengal":dict(w=.075,region="East",rural=.68,langs={"Bengali":.85,"Hindi":.08,"Urdu":.07},rel={"Hindu":.70,"Muslim":.27,"Christian":.03}),
 "Madhya Pradesh":dict(w=.060,region="Central",rural=.72,langs={"Hindi":.85,"Bundeli":.08,"Malvi":.07}),
 "Tamil Nadu":dict(w=.057,region="South",rural=.52,langs={"Tamil":.90,"Telugu":.06,"Urdu":.04},rel={"Hindu":.87,"Christian":.06,"Muslim":.07}),
 "Rajasthan":dict(w=.057,region="North",rural=.75,langs={"Hindi":.78,"Marwari":.16,"Mewari":.06}),
 "Karnataka":dict(w=.051,region="South",rural=.61,langs={"Kannada":.66,"Urdu":.11,"Telugu":.06,"Tamil":.04,"Hindi":.13}),
 "Gujarat":dict(w=.050,region="West",rural=.57,langs={"Gujarati":.86,"Hindi":.09,"Bhili":.05}),
 "Andhra/Telangana":dict(w=.070,region="South",rural=.62,langs={"Telugu":.84,"Urdu":.13,"Hindi":.03}),
 "Odisha":dict(w=.035,region="East",rural=.83,langs={"Odia":.86,"Hindi":.06,"Sambalpuri":.05,"Santali":.03}),
 "Kerala":dict(w=.028,region="South",rural=.52,langs={"Malayalam":.97,"Tamil":.03},rel={"Hindu":.55,"Muslim":.27,"Christian":.18}),
 "Jharkhand":dict(w=.027,region="East",rural=.76,langs={"Hindi":.50,"Khortha":.14,"Santali":.12,"Nagpuri":.12,"Ho":.07,"Kurukh":.05}),
 "Assam":dict(w=.026,region="Northeast",rural=.86,langs={"Assamese":.55,"Bengali":.29,"Bodo":.10,"Mishing":.06},rel={"Hindu":.61,"Muslim":.34,"Christian":.05}),
 "Punjab":dict(w=.023,region="North",rural=.62,langs={"Punjabi":.92,"Hindi":.08},rel={"Sikh":.58,"Hindu":.38,"Christian":.04}),
 "Haryana":dict(w=.021,region="North",rural=.65,langs={"Hindi":.85,"Haryanvi":.12,"Punjabi":.03}),
 "Delhi":dict(w=.014,region="North",rural=.03,langs={"Hindi":.81,"Punjabi":.08,"Urdu":.07,"Bengali":.04}),
 "Chhattisgarh":dict(w=.025,region="Central",rural=.77,langs={"Hindi":.70,"Chhattisgarhi":.25,"Odia":.05}),
 "Uttarakhand":dict(w=.010,region="North",rural=.70,langs={"Hindi":.88,"Garhwali":.07,"Kumaoni":.05}),
 "Himachal Pradesh":dict(w=.007,region="North",rural=.90,langs={"Hindi":.90,"Pahari":.10}),
 "Goa":dict(w=.002,region="West",rural=.38,langs={"Konkani":.66,"Marathi":.20,"Hindi":.14},rel={"Hindu":.66,"Christian":.25,"Muslim":.09}),
 "Tripura":dict(w=.004,region="Northeast",rural=.74,langs={"Bengali":.65,"Kokborok":.25,"Hindi":.10},rel={"Hindu":.83,"Muslim":.09,"Christian":.08}),
 "Manipur":dict(w=.003,region="Northeast",rural=.70,langs={"Meitei (Manipuri)":.53,"Thadou":.20,"Tangkhul":.15,"Hindi":.12},rel={"Hindu":.41,"Christian":.41,"Muslim":.08,"Other":.10}),
 "Jammu & Kashmir":dict(w=.011,region="North",rural=.73,langs={"Kashmiri":.53,"Dogri":.20,"Urdu":.17,"Hindi":.10},rel={"Muslim":.68,"Hindu":.28,"Sikh":.04}),
}
REL_DEFAULT={"Hindu":.795,"Muslim":.142,"Christian":.023,"Sikh":.017,"Buddhist":.007,"Jain":.004,"Other":.012}
CATEGORY={"OBC":.41,"General":.29,"SC":.20,"ST":.09}
AGE_BANDS={"18-24":.18,"25-34":.24,"35-44":.21,"45-59":.22,"60+":.15}
BAND_RANGE={"18-24":(18,24),"25-34":(25,34),"35-44":(35,44),"45-59":(45,59),"60+":(60,78)}
EDU=[("no formal schooling",0,.12),("some schooling",.12,.35),("Class 10",.35,.55),("Class 12",.55,.7),("a graduate degree",.7,.9),("a postgraduate degree",.9,1.01)]
GRAD={"a graduate degree","a postgraduate degree"}; LOWED={"no formal schooling","some schooling","Class 10"}
CLASS_DESC={"A1":"affluent","A2":"affluent","A3":"upper-middle","B1":"upper-middle","B2":"middle","C1":"lower-middle","C2":"lower-middle","D":"poor","E1":"very poor","E2":"very poor","E3":"very poor"}
NCCS_BY_SES=["E3","E2","E1","D","D","C2","C2","C1","C1","B2","B2","B1","A3","A2","A1"]
LAM={"A1":(1.9,2.05),"A2":(1.95,2.1),"A3":(2.0,2.1),"B1":(2.0,2.15),"B2":(2.1,2.25),"C1":(2.2,2.35),"C2":(2.25,2.4),"D":(2.4,2.65),"E1":(2.55,2.8),"E2":(2.6,2.9),"E3":(2.7,3.0)}
# capital index c∈[0,1] and reference income per NCCS (see PERSONA_MATHEMATICAL_MODEL.md §2,§4)
CAPIDX={"E3":0.0,"E2":0.1,"E1":0.2,"D":0.3,"C2":0.4,"C1":0.5,"B2":0.6,"B1":0.7,"A3":0.8,"A2":0.9,"A1":1.0}
REF_INC={"A1":120000,"A2":90000,"A3":60000,"B1":45000,"B2":30000,"C1":20000,"C2":15000,"D":9000,"E1":7000,"E2":5500,"E3":4000}
def peak_exh_hour(o):
    if any(k in o for k in("mason","construction","daily-wage")): return 18.0
    if "vendor" in o: return 21.0
    if any(k in o for k in("farmer","cultivator","agricultural","dairy")): return 13.0
    if any(k in o for k in("driver","rider")): return 17.0
    return 17.0
OCC_RURAL_LOW=["agricultural labourer","small farmer","daily-wage labourer","dairy/livestock worker"]
OCC_RURAL_MID=["owner-cultivator","kirana shopkeeper","mason","ASHA worker","tractor/truck driver","tailoring/boutique owner","tuition teacher","anganwadi worker"]
OCC_URBAN_LOW=["daily-wage labourer","domestic worker","street vendor","construction worker","delivery rider"]
OCC_URBAN_MID=["shop assistant","small trader","factory operator","clerk","auto/cab driver","nurse","tailoring/boutique owner","tuition teacher"]
OCC_HIGH=["government officer","schoolteacher","software professional","bank employee","doctor","business owner","college student"]
# (occupation TIERS — psychology is bound to these, not to the SES latent)
CORP={"software professional","business owner","bank employee","doctor"}
OFFICER={"government officer","schoolteacher","clerk","nurse"}
SKILLED={"kirana shopkeeper","small trader","shop assistant","owner-cultivator","ASHA worker","anganwadi worker","tailoring/boutique owner","tuition teacher","college student"}
def occ_tier(o):
    if o in CORP: return "corporate"
    if o in OFFICER: return "officer"
    if o in SKILLED: return "skilled"
    return "manual"
EDU_PIVOT_RURAL=["schoolteacher","tuition teacher","clerk","ASHA worker","anganwadi worker","tailoring/boutique owner","small trader","nurse"]
EDU_PIVOT_URBAN=["clerk","schoolteacher","shop assistant","small trader","nurse","bank employee","tuition teacher"]
QUIRKS_LOW=["counts cash twice before handing it over","won't start important work on an inauspicious day","keeps key papers locked in a steel almirah","saves the 'good' clothes only for festivals","haggles on reflex, even small amounts","screenshots or notes down every payment"]
QUIRKS_HIGH=["over-documents everything as a way to manage anxiety","re-checks a decision several times before committing","makes lists for everything","goes quiet and structured when stressed","researches exhaustively before any purchase","keeps work and home strictly separated"]
FEARS_LOW=["that one bad season or illness undoes years of saving","that the children will not do better than them","falling ill with no real safety net","what the community will say if things go wrong (log kya kahenge)","sliding back into debt"]
# tier psychology (drivers / hidden_fears / quirks / (stress_driver, trigger, coping))
TIER_PSYCH={
 "corporate":dict(drivers=["recognition at work","intellectual mastery","financial independence","a head start for the children"],
   fears=["imposter syndrome — that one failure will expose them as not good enough","guilt that ambition steals time from family","being left behind as their field changes","losing the lifestyle they have built"],
   quirks=QUIRKS_HIGH, stress=("achievement and milestones","loss of control, vague metrics, unexpected conflict","over-prepares, withdraws into structured problem-solving, suppresses emotion at work")),
 "officer":dict(drivers=["a stable, respected career","the children's future","standing in society","doing the job by the book"],
   fears=["being passed over or stuck in the same post","an unwanted transfer or instability","not living up to expectations","loss of standing"],
   quirks=["goes quiet and methodical under stress","keeps everything documented and by-procedure","double-checks before committing"],
   stress=("a stable career and order","loss of control, audits, unexpected conflict","goes quiet and structured, withdraws into methodical problem-solving")),
 "skilled":dict(drivers=["growing the work / more customers or students","the children's schooling","financial autonomy and own income","steady advancement and respect"],
   fears=["the work drying up or a slow season","unreliable equipment, power cuts or late payments","losing regular customers or students","the income staying unpredictable"],
   quirks=["keeps detailed accounts/records","double-checks the work before committing","reconciles the day's takings every evening","keeps tools and stock in careful order"],
   stress=("order and financial predictability","unreliable equipment, late payments, or disputes over price/fees","withdraws into precise work, leans on a savings group or trusted peers, cuts non-essentials quietly")),
 "manual":dict(drivers=["providing for the family","steady daily work","the children's schooling","staying out of debt"],
   fears=FEARS_LOW, quirks=QUIRKS_LOW,
   stress=("providing for and protecting the family","money running short, a health shock, or no work that day","leans on family and the savings group, takes any work going, prays / waits it out")),
}
NAMES={
 "Hindu_m":["Ramesh","Suresh","Arjun","Vikram","Mohan","Rohit","Sanjay","Deepak","Manoj","Kiran","Anil","Prakash"],
 "Hindu_f":["Sunita","Lakshmi","Priya","Anita","Kavita","Pooja","Rekha","Meena","Geeta","Asha","Savita","Radha"],
 "Muslim_m":["Imran","Salman","Faizal","Aamir","Rashid","Javed","Sohail","Tariq","Naseem","Arif"],
 "Muslim_f":["Ayesha","Fatima","Nasreen","Rukhsana","Shabana","Heena","Zoya","Sana","Farah","Razia"],
 "Sikh_m":["Gurpreet","Harjeet","Manpreet","Jaswinder","Baljit"],"Sikh_f":["Harpreet","Simran","Gurleen","Manjeet","Jasleen"],
 "Christian_m":["Thomas","George","Joseph","Roshan","Daniel"],"Christian_f":["Mary","Anjali","Grace","Reena","Nisha"],
 "default_m":["Arun","Kumar","Raju","Sandeep","Vijay","Naveen"],"default_f":["Devi","Shanti","Usha","Rani","Pushpa","Maya"]}
SURN_REL={"Muslim":["Khan","Sheikh","Ansari","Qureshi","Pathan","Sayyed","Mirza"],"Sikh":["Sandhu","Gill","Dhillon","Brar","Bedi"],"Christian":["Thomas","George","D'Souza","Fernandes","Pinto","Mathew","Jacob"]}
NR={"Uttar Pradesh":"Hindi-belt","Bihar":"Hindi-belt","Madhya Pradesh":"Hindi-belt","Rajasthan":"Hindi-belt","Haryana":"Hindi-belt","Delhi":"Hindi-belt","Jharkhand":"Hindi-belt","Chhattisgarh":"Hindi-belt","Uttarakhand":"Hindi-belt","Himachal Pradesh":"Hindi-belt","Manipur":"Hindi-belt",
 "West Bengal":"Bengali","Tripura":"Bengali","Odisha":"Odia","Assam":"Assamese","Maharashtra":"Marathi","Goa":"Marathi","Gujarat":"Gujarati","Tamil Nadu":"Tamil","Karnataka":"Kannada","Andhra/Telangana":"Telugu","Kerala":"Malayalam","Punjab":"Punjabi-Hindu","Jammu & Kashmir":"Kashmiri"}
SURN={
 "Hindi-belt":{"General":["Sharma","Tiwari","Mishra","Pandey","Singh","Chauhan","Dubey","Shukla","Tripathi","Srivastava"],"OBC":["Yadav","Kushwaha","Maurya","Kurmi","Sahu","Patel","Verma","Nishad","Mahato"],"SC":["Paswan","Jatav","Valmiki","Ram","Gautam","Kumar","Rawat"],"ST":["Oraon","Munda","Gond","Bhil","Meena"]},
 "Bengali":{"General":["Banerjee","Chatterjee","Mukherjee","Ghosh","Bose","Sen","Dutta"],"OBC":["Mahato","Sahu","Pramanik"],"SC":["Mondal","Biswas","Das","Sarkar","Halder"],"ST":["Murmu","Soren","Hansda","Tudu"]},
 "Odia":{"General":["Patnaik","Mohanty","Mishra","Panda","Rath"],"OBC":["Sahoo","Behera","Pradhan"],"SC":["Nayak","Das","Jena"],"ST":["Majhi","Marndi","Hembram"]},
 "Assamese":{"General":["Bora","Saikia","Sarma","Hazarika"],"OBC":["Gogoi","Kalita","Nath"],"SC":["Das","Namasudra"],"ST":["Boro","Basumatary","Brahma"]},
 "Marathi":{"General":["Deshmukh","Kulkarni","Joshi","Deshpande","Patil"],"OBC":["Jadhav","Pawar","Shinde","More","Bhosale"],"SC":["Kamble","Gaikwad","Sonawane","Waghmare","Ahire"],"ST":["Pawra","Gavit","Valvi"]},
 "Gujarati":{"General":["Shah","Mehta","Desai","Trivedi","Joshi"],"OBC":["Patel","Prajapati","Thakor"],"SC":["Parmar","Solanki","Makwana","Vaghela"],"ST":["Rathwa","Damor","Bhabhor"]},
 "Tamil":{"General":["Iyer","Iyengar","Sastry"],"OBC":["Nadar","Gounder","Thevar","Mudaliar","Pillai"],"SC":["Murugan","Raj","Selvam","Kumar"],"ST":["Naicker","Naik"]},
 "Kannada":{"General":["Hegde","Bhat","Rao","Joshi"],"OBC":["Gowda","Shetty","Patil","Naik"],"SC":["Kumar","Raj","Naik"],"ST":["Nayaka","Naik"]},
 "Telugu":{"General":["Sastry","Sarma","Rao"],"OBC":["Reddy","Naidu","Goud","Chowdary","Yadav"],"SC":["Kumar","Raj"],"ST":["Naik","Nayak"]},
 "Malayalam":{"General":["Nair","Menon","Pillai","Kurup","Warrier"],"OBC":["Nair","Pillai","Panicker"],"SC":["Kumar","Das"]},
 "Punjabi-Hindu":{"General":["Sharma","Verma","Gupta","Khanna","Malhotra","Arora"],"OBC":["Saini","Kamboj"],"SC":["Bharti","Kumar","Mahey","Ram"]},
 "Kashmiri":{"General":["Bhat","Raina","Kaul","Pandita","Dhar"],"OBC":["Bhat","Khar"],"SC":["Kumar","Bhat"]},
}
DIALECT={"Rajasthan":"Marwari-inflected Hindi","Bihar":"Bhojpuri/Magahi-inflected Hindi","Uttar Pradesh":"Awadhi/Bhojpuri-inflected Hindi","Haryana":"Haryanvi Hindi","Madhya Pradesh":"Malwi/Bundeli-inflected Hindi","Jharkhand":"Nagpuri-inflected Hindi","Delhi":"Dilli Hindustani"}
REGION_CROP={"North":["wheat","sugarcane","paddy","mustard"],"Central":["wheat","soybean","gram"],"East":["paddy","jute","potato"],"West":["cotton","groundnut","sugarcane","onion"],"South":["paddy","ragi","sugarcane","cotton"],"Northeast":["paddy","tea"],"Other":["the crop"]}
REGION_CITY={"North":["Delhi","Surat","Ludhiana"],"Central":["Indore","Bhopal"],"East":["Kolkata","Delhi","Mumbai"],"West":["Mumbai","Pune","Surat"],"South":["Bengaluru","Chennai","Hyderabad"],"Northeast":["Guwahati"],"Other":["the city"]}
VALUES_POOL=["security","family duty","tradition","respect/status","getting ahead","faith","fairness","independence","enjoying life","community standing"]
VAL_SHOW={"security":"avoids any risk that could threaten the household","family duty":"puts family obligations before personal wants","tradition":"keeps customs and rituals even at a cost","respect/status":"is keenly aware of standing in the community","getting ahead":"looks for any edge to improve their lot","faith":"turns to religion in decisions and in hardship","fairness":"reacts strongly to being cheated or short-changed","independence":"dislikes depending on anyone","enjoying life":"makes room for small pleasures despite constraints","community standing":"guards the family's reputation"}
MFT_PHRASE={"Care":"protecting kin and avoiding harm","Fairness":"fairness and reciprocity","Loyalty":"loyalty and duty to the group","Authority":"respect for elders and hierarchy","Sanctity":"purity, tradition and the sacred","Liberty":"personal freedom"}
EMO=["calm","content","quietly anxious","hopeful","tired and short-tempered","expectant"]
POL_POOL=["votes mainly on local development and welfare delivery","community/caste-aligned in voting","leans toward whoever delivers welfare schemes","nationalist-leaning","largely apolitical, focused on daily survival","reform- and aspiration-minded, pragmatic"]

def pick(d): k=list(d); return random.choices(k,[d[x] for x in k])[0]
def jn(mu,sd=.12,lo=0.,hi=1.): return max(lo,min(hi,random.gauss(mu,sd)))
def edu_for(z):
    for n,a,b in EDU:
        if a<=z<b: return n
    return "a graduate degree"
def adjectives(h,tier):
    out=[]
    if tier=="skilled": out.append("resourceful")
    if h["C"]>.6: out.append("meticulous" if tier in("skilled","officer") else "disciplined")
    elif h["C"]<.4: out.append("easygoing")
    if h["A"]>.62: out.append("accommodating")
    elif h["A"]<.4: out.append("blunt")
    if h["X"]>.62: out.append("outgoing")
    elif h["X"]<.4: out.append("reserved")
    if h["O"]>.62 and "resourceful" not in out: out.append("curious")
    seen=[]; [seen.append(x) for x in out if x not in seen]
    return (seen or ["cautious"])[:3]
def surname(state,category,religion,gender):
    if religion=="Muslim": return "Begum" if (gender=="F" and random.random()<.3) else random.choice(SURN_REL["Muslim"])
    if religion=="Sikh": return "Kaur" if gender=="F" else random.choice(SURN_REL["Sikh"])
    if religion=="Christian": return random.choice(SURN_REL["Christian"])
    reg=SURN.get(NR.get(state,"Hindi-belt"),{}); pool=reg.get(category) or reg.get("General") or ["Kumar","Das","Naik","Raj"]
    return random.choice(pool)
def dialect_of(state,lang):
    if lang=="Hindi" and state in DIALECT: return DIALECT[state]
    if lang=="Other": return "the local regional dialect"
    return lang
def trade_vocab(o,tier):
    if "tailor" in o: return ["silai (stitching)","kapda (fabric)","naap (measurement)","karigari (craftsmanship)","bouni (first sale)"]
    if o in ("kirana shopkeeper","small trader","shop assistant","street vendor","business owner"): return ["vyapaar (trade)","grahak (customer)","udhaari (credit)","bhav (rate)","bohni (first sale)","mandha (slowdown)"]
    if "farmer" in o or "cultivator" in o or "dairy" in o or "agricultural" in o: return ["fasal (crop)","mandi","beej-khaad (seed & fertiliser)","baarish (rain)","karza (loan)"]
    if o in ("auto/cab driver","delivery rider","tractor/truck driver"): return ["sawari (fare)","meter","kiraya","diesel/CNG ka kharcha"]
    if o in ("mason","construction worker","daily-wage labourer","factory operator"): return ["dihaadi (daily wage)","thekedar (contractor)","naka (labour stand)","maal (material)","karni (trowel)","radda (course of bricks)"]
    if o in ("tuition teacher","schoolteacher"): return ["syllabus","batch","fees","revision","board exam"]
    if o=="nurse": return ["duty","ward","shift","register","dawai (medicine)"]
    if o in ("clerk","government officer","bank employee"): return ["file","register","posting","sanction","procedure"]
    if o in ("ASHA worker","anganwadi worker"): return ["survey","dawai (medicine)","register","aanganwadi","scheme"]
    if tier=="corporate": return ["target","scope","alignment","deadline","follow-up"]
    if o=="homemaker": return ["ghar-grihasti","ration","bachat (savings)","mehmaan (guests)"]
    if o=="college student": return ["semester","attendance","placement","fees","notes"]
    return ["everyday kinship and bazaar words"]
def markers_for(o,tier):
    if "tailor" in o: return ["uses tailoring metaphors ('measure twice, cut once')","precise customer courtesy"]
    if o in ("tuition teacher","schoolteacher"): return ["uses academic/teaching framing","cites students' results and milestones"]
    if o in ("kirana shopkeeper","small trader","shop assistant","street vendor","business owner"): return ["talks in terms of accounts, udhaari and the day's takings","easy customer-courtesy patter"]
    if o=="nurse": return ["clinical, by-procedure phrasing","calm reassurance"]
    if o in ("ASHA worker","anganwadi worker"): return ["health-scheme and survey phrasing","community-mobiliser tone"]
    if "farmer" in o or "cultivator" in o or "dairy" in o or "agricultural" in o: return ["talks in seasons, crops and mandi rates"]
    if o in ("auto/cab driver","delivery rider","tractor/truck driver"): return ["fare, route and meter talk"]
    if o in ("government officer","clerk","bank employee"): return ["precise, by-procedure phrasing"]
    if tier=="corporate": return ["uses framework/business words"]
    return ["uses proverbs and kinship terms","switches to the mother tongue for emotion"]
def compose_memory(age,occ,region,gender):
    young=age<26; farm=("farmer" in occ or "agricultural" in occ or "cultivator" in occ or "dairy" in occ)
    labour=occ in ("daily-wage labourer","mason","construction worker","delivery rider","auto/cab driver","domestic worker","factory operator","street vendor")
    crop=random.choice(REGION_CROP.get(region,["the crop"])); city=random.choice(REGION_CITY.get(region,["the city"]))
    pool=[]
    if young:
        pool+=[("leaving studies early to start earning when the family's income fell","big financial risks"),(f"a first move to {city} for work and feeling like an outsider","outsiders' promises"),("not getting a seat or a job despite trying hard","being overlooked"),("a sudden family expense that meant taking up work young","unplanned expenses")]
        if gender=="F": pool+=[("being pulled out of school for the household","being denied a say")]
    if farm: pool+=[(f"the season the {crop} failed and the loan still had to be repaid","big financial risks and new debt"),(f"a mandi price crash that wiped out a year's effort on {crop}","middlemen and traders"),("selling a piece of land to clear an old debt","losing what little they hold")]
    if labour: pool+=[("the lockdown that stopped all work for weeks","a sudden loss of income"),("a contractor who vanished without paying the wages","middlemen and false promises"),("an injury on the worksite with no cover","unplanned expenses and borrowing")]
    if "tailor" in occ or occ in ("kirana shopkeeper","small trader","tuition teacher"): pool+=[("saving up to buy her first sewing machine / open the shop","losing the customers she has built up"),("a slow season that tested whether the business would survive","an unreliable income"),("the first big order / batch that proved she could do it","squandering a good run")]
    if not young: pool+=[("a medical emergency that drained the savings","unplanned expenses and borrowing"),("an elder whose example set their sense of duty","letting the family down")]
    if occ in ("software professional","business owner","bank employee","doctor","government officer","schoolteacher") or occ=="college student": pool+=[("a job loss or a venture that did not work out","a public career setback"),("cracking a tough exam after years of effort","wasting the opportunity")]
    if not pool: pool=[("a lean year that taught hard lessons about money","big financial risks")]
    return random.choice(pool)
def schedule(occ):
    if "farmer" in occ or "agricultural" in occ or "cultivator" in occ or "dairy" in occ:
        return dict(chronotype="dawn riser, season-driven",wake="04:45",sleep="21:00",peak_load="early-morning fieldwork; forced mid-day rest in peak heat (12:00–15:00)",peak_exhaustion="late-morning heat, and the sowing/harvest crunch",availability="reachable at midday rest and after dusk; unreachable at dawn fieldwork",habit_loop="Dawn fieldwork → midday heat rest & meal → evening livestock/repairs → early sleep; swings hard between monsoon/harvest and lean months.")
    if occ=="street vendor":
        return dict(chronotype="late-morning to night",wake="07:30",sleep="23:30",peak_load="evening market rush 17:00–21:00 — peak transactional stress (NOT watching TV then)",peak_exhaustion="after the night rush, ~22:00",availability="free late morning; do NOT disturb during the evening rush",habit_loop="Late-morning sourcing & setup → slow afternoon → intense 5–9 PM rush → late wind-down.")
    if occ in ("mason","construction worker","daily-wage labourer"):
        return dict(chronotype="early, shift-bound",wake="06:00",sleep="22:00",peak_load="continuous physical exertion on-site 08:00–17:00",peak_exhaustion="immediately post-shift (17:00–19:00): high cortisol, depleted, short-tempered",availability="reachable at the naka before 8 and after 6; not during the shift",habit_loop="At the naka/site by 8 → hard labour till 5 → post-shift exhaustion, tea/tobacco, food → early sleep.")
    if occ in ("auto/cab driver","delivery rider","tractor/truck driver"):
        return dict(chronotype="long, irregular",wake="06:30",sleep="23:30",peak_load="commute peaks (8–11, 17–21) and meal-time orders; fatigue compounds through the day",peak_exhaustion="late afternoon if the daily target is unmet (cash stress + tiredness)",availability="between trips; least responsive in peak hours",habit_loop="Early start chasing the daily target → peak-hour grind → late-afternoon stress if short → night wind-down.")
    if occ=="domestic worker":
        return dict(chronotype="early, multi-shift",wake="05:30",sleep="22:00",peak_load="back-to-back houses, morning and evening",peak_exhaustion="midday between shifts, and late evening",availability="short midday break and after 8 PM",habit_loop="Own-home chores → morning houses → midday own home → evening houses → late rest.")
    if "tailor" in occ:
        return dict(chronotype="structured day-rhythm",wake="05:30",sleep="22:30",peak_load="09:00–12:00 intense pattern-drafting; afternoon alterations and fittings",peak_exhaustion="late afternoon (16:00–18:00) from eye-strain and sitting",availability="best reached in the afternoon rest window, 2–4 PM",habit_loop="Morning house tasks → open the home shop by 9 → stitch & assemble orders → evening meal prep → late design sketching.")
    if occ=="tuition teacher":
        return dict(chronotype="afternoon-evening peak",wake="06:30",sleep="23:00",peak_load="after-school batches 16:00–20:00; morning prep and corrections",peak_exhaustion="after the last evening batch",availability="late morning and early afternoon",habit_loop="Morning prep/house → midday free → after-school batches 4–8 → evening correction & next-day prep.")
    if occ=="anganwadi worker":
        return dict(chronotype="morning-centre",wake="06:00",sleep="22:00",peak_load="centre work and home visits 09:00–13:00",peak_exhaustion="midday after visits in the heat",availability="afternoons after the centre closes",habit_loop="Home chores → anganwadi centre & surveys → midday close → afternoon home & records.")
    if occ in ("kirana shopkeeper","small trader","shop assistant","business owner"):
        return dict(chronotype="shop hours",wake="07:00",sleep="22:30",peak_load="morning and evening footfall; festival surges",peak_exhaustion="after evening closing",availability="lean afternoon hours; busy at open and close",habit_loop="Open ~9 → morning customers → afternoon lull (accounts, udhaari) → evening rush → close ~9.")
    if occ=="homemaker":
        return dict(chronotype="continuous, no off-switch",wake="05:00",sleep="22:00",peak_load="dawn cooking & childcare and the evening meal; caregiving all day",peak_exhaustion="late morning after the first round, and night",availability="a short midday window; rarely truly off",habit_loop="Pre-dawn chores → school/work send-off → housework & caregiving → evening cooking → late rest.")
    if occ in ("nurse","factory operator"):
        return dict(chronotype="rotating shifts",wake="varies by shift",sleep="varies by shift",peak_load="whatever the current shift demands; circadian disruption from rotation",peak_exhaustion="end of a long or night shift",availability="depends on the shift roster",habit_loop="Shift work → recovery sleep → family time in the gaps → repeat on rotation.")
    if occ in CORP or occ in ("government officer","schoolteacher","clerk"):
        return dict(chronotype="early-to-mid-morning peak",wake="06:30",sleep="23:00",peak_load="08:00–11:30 deep-focus block; meetings/duty drain the afternoon",peak_exhaustion="late-afternoon decision-fatigue",availability="calendar/duty-bound; best reached early morning",habit_loop="Morning routine → high-focus block → meetings/duty → evening family decompress → late reading.")
    if occ=="college student":
        return dict(chronotype="night-leaning",wake="07:30",sleep="00:30",peak_load="classes by day; study and scroll late",peak_exhaustion="late night",availability="evenings and between classes",habit_loop="Classes → friends/part-time → late-night study and phone.")
    return dict(chronotype="day-rhythm",wake="06:30",sleep="22:30",peak_load="standard work hours",peak_exhaustion="end of day",availability="evenings",habit_loop="Work by day → evening with family on phone/TV → night rest.")

def somatic_stressors(o):
    if o in ("mason","construction worker","daily-wage labourer","agricultural labourer","small farmer","owner-cultivator","dairy/livestock worker","tractor/truck driver"):
        return ["lower-back strain from years of lifting/bending","knee & joint pain","heat exhaustion and dehydration"]
    if "tailor" in o: return ["chronic eye strain","neck & shoulder strain from sitting bent over"]
    if o in ("auto/cab driver","delivery rider"): return ["lower-back pain / sciatica from long sitting","eye strain and fatigue"]
    if o=="domestic worker": return ["wrist & knee strain","persistent fatigue"]
    if o=="street vendor": return ["leg & foot fatigue from standing all day","sun/heat exposure"]
    if o in ("nurse","factory operator"): return ["circadian disruption from rotating shifts","standing fatigue"]
    if o=="homemaker": return ["chronic fatigue","back strain from constant chores"]
    if o in CORP or o in ("government officer","schoolteacher","clerk","bank employee","tuition teacher","college student"):
        return ["sedentary back/neck pain","screen eye strain","sleep debt"]
    return ["general fatigue","back strain"]
EXH_WINDOW={"mason":"17:00–19:00","construction worker":"17:00–19:00","daily-wage labourer":"17:00–19:00",
 "street vendor":"21:00–22:30","auto/cab driver":"16:00–19:00","delivery rider":"16:00–19:00",
 "domestic worker":"19:00–21:00","homemaker":"12:00–14:00 and after 21:00"}
VALUE_GAP={"independence":("a digital or official transaction under time pressure","hands the phone or the paperwork to a shopkeeper or male relative to finish it — quietly violating her prized self-reliance"),
 "security":("a festival, a wedding or a child's insistent demand","overspends well beyond the budget and reframes it as duty rather than waste"),
 "family duty":("their own exhaustion or quiet resentment","cuts corners on an obligation, then over-compensates out of guilt"),
 "tradition":("a clearly better economic opportunity","quietly bends the custom when real money is at stake, while still defending it in public"),
 "faith":("desperation, illness or a cash emergency","turns to a moneylender or an unproven fix their stated principles disapprove of"),
 "fairness":("having been cheated first, or sheer survival","fudges a measurement or a price and calls it 'evening the score'"),
 "respect/status":("a sudden cash crunch","secretly takes a 'beneath them' job or a hidden loan they would publicly disdain"),
 "getting ahead":("fear after a setback","clings to the safe known option and rationalises the missed chance"),
 "community standing":("private temptation","does the thing they would condemn in others, taking care that no one sees"),
 "enjoying life":("guilt or scarcity","denies themselves, then resents those who don't")}
def build_persona():
    st=pick({k:v["w"] for k,v in STATES.items()}); sd=STATES[st]; region=sd["region"]
    rural=random.random()<sd["rural"]
    place=("a village" if rural else random.choice(["a small town","a Tier-2 city","a metro"]))
    lang=pick(sd["langs"]); religion=pick(sd.get("rel",REL_DEFAULT))
    category="General" if religion in("Christian","Jain") and random.random()<.5 else pick(CATEGORY)
    band=pick(AGE_BANDS); lo,hi=BAND_RANGE[band]; age=random.randint(lo,hi)
    gender=random.choices(["M","F","Other"],[.51,.485,.005])[0]
    z=jn(.5+(.12 if not rural else -.08)+(.06 if category=="General" else (-.06 if category in("SC","ST") else 0)),.2)
    education=edu_for(z); nccs=NCCS_BY_SES[min(14,max(0,int(z*15)))]; cls=CLASS_DESC[nccs]
    married=(band!="18-24") or random.random()<.3   # decided before occupation (homemaker requires it)
    if band=="18-24" and z>.6 and random.random()<.35: occ="college student"
    elif gender=="F" and married and random.random()<.55 and z<.7: occ="homemaker"
    elif z>=.72: occ=random.choice(OCC_HIGH)
    elif rural: occ=random.choice(OCC_RURAL_LOW if z<.4 else OCC_RURAL_MID)
    else: occ=random.choice(OCC_URBAN_LOW if z<.4 else OCC_URBAN_MID)
    # ---- EDUCATION-OCCUPATION GATE (no graduate masons; no illiterate doctors) ----
    if education in GRAD and occ_tier(occ)=="manual" and occ!="homemaker":
        occ=random.choice(EDU_PIVOT_RURAL if rural else EDU_PIVOT_URBAN)
    if occ_tier(occ)=="corporate" and education in LOWED:
        education="a graduate degree"
    if occ in ("schoolteacher","tuition teacher","nurse","clerk","bank employee") and education in LOWED:
        education="Class 12"
    tier=occ_tier(occ); psych=TIER_PSYCH[tier]
    children=0 if not married else random.choices([0,1,2,3,4],[.15,.25,.3,.2,.1])[0]
    household="joint family" if (rural and random.random()<.6) else "nuclear family"
    smartphone=random.random()<(.55+z*.4)
    h={k:jn(m) for k,m in {"H":.6,"E":.58,"X":.5,"A":.55,"C":.6,"O":.42+z*.2}.items()}
    religiosity=jn(.72 if region!="South" else .66,.15); scarcity=jn(max(.05,.9-z*.85),.08)
    lo_l,hi_l=LAM[nccs]; loss_av=round(random.uniform(lo_l,hi_l),2)
    reflective=jn(.25+z*.5,.1); precision=jn(.62,.14)
    interdependence=jn(.72,.12); power_distance=jn(.74,.12); locus_ext=jn(.5+religiosity*.2,.12)
    lajja_high=interdependence>.6 or household=="joint family" or (rural and category in("SC","ST","OBC"))
    conform=power_distance>.6 or lajja_high or household=="joint family"
    mft={"Care":jn(.7),"Fairness":jn(.55),"Loyalty":jn(.72),"Authority":jn(.70),"Sanctity":jn(.68),"Liberty":jn(.40+z*.2)}
    dom=max(mft,key=mft.get); misinfo=jn(max(.1,.62-z*.3),.12)
    fasting=(religion=="Muslim" and random.random()<.12) or (religion=="Hindu" and gender=="F" and random.random()<.12)
    emo=random.choice(EMO); want_status=jn(.4+z*.3,.18); tobacco=gender=="M" and tier=="manual" and random.random()<.5
    mem,aversion=compose_memory(age,occ,region,gender)
    values=random.sample(VALUES_POOL,3)
    if religiosity>.7 and "faith" not in values: values[2]="faith"
    g="m" if gender=="M" else "f"; relkey=religion if religion in("Hindu","Muslim","Sikh","Christian") else "default"
    given=random.choice(NAMES.get(f"{relkey}_{g}",NAMES[f"default_{g}"])); name=f"{given} {surname(st,category,religion,gender)}"
    dialect=dialect_of(st,lang); tvocab=trade_vocab(occ,tier)
    lang_disp=lang if lang!="Other" else "a regional language"; speaks=f"{lang}-speaking " if lang!="Other" else ""
    portrait=(f"{age}-year-old {speaks}{occ} in {place} in {st}; {'married' if married else 'unmarried'}, {education}, {cls} (NCCS {nccs}). {', '.join(adjectives(h,tier)).capitalize()}.")
    sch=schedule(occ); educated=education in GRAD
    if occ=="homemaker" and children==0: sch=dict(sch); sch["peak_load"]=sch["peak_load"].replace("& childcare","& housework")
    drivers=random.sample(psych["drivers"],2); fears=random.sample(psych["fears"],2)
    if children==0:   # no child references for the childless
        rd=["their own advancement","supporting their parents","building a secure base","saving for the future"]
        rf=["staying out of debt","an unstable income","falling ill with no safety net","being stuck with no progress"]
        drivers=[d if "child" not in d.lower() else random.choice(rd) for d in drivers]
        fears=[f if "child" not in f.lower() else random.choice(rf) for f in fears]
        if drivers[0]==drivers[1]: drivers[1]=random.choice([x for x in rd if x!=drivers[0]])
        if fears[0]==fears[1]: fears[1]=random.choice([x for x in rf if x!=fears[0]])
    pillars={
     "1_perception_and_belief":(("Holds core beliefs firmly and is slow to change them" if precision>.6 else "Fairly open to changing their mind with evidence")+("; on a phone, likely to believe and forward WhatsApp claims that fit the community's view" if smartphone and misinfo>.5 else "; reasonably sceptical of forwarded claims" if smartphone else "; gets most news by word of mouth")+"."),
     "2_wanting_vs_liking":(("Craves a better setup / higher status more than it would satisfy" if want_status>.5 else "Not very driven by status or upgrades")+("; a habitual tobacco user who wants it more than enjoys it" if tobacco else "")+f"; gut-wary of {aversion}."),
     "3_thinking_mode":(("Mostly fast, intuitive decisions, deliberating only on big unfamiliar choices" if reflective>.5 else "Mostly snap, gut-feel decisions, rarely second-guessing")+"; falls back on habit when tired or short of cash."),
     "4_emotional_state":(f"Currently {emo}"+(", and fasting today so more irritable" if fasting else "")+("; highly sensitive to family honour and 'what people will say' (lajja)" if lajja_high else "; not very swayed by social judgement")+"."),
     "5_self_story_and_memory":(f"Sees their life as shaped by {mem}; recalls the past selectively and tends to justify choices after making them."),
     "6_moral_and_social":(f"Moral calls come as gut reactions weighted toward {MFT_PHRASE[dom]}"+("; conforms to the group and defers to elders" if conform else "; fairly independent of group pressure")+"."),
     "7_money_and_risk":(f"Feels losses about {loss_av}x as hard as equal gains (loss looms larger as the capital base shrinks); "+("short-term and present-focused under cash pressure" if scarcity>.5 else "patient when cash is steady")+"; keeps money in separate mental pots, with any goal/savings fund kept untouched."),
     "8_cultural_lens":("Defines self through family and community more than as an individual; explains others' behaviour by circumstances rather than character; thinks holistically; "+("and sees much of life as shaped by fate or God's will" if locus_ext>.55 else "with a strong sense of personal effort")+"."),
    }
    tone={"corporate":"structured and precise, business-like","officer":"measured, procedural, courteous","skilled":"measured, courteous, detail-oriented","manual":"plain, proverb-led, story-style"}[tier]
    markers=markers_for(occ,tier)
    voice={"languages":[lang_disp]+(["Hindi"] if lang not in("Hindi","Other") and random.random()<.6 else [])+(["functional English"] if educated and random.random()<.7 else []),
        "dialect":dialect,"register":"formal-deferential" if power_distance>.7 else "casual","honorific":"aap (respectful)" if power_distance>.6 else "tum (familiar)",
        "tone":tone,"trade_vocabulary":tvocab,"markers":markers,"emoji_use":"low" if tier in("corporate","officer") else ("emoji-heavy on WhatsApp" if smartphone else "rarely texts")}
    # cognitive architecture
    low_lit=education in LOWED
    daily_income=occ in ("daily-wage labourer","agricultural labourer","street vendor","delivery rider","auto/cab driver","mason","construction worker","domestic worker","kirana shopkeeper","tractor/truck driver")
    dom_lang=max(sd["langs"],key=sd["langs"].get); ling_minority=lang!="Other" and lang!=dom_lang
    trig=[]
    if low_lit or not smartphone: trig.append("Navigating government paperwork or a banking/online process alone — triggers dependence on a middleman/shopkeeper, or outright avoidance.")
    if ling_minority: trig.append(f"Interpersonal conflict with local {dom_lang} speakers where they cannot express nuance in {lang} — triggers withdrawal or deference.")
    elif tier=="manual" and random.random()<.5: trig.append("A dispute or official conversation in officialese they are not fluent in — triggers withdrawal or deference.")
    if scarcity>.5: trig.append("An unexpected expense while cash is already tight — triggers panic, short-term borrowing, or cutting essentials.")
    if tier=="corporate": trig+=["Ambiguous goals with no clear framework — triggers analysis-paralysis and over-research.","Real-time emotional confrontation — triggers avoidance; prefers async, data-backed resolution."]
    if tier in("skilled","officer"): trig.append("Unreliable equipment/process or a late payment that disrupts the plan — triggers tense, methodical fixing.")
    if gender=="F" and (rural or occ=="homemaker"): trig.append("Dealing with a bank or official without the husband present or the shared phone — defers or avoids.")
    trig+=["A high-pressure sales pitch under time pressure — triggers shutdown and 'I'll ask my family or group first'.","A decision with no obvious right answer — triggers deferral to whoever they trust most."]
    trig=random.sample(trig,2)
    if ling_minority: ling=(f"Survival multilingual: broken, functional {dom_lang} for transactions (commuters, police, vendors, union); falls back to {lang}"+(" and respectful Hindi" if lang!="Hindi" else "")+" with trusted peers and family. Constant low-grade language friction and the odd slight quietly raise daily stress.")
    else: ling=(f"Comfortable in {dialect} for almost everything locally"+("; functional Hindi/English for official or city dealings." if (educated or not rural) else "; limited ability outside it."))
    meter=("the daily earnings target" if daily_income else "the monthly salary and work targets" if tier in("corporate","officer") else "the season's harvest income" if ("farmer" in occ or "cultivator" in occ) else "the month's household money" if occ=="homemaker" else "the business takings" if tier=="skilled" else "the monthly income")
    flush=f"When {meter} is comfortably met: more relaxed and generous, willing to chat, open to trying new things, follows community WhatsApp trends."
    scarce=(f"When behind on {meter}: tunnel vision and severe time-discounting (small cash now over a larger sum later), "+("curt and abrupt even in the respectful register" if power_distance>.6 else "blunt and impatient")+", defers big decisions and cuts every non-essential.")
    if daily_income: window="Risk tolerance falls toward zero by late afternoon (~4–6 PM) on days the daily target is unmet — the peak window for quick-cash scams and predatory lending (acute scarcity narrows judgement, ~13 IQ-point effect)."
    elif tier in("corporate","officer"): window="Most exposed in the days before payday and at quarter/target/appraisal deadlines."
    elif "farmer" in occ or "cultivator" in occ: window="Most exposed in the lean pre-harvest months when cash is thin and loans tempt."
    elif tier=="skilled": window="Most exposed during a slow season or when a large payment is overdue."
    else: window="Most exposed in the last week before the month's money comes in."
    if tier=="corporate": conflict="Deliberation can tip into analysis-paralysis; copes by over-documenting and seeking data validation after the fact."
    elif tier in("skilled","officer"): conflict="Deliberates carefully over spending and keeps business/work money strictly separate from household cash; second-guesses big-ticket buys and seeks reassurance."
    elif loss_av>2.0: conflict="Snap, gut-feel choices collide with a deep fear of debt, producing real post-purchase anxiety (buyer's remorse); copes by aggressively justifying a spend to the family to protect their pride rather than admit a mistake."
    else: conflict="Mostly at peace with their choices, but second-guesses big-ticket spends and seeks reassurance from family."
    deference=("When a choice could threaten the family's standing or honour, freezes and will NOT commit until a trusted elder, spouse or the kinship/SHG network is consulted." if lajja_high else "Weighs others' views but can decide alone on personal matters.")
    if tier=="corporate" and want_status>.5: nvl="Frame offers as a concrete edge or upgrade with clear numbers and a bounded downside; aggressive-growth framing works only if the risk is capped."
    elif tier=="skilled": nvl="Frame as protecting and steadily growing their own income/work, vetted by "+("the women's savings group (SHG)" if gender=="F" else "trusted peers or the local trade association")+" — never a risky leap."
    elif loss_av>2.3 or "security" in values or "family duty" in values: nvl="Any offer must be framed as shielding or protecting what the family already has — never as an aggressive growth play — and ideally vetted by the group or an elder first."
    elif religiosity>.7: nvl="Framing that aligns with family duty and the children's future lands; pure personal gain does not, and a trusted referral seals it."
    else: nvl="Must be framed as reducing risk and helping the family, and confirmed by someone they trust before they will agree."
    cog={"cognitive_load_triggers":trig,"linguistic_survival_profile":ling,"scarcity_behavior_shift":{"condition_flush":flush,"condition_scarce":scarce,"high_risk_window":window},"system1_goal_conflict":conflict,"social_deference_loop":deference,"narrative_validation_loop":nvl}
    can_jargon=tier in("corporate","officer")
    guardrails={"always":["Answer in their own dialect/register and from their lived situation","Weigh family, cash constraints and what the community thinks before deciding",("Freeze and consult an elder/peer before any choice that touches family honour" if lajja_high else "Reason from their own experience first")],
        "never":["Use corporate/tech jargon or English frameworks beyond their background" if not can_jargon else "Pretend domain expertise they don't have","Give a confident, individualistic, Western-framed answer that ignores context","Claim knowledge or numbers a person in their situation would not have"]}
    sd2,trg,cop=psych["stress"]
    if occ=="college student": career=["schooling","currently studying"]
    elif "farmer" in occ or "cultivator" in occ or "agricultural" in occ: career=["worked family land from a young age",f"now {occ}"]
    elif tier in("skilled","officer"): career=["completed local studies",f"built up work as a {occ}"]
    elif tier=="corporate": career=[f"trained/started in the field","now established as a "+occ]
    else: career=["odd jobs as a teenager",f"now works as a {occ}"]
    # ---- TIER 3: contextual dynamics (somatic / macro / social capital / temporal) ----
    physical=somatic_stressors(occ)
    if age>=50 and physical: physical=[f"25+ years of work — {physical[0]}"]+physical[1:]
    exh=EXH_WINDOW.get(occ) or ("11:00–15:00 (peak heat)" if ("farmer" in occ or "cultivator" in occ or "agricultural" in occ)
        else "16:00–18:00 (eye strain)" if "tailor" in occ else "16:00–18:00 (decision fatigue)" if tier in("corporate","officer") else "the end of the working day")
    manual_phys=tier=="manual" or ("farmer" in occ or "cultivator" in occ)
    decay=("Exponential — pain and fatigue compound through the shift; past mid-afternoon patience drops sharply and processing collapses to blunt System-1 survival choices." if (manual_phys and age>=40)
           else "Linear — decision fatigue builds across the day, with a clear late-day drop in patience.")
    infl=round(min(.95,max(.15,.95-z*.7+random.uniform(-.05,.05))),2)
    if "farmer" in occ or "cultivator" in occ or "agricultural" in occ or "dairy" in occ: eco=["monsoon timing / rainfall","mandi crop prices","seed & fertiliser cost"]
    elif occ in ("kirana shopkeeper","small trader","shop assistant","street vendor","business owner"): eco=["wholesale commodity prices (edible oil, pulses, vegetables)","fuel/transport cost","festival demand swings"]
    elif occ in ("auto/cab driver","delivery rider","tractor/truck driver"): eco=["fuel / CNG prices","platform commission & demand"]
    elif tier=="manual": eco=["construction / work-availability slowdown","seasonal demand for labour"]
    elif "tailor" in occ: eco=["fabric & thread prices","wedding/festival-season demand","power cuts"]
    elif tier in("corporate","officer"): eco=["job market / hiring freezes","interest & EMI rates"]
    else: eco=["local price levels","seasonal demand"]
    if region in ("North","Central"): eco.append("summer heat & power cuts")
    stressed=round(min(3.6,loss_av*(1+.55*infl)),2)
    gk=(["the SHG / Bachat Gat (savings-group) leader","the ASHA / anganwadi worker","a literate elder or mother-in-law"] if (rural and gender=="F")
        else ["a village elder / panchayat member","a trusted shopkeeper or input-dealer","an educated relative"] if rural
        else ["a knowledgeable peer or colleague","their spouse","an online-savvy friend"] if tier in("corporate","officer")
        else ["a trusted relative","the local kirana owner","a senior at work"])
    if religion=="Muslim": gk=gk[:2]+["a mosque / community-committee elder"]
    elif religiosity>.72: gk=gk[:2]+["a temple / devotional-committee elder"]
    dfilt=("Skeptical-but-self-verifying: checks unfamiliar finance/legal claims against documents or a trusted peer before acting." if educated
        else "Verify-with-kinship: any unsolicited call, SMS or app notification about money or law is treated as a threat and ignored until checked face-to-face with a trusted node.")
    if age<30: thm={"classification":"Expansive (exploratory / youth)","time_discount_bias":"Hyperbolic — prefers immediate, exploratory gains and peer alignment","novelty_resistance_index":round(min(1,max(.05,.35-h['O']*.2+(0 if educated else .1))),2)}
    elif age>=58: thm={"classification":"Constricted (legacy-protective / elder)","time_discount_bias":"Intergenerational — preserves assets and health for heirs and emotional equilibrium over exploratory gain","novelty_resistance_index":round(min(1,.7+(.1 if not educated else 0)+(.05 if rural else 0)),2)}
    else: thm={"classification":"Provisioning (family-focused, mid-horizon)","time_discount_bias":"Discounts toward the children's near-term needs; cautious on far-future bets","novelty_resistance_index":round(min(1,max(.05,.5-h['O']*.2)),2)}
    cdyn={"somatic_homeostasis":{"chronic_physical_stressors":physical,"circadian_depletion_rate":decay,
            "peak_somatic_exhaustion_window":exh+" — physical discomfort shifts processing from System 2 to blunt System 1; rejects by default to avoid cognitive strain."},
        "macro_environmental_sensitivity":{"inflation_elasticity_coefficient":infl,"ecological_dependency_vectors":eco,
            "macro_stress_modifier":f"Under a commodity-price spike or income shock, effective loss aversion balloons from {loss_av}x toward ~{stressed}x as the survival safety-margin nears zero."},
        "social_capital_trust_network":{"institutional_gatekeepers":gk,"external_channel_distrust_filter":dfilt},
        "temporal_horizon_mode":thm}
    # ---- TIER 4: psychological paradoxes (the irrational soul) ----
    vg=VALUE_GAP.get(values[0],VALUE_GAP["security"])
    if z<.6:
        desire=random.choice(["an upscale city flat / gated apartment","an expensive car","an English-medium elite school for the kids","branded / foreign goods","a lavish urban lifestyle"])
        reject=random.choice(["'City people have no peace — adulterated food, no sleep; our village air and food are pure.'","'Too much money only corrupts the children and the family values.'","'Those flats are just cages stacked on cages — no community, no real life.'","'Show-off spending invites the evil eye; simple living keeps us safe.'"])
    else:
        desire="the lifestyle of the genuinely wealthy / elite circles"; reject="'That world is all stress and no values — I'd rather have balance and my own people.'"
    if locus_ext>.6 or religiosity>.72: drw="Blames fate / God's will and 'the weather or market turned' — never personal error; a money loss is pinned on a merchant's or middleman's bad intent."
    elif tier in("corporate","officer"): drw="Reframes a bad call as a calculated risk that 'taught a lesson'; rarely admits a clear mistake, points to incomplete information at the time."
    else: drw="Shifts blame to an outsider (the seller, an official, bad luck) or reframes the loss as a necessary sacrifice for the family; aggressively defends the decision to protect pride."
    para={"value_action_gaps":[{"stated_value":values[0],"trigger_condition":vg[0],"fallback_behavior":vg[1]}],
        "adaptive_preference_shields":[{"unachievable_desire":desire,"rationalized_rejection":reject}],
        "dissonance_rewriting_strategy":drw}
    # ---- formal decision-model parameters (see PERSONA_MATHEMATICAL_MODEL.md / persona_math.py) ----
    dmodel={"capital_index":CAPIDX.get(nccs,0.3),
        "prospect":{"alpha":0.88,"loss_aversion_lambda":loss_av,"prob_weight_gamma":0.65,"reference_income_inr":REF_INC.get(nccs,9000)},
        "time":{"present_bias_beta":round(max(.25,.95-.6*scarcity),3),"long_run_delta":0.97},
        "scarcity":{"state":round(scarcity,3),"iq_bandwidth_drop":round(-13*scarcity,1)},
        "somatic":{"shift_start":8.0,"peak_exhaustion_hour":peak_exh_hour(occ),"depletion_rate":0.08 if tier=="manual" else 0.04,"convex_aging":tier=="manual" and age>=45},
        "dual_process":{"reflective_disposition":round(reflective,3)},
        "ddm":{"boundary_a0":1.0,"drift_gain":1.2,"noise":0.6},
        "belief":{"prior_precision":round(precision,3)},
        "novelty_resistance_index":round(max(0.0,min(1.0,0.35+(0.45 if age>=58 else 0)-0.2*h["O"]-(0.1 if educated else 0)+(0.05 if rural else 0))),3),
        "temporal_horizon":"Expansive" if age<30 else ("Constricted" if age>=58 else "Provisioning")}
    return {
     "id":str(uuid.uuid4()),"name":name,
     "identity":{"age":age,"gender":gender,"state":st,"region":region,"setting":"rural" if rural else "urban","language":lang,"dialect":dialect,"religion":religion,"community":category,"occupation":occ,"occupation_tier":tier,"education":education,"class_nccs":nccs,"income_band":cls},
     "portrait":portrait,
     "background":{"marital_status":"married" if married else "unmarried","children":children,"household":household,
        "career_path":career,"anchoring_memory":mem},
     "dominant_traits":adjectives(h,tier),
     "quirks":random.sample(psych["quirks"],min(3,len(psych["quirks"]))),
     "core_values":[{"rank":i+1,"value":v,"shows_up_as":VAL_SHOW[v]} for i,v in enumerate(values)],
     "motivations":{"explicit_drivers":drivers,"hidden_fears":fears},
     "stress_and_coping":{"primary_driver":sd2,"stress_trigger":trg,"coping":cop},
     "political_leaning":random.choice(POL_POOL)+" (coarse, sensitive — simulation only, not validated)",
     "daily_rhythm":sch,"voice":voice,"eight_pillars":pillars,"decision_model":dmodel,"cognitive_architecture":cog,
     "contextual_dynamics":cdyn,"psychological_paradoxes":para,"agent_guardrails":guardrails,
     "confidence":"interim (approximate priors, pre-validation; scaffold, not a validated predictor)",
    }

def gen_batch(n,seen):
    out=[]
    while len(out)<n:
        p=build_persona()
        if p["id"] in seen: continue
        seen.add(p["id"]); out.append(p)
    return out
def write_shard(recs,outdir,idx,mode="a"):
    os.makedirs(outdir,exist_ok=True)
    with open(os.path.join(outdir,f"personas_{idx:05d}.jsonl"),mode,encoding="utf-8") as f:
        for r in recs: f.write(json.dumps(r,ensure_ascii=False)+"\n")
def manifest(outdir,total,rate):
    with open(os.path.join(outdir,"_manifest.json"),"w",encoding="utf-8") as f:
        json.dump({"updated_utc":datetime.now(timezone.utc).isoformat(timespec="seconds"),"total_personas":total,"generator":"persona_factory v0.8 (occupation-tier + education gate)","last_rate_per_min":round(rate,1)},f,indent=2)
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",default="personas"); ap.add_argument("--count",type=int,default=0); ap.add_argument("--daemon",action="store_true")
    ap.add_argument("--rate",type=int,default=100); ap.add_argument("--interval",type=int,default=600); ap.add_argument("--shard-size",type=int,default=5000)
    ap.add_argument("--seed",type=int,default=None); ap.add_argument("--max-cycles",type=int,default=0); a=ap.parse_args()
    if a.seed is not None: random.seed(a.seed)
    seen=set(); stop={"v":False}; signal.signal(signal.SIGINT,lambda *x:stop.update(v=True))
    if a.count:
        t0=time.time(); total=0; idx=0
        while total<a.count:
            n=min(a.shard_size,a.count-total); recs=gen_batch(n,seen); write_shard(recs,a.out,idx,mode="w"); total+=n; idx+=1
            if total%20000==0: print(f"  ...{total} written")
        dt=time.time()-t0; manifest(a.out,a.count,a.count/max(dt,1e-6)*60)
        print(json.dumps({"mode":"burst","generated":a.count,"seconds":round(dt,2),"rate_per_min":round(a.count/max(dt,1e-6)*60),"shards":idx},indent=2)); return
    if a.daemon:
        print(f"[daemon] {a.rate} every {a.interval}s. Ctrl-C to stop."); total=0;idx=0;sc=0;cyc=0
        while not stop["v"]:
            cyc+=1;t0=time.time();recs=gen_batch(a.rate,seen);write_shard(recs,a.out,idx);sc+=len(recs);total+=len(recs)
            if sc>=a.shard_size: idx+=1;sc=0
            manifest(a.out,total,a.rate/max(time.time()-t0,1e-6)*60)
            print(f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] cycle {cyc}: +{len(recs)} total={total}")
            if a.max_cycles and cyc>=a.max_cycles: break
            for _ in range(int(max(0,a.interval-(time.time()-t0)))):
                if stop["v"]: break
                time.sleep(1)
        return
    ap.print_help()
if __name__=="__main__": main()
