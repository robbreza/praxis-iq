"""Compare the user's regional Focused Target List against house-CRM firms. Flags which list
accounts are NOT already present. Fuzzy match (normalized, legal-suffix-stripped, token-subset)
with the matched DB firm shown so false positives are visible."""
import re
from core.security import load_environment; load_environment()
from core import db

LIST = {
"NY": ["1798 Global Partners","Abdiel Capital","ACT II Partners","Alkeon","Alliance","Alpine","Altai Capital","Aptigon (Citadel)","AQR Capital","Ardsley","Ark","ART Advisor","Artemis","Axiom","BAM","Baron","Bascom Hill","BlackRock","BlueMar Capital","Boothbay Funds","Brahman","Brompton Cross","Cadian","Camelot","Capital Management","Catalyst","Catapult Partners","Caxton","Chilton","Cipher Capital","Citadel","Clearbridge","Coatue","Cobalt","Colonial Fund","Columbus Circle","Cooper Creek","Cortina","CR Intrinsic","Cramer Rosenthal","CREF","Cubist","D.E. Shaw","Dalton Greiner","Dane Capital","Deutsche Bank Trust","Edgewood","Emancipation","Empire","Engineers Gate","Epoch","Espalier","Federated Global","First York","Fred Alger","G2 Investment Partners","George Weiss","Gilder Gagnon","GJK Capital","Glenview","Goldman Capital","Goldman Sachs","Greenhouse Funds","Harvest","Highbridge","Hudson Bay","Hutchin Hill Capital","ING Investments","Inle Capital","Invicta","J Goldman","Jacobs Levy","Jane Street Capital","JAT Capital","Jennison","JP Morgan","Kacela Capital","Karsch","Kingdom Ridge","Kingdon Capital","Kohlberg Kravis Roberts","Laurion Capital","Levin","Long Oar","Lord Abbett","Madera Tech Partners","Manatuck","MapleLane","Marshall Wace","Millennium","Moore Capital","Morgan Stanley","Mutual of America","Neuberger","New Jersey Division of Investment","Newbrook","Nishkama","NL Capital","Nokota","NY Mellon","NY State Common Retirement","Omega","Open Field","Oppenheimer","Owl Creek","Palisade","Paloma Partners","PAW","PDT Partners","Perella Weinberg","Perry Partners","Phoenix","Pier Capital","Pioneer Path","Plural Investments","Porter Orlin","Principled","QS Investors","Renaissance Technologies","Ridgecrest","Royce","RS Investments","S Squared","Samjo","Sankofa Capital","Schottenfeld","Searock","Shannon River Fund Management","Schroder","Sigma","Soros","Spark Investment","Springbok","Squarepoint","SRS Investment","STG Capital","SunAmerica","Sursum","Surveyor","Teton","The Bank of NY Mellon","Thrax Management","Tiger","Time Square","Tower Research","Trellus","Tremblant","Trexquant","TriOaks","Tudor","Two Sigma","UBS Asset Management","UBS O'Connor","Unterberg","US Trust","Victory Capital","Voya","Weiss Asset","Welch Capital","Wynnefield Capital","York Capital","Ziff Asset"],
"Mid West": ["1492 Management","Acrospire","Acuta","Advisory Research","Alyeska","American Century","AMP","Anchor Bolt","Ancora","Arbor (foundry)","Ariel Capital","Artisan","Aspire Capital","Asymmetry","Baird Asset","Blackthorn","Blue Rock","Brazos (maverick)","Calamos","Cambiar","Camelot","Carlson","Carnegie Investment","CastleArk","Channing Capital","Chicago Equity Partners","Chickasaw","Citadel","Cloverdale","Columbia Wanger","Continental","Copia","CopperLeaf","Cortina","Courage Capital","Crystal Rock","Denver Investments","Dimensional","Driehaus","Eagle Global","Employees Retirement","Fortaleza","Fosun","GEM Realty Value","Gerald Ray & Associates","Harris Associates","Harrison Street","HBK Investments","Heartland","Heitman","Highland Capital","Highside","Invesco","IronBridge","Janus","Janus Henderson","JetStream","Kaizen","Kennedy Capital","Magnetar","Marsico","Nationwide","Neuberger Berman","Next Century","Nokomis","North Lion","Northern Trust","Oak Ridge","Oberweis Asset","Parkwest","Peak 6","Pennington","Penwater","Peregrine","Perkins","Perritt","Precept Capital","Principal","Provenire","Rail-Splitter","Ranger","Riverwater Partners","RMB Capital","Rothschild","Segall Bryant","SG Capital","Sheffield Asset Management","Shine Investment","Simplex","Skyline","State of Wisconsin","State Teachers of Ohio","Surveyor (Citadel)","Tennessee Consolidated Retirement","Texas Teachers","Thornburg","Thrivent","UBS O'Connor","Vaughan Nelson","Venbio","Waddell & Reed","Walleye","Walrus Partners","Wanger","WC Capital","Wells Capital","Wells Fargo","Westwood","Whetstone Capital","William Blair","Woodway Financial"],
"West Coast": ["Akahi","Algert Global","Alliance","Alta Park Capital","Analytic Investors","Archon Capital","Artis Capital","Ascend","AXA Rosenberg","Big Basin","BlackRock","California Teachers","Capital Guardian","Capital Research","Capital World","Columbia Management","Columbia Threadneedle","Cramer Rosenthal","Criterion Capital","Crosslink","Cutler","DB Alternative Trading","Digital","Dodge & Cox","EAM","Falcon Point","First Pacific","Franklin Templeton","Granite Investment Partners","GROW Partners","H&W","Harpoon","Hotchkis & Wiley","ICONIQ Capital","Ivory","Jafra","Keenan Capital","Menta Capital","Montibus","Nicholas","NWQ","Oliver Press","Osterweis Capital","Owenoke","Ozumo","Pacific Grove","Panoramic","Park West","Partner Fund","Passport Capital","PIMCO","Platte River","Potrero Capital","Preservation","PresPoint Capital","Primecap","Prospect Capital","Provident","QCM","Rainier","Relational Investors","Rice Hall","Ridgecrest","RS Investment","Russell Investment","Seasons Capital","SFNT","Sidus","Stadlin Capital","Stonebridge Capital","Symmetry","TCW","Tech Oppty","Tenzing Global","Transamerica","Tribeca","Tygh Capital","Valinor","Wells Fargo"],
"Boston": ["Acadian","Adage","Alydar Partners","Arrowstreet","Ash Capital","Baring Asset Global","Bogle","Brookside","Cadence Capital","Coll Capital","Columbia Management","Constitutional","D.L. Babson","DG Capital","Eaton Vance","Essex","Evergreen","Federated","Fidelity","Frontier","Geode Capital","Granahan","Granite Point","Hancock","Independence","Invenomic Capital","John McStay","Lee Munder","LMCG Investments","Loring Wolcott","Mellon Growth Advisors","MFS","PanAgora Asset","Pangaea","Pioneer","Portolan","Putnam","RhumbLine Advisors","Robeco","Standard Life","State Street","Taylor Wealth Management","Telemark","Teton","The Boston Company","Tudor","Vinik","Wellington","Westfield","Whalerock","WPG Partners"],
"Mid Atlantic/South": ["1838 Investment Advisors","Aberdeen","Afton","Alpha One","Ashford","Atlantic Capital","Banbury","BlackRock","BlueCrest","Brown Investment Advisors","Cambiar","Casey","Chief Cornerstone","Columbia Partners","Concourse","Conestoga","Croft-Leominster","Delaware Investments","DePrince Race & Zollo","Eagle Asset Management","Emerald","Ewing (Mint Capital)","Financial Architects","Florida State Board of Admin","Friess","Glenmede","Greenhouse","Manulife","Masters","MFC Global","Millrace","Penn Capital","PNC Capital","Retirement Systems of Alabama","RGM","Ridgeworth","Roundview","Spartan","State of Georgia","Sterling","SunTrust","T. Rowe","TFS","Thompson Davis","Tower Bridge","Trusco","US Trust","Vanguard","Wedge Capital","Wells Trust"],
"Canada": ["Addenda Capital","AGF Management","AMI","Barometer","BC Investment","Bimcor","BloombergSen Investment Partners","Burgundy Asset","C.A. Delaney","Canada Pension Plan","CDPQ","CI Signature","Connor Clark & Lunn","Creststreet","Formula Growth","Front Street Capital","G3 Capital","Gluskin","Goodman","GWL Investment","Gyrus Investment","Hillsdale","IGM Financial","Invesco Trimark","Investor Group","Jarislowsky Fraser","Jones Heward","K2","KBSH Capital","Letko Brosseau & Associates","Mackenzie","Manulife","MFC Global Investment","Natcan","New Brunswick","Northern Rivers Capital","OMERS","Ontario Teachers","Pembrook","Picton Mahoney","Polar","Pyramis","RBC","Ridgewood","Societe De Transport de Montreal","Scotia","Sentry Select","Stark Investment","Strategic Development","TD Asset","TD Harbour","Webb Asset"],
}

LEGAL={"llc","lp","inc","incorporated","ltd","limited","llp","co","company","corp","corporation",
       "plc","the","of","and","&","group","holdings"}
def toks(s):
    s=re.sub(r"\(.*?\)"," ",s.lower())
    s=re.sub(r"[^a-z0-9 ]"," ",s)
    return [t for t in s.split() if t and t not in LEGAL]

c=db.get_connection().cursor()
c.execute("SELECT DISTINCT firm FROM contacts WHERE firm IS NOT NULL AND firm<>''")
dbfirms=[r[0] for r in c.fetchall()]
db_index=[]
for f in dbfirms:
    t=toks(f)
    db_index.append((f, t, " ".join(t)))

def match(name):
    lt=toks(name)
    if not lt: return None
    lj=" ".join(lt)
    for f,dt,dj in db_index:
        if not dt: continue
        # exact core, or list-core is leading token-subsequence of db, or substring either way
        if lj==dj: return f
        if lt[0]==dt[0] and (len(lt)==1 and len(lt[0])>=5 or set(lt[:2])<=set(dt)): return f
        if len(lj)>=5 and (lj in dj or (len(dj)>=5 and dj in lj)): return f
    return None

tot=miss=0; out={}
for region,firms in LIST.items():
    seen=set(); mrows=[]
    for name in firms:
        k=name.lower()
        if k in seen: continue
        seen.add(k); tot+=1
        m=match(name)
        if m is None: miss+=1; mrows.append(name)
    out[region]=(len(seen),mrows)
print(f"TOTAL list accounts (deduped within region): {tot} | NOT in DB: {miss} | in DB: {tot-miss} ({round(100*(tot-miss)/tot)}%)\n")
for region,(n,mrows) in out.items():
    print(f"=== {region}: {n} listed, {len(mrows)} NOT in DB ===")
    print("   " + " | ".join(mrows))
    print()
