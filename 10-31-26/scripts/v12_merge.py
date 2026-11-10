"""One institution, one name, for v12 -> data/analysis/institution_merge_v12.csv: the v11 merges plus the names below.

The v11 rules only reached names shaped like "X University Hospital", so "Wake Forest Baptist Medical Center", "Mayo Foundation" and "Cleveland Clinic Florida" kept their own dots.
Here each pattern is a name that belongs to one institution, read from the largest names left apart: its hospitals and schools, its spellings, and its former names.
Two general rules follow: a hospital or school carrying a whole university's name at its end, and names with the same words in another order or language.
A name whose main country differs from the parent's stays apart, so Cleveland Clinic Abu Dhabi, Duke-NUS and Monash Malaysia keep their own dots.
Names with no country of their own follow the pattern. Independent hospitals (Cleveland Clinic against Case Western, MSK, MD Anderson) stay apart as in v11.

Usage: python 10-31-26/scripts/v12_merge.py   (from the IMPACT folder)
"""
import collections
import csv
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v10_merge as V  # noqa: E402

DATA = V.DATA
MIN_PAPERS = 3
# parent: patterns matched from the start of the name
FAMILIES = {
    "wake forest university": [r"wake forest\b", r"atrium (health )?wake forest\b", r"(the )?comprehensive cancer center (at|of) wake forest\b", r"bowman gray school of medicine", r"(north carolina )?baptist (medical center|hospitals?) (of |at )?(wake|winston)"],
    "mayo clinic": [r"mayo clinic\b", r"mayo medical (school|center|laboratories)", r"mayo foundation", r"mayo graduate school", r"mayo school of", r"mayo college of"],
    "cleveland clinic": [r"cleveland clinic\b"],
    "oregon health and science university": [r"oregon health (and |& )?sciences? (university|center)", r"ohsu\b"],
    "duke university": [r"duke (university|clinical research|health|cancer|medical|eye|global health|molecular|human vaccine|comprehensive)\b(?! nus)"],
    "northwestern university": [r"northwestern (feinberg|medicine|memorial hospital)\b", r"feinberg school of medicine", r"robert h lurie (comprehensive )?cancer center"],
    "pennsylvania state university": [r"pennsylvania state (college of medicine|university|milton)\b", r"penn state\b"],
    "temple university": [r"temple university\b", r"lewis katz school of medicine"],
    "icahn school of medicine at mount sinai": [r"icahn school of medicine\b", r"mount sinai school of medicine", r"mount sinai health system", r"icahn medical"],
    "rush university": [r"rush (university|medical college|presbyterian|medical center)\b"],
    "rutgers university": [r"rutgers\b", r"robert wood johnson medical school", r"university of medicine and dentistry of new jersey", r"umdnj\b"],
    "tufts university": [r"tufts\b"],
    "university of michigan": [r"michigan medicine\b", r"university of michigan\b(?! (flint|dearborn))"],
    "texas a and m university": [r"texas a ?(and|&) ?m (university system|university college|health science|college|university health|university school)\b"],
    "louisiana state university": [r"louisiana state university\b", r"lsu\b"],
    "augusta university": [r"georgia regents university\b", r"georgia health sciences university\b", r"medical college of georgia\b", r"augusta university\b"],
    "university of colorado": [r"university of colorado\b(?! (boulder|colorado springs|at boulder|at colorado springs))"],
    "university of maryland baltimore": [r"university of maryland (medical|school|greenebaum|marlene)\b"],
    "h lee moffitt cancer center and research institute": [r"(h lee )?moffitt cancer\b"],
    "city of hope national medical center": [r"city of hope\b"],
    "university of pennsylvania": [r"penn medicine\b", r"perelman (school|center)\b", r"hospital of the university of pennsylvania"],
    "university of pittsburgh": [r"upmc\b(?! (hamot|altoona|pinnacle))", r"university of pittsburgh (medical|school|cancer)\b"],
    "emory university": [r"emory (healthcare|university|winship|saint|clinic|school|rollins)\b"],
    "vanderbilt university": [r"vanderbilt\b"],
    "yale university": [r"yale (school|new haven|cancer|medicine|university)\b"],
    "ohio state university": [r"ohio state university\b", r"the ohio state\b"],
    "university of california san diego": [r"uc san diego\b", r"ucsd\b"],
    "university of california los angeles": [r"ucla\b"],
    "university of california san francisco": [r"ucsf\b"],
    "mcgill university": [r"mcgill\b"],
    "monash university": [r"monash (health|medical cent(?:er|re)|university|school)\b"],
    "aarhus university": [r"aarhus universi", r"aarhus university hospital"],
    "erasmus university": [r"erasmus (mc|medical cent(?:er|re)|university)\b"],
    "friedrich alexander universitat erlangen nurnberg": [r"friedrich alexander", r"university of erlangen", r"universitat erlangen", r"university erlangen", r"universitatsklinikum erlangen", r"university hospital erlangen"],
    "friedrich schiller university jena": [r"friedrich schiller", r"university of jena\b", r"jena university", r"university hospital jena", r"universitatsklinikum jena"],
    "university of freiburg": [r"albert ludwigs", r"university of freiburg\b(?! \w*switzerland)", r"universitat freiburg", r"university medical cent(?:er|re) freiburg", r"university hospital freiburg", r"universitatsklinikum freiburg"],
    "heinrich heine university": [r"heinrich heine", r"university of dusseldorf", r"universitat dusseldorf", r"university hospital dusseldorf", r"universitatsklinikum dusseldorf"],
    "charles university": [r"charles university\b"],
    "vrije universiteit amsterdam": [r"vu university\b", r"vu medical cent", r"vu medisch", r"vrije universiteit( amsterdam| medical cent(?:er|re))?$"],
    "jagiellonian university": [r"jagiellonian university\b"],
    "ben gurion university of the negev": [r"ben gurion university\b"],
    "aristotle university of thessaloniki": [r"aristotle university\b"],
    "wageningen university": [r"wageningen (university|ur)\b"],
    "imperial college london": [r"imperial college of science\b"],
    "russian academy of sciences": [r"russian academy of science$"],
    "polish academy of sciences": [r"polish academy of science$"],
    "huazhong agricultural university": [r"huazhong agriculture university"],
    "capital medical university": [r"capital university of medical sciences?\b"],
    "wenzhou medical university": [r"wenzhou medical college\b"],
    "sun yat sen university": [r"sun yat sen university of medical sciences?\b"],
    "king saud university": [r"king saud university medical city"],
    "king faisal specialist hospital and research centre": [r"king faisal specialist hospital and research center"],
    "hospital clinic": [r"hospital clinic (de |of |i provincial de |i provincial of )?barcelona\b"],
    # Second reading: spellings and languages of one name, and names that carry a parent's name inside them.
    "harvard university": [r"harvard (business|law|kennedy|graduate|college|divinity|stem cell|pilgrim)\b", r".*\bharvard medical school$"],
    "johns hopkins university": [r"johns? hopkins (asthma|school|hospital|medical|university|bloomberg|kimmel|bayview|oncology|wilmer|sidney)\b"],
    "shanghai jiao tong university": [r"affiliated to shanghai jiao tong university"],
    "xi an jiaotong university": [r"xi an jiao tong university"],
    "peking university": [r"peking university\b"],
    "university of wisconsin madison": [r"university of wisconsin$", r"university of wisconsin (hospital|school|medical|carbone|paul p carbone|at madison)\b"],
    "university of missouri columbia": [r"university of missouri$", r"university of missouri (school|hospital|health)\b"],
    "university of illinois urbana champaign": [r"university of illinois (urbana|champaign|at urbana)\b"],
    "western sydney university": [r"university of western sydney\b"],
    "university of zurich": [r"university children s hospital zurich", r"universitatsspital zurich", r"universitaet zurich", r"universitat zurich"],
    "eth zurich": [r"eidgenossische technische hochschule"],
    "cincinnati children s hospital medical center": [r"cincinnati children s\b"],
    "university of toronto": [r"university of toronto\b"],
    "university of melbourne": [r"university of melbourne\b"],
    "university of iowa": [r"university of iowa\b"],
    "cornell university": [r"new york presbyterian hospital weill\b", r"weill cornell\b", r"new york presbyterian weill\b"],
    "university of texas md anderson cancer center": [r"(ut|the university of texas) (m d|md) anderson\b", r"md anderson\b"],
    "utrecht university": [r"umc utrecht", r"universitair medisch centrum utrecht", r"university medical cent(?:er|re) utrecht"],
    "university of groningen": [r"universitair medisch centrum groningen", r"umc groningen", r"university medical cent(?:er|re) groningen"],
    "radboud university": [r"(universitair medisch centrum|university medical cent(?:er|re)|umc) st radboud", r"radboud\b"],
    "sapienza university of rome": [r"(?:.* )?sapienza\b"],
    "ku leuven": [r"catholic university (of )?leuven"],
    "university of miami": [r"university of miami\b"],
    "university of texas southwestern medical center": [r"university of texas southwestern\b", r"ut southwestern\b", r"southwestern medical (center|school)\b"],
    "hebrew university of jerusalem": [r"hebrew university\b", r"hadassah hebrew university"],
    "shahid beheshti university of medical sciences": [r"shaheed beheshti university of medical sciences?"],
    "university of heidelberg": [r"ruprecht karls", r"university heidelberg", r"medical faculty mannheim", r"universitat heidelberg", r"universitatsklinikum heidelberg", r"university hospital heidelberg"],
    "university of wurzburg": [r"julius maximilians"],
    "ludwig maximilians university munich": [r"ludwig maximilians? universi", r"lmu\b", r"klinikum der ludwig maximilians"],
    "university of bonn": [r"rheinische friedrich wilhelms"],
    "university of tubingen": [r"eberhard karls"],
    "university of gottingen": [r"georg august"],
    "university of munster": [r"westfalische wilhelms"],
    "johannes gutenberg university": [r"(?:.* )?johannes gutenberg universit"],
    "humboldt universitat zu berlin": [r"humboldt universit"],
    "freie universitat berlin": [r"free university of berlin"],
    "university of hamburg": [r"universitatsklinikum hamburg", r"university hospital hamburg", r"university medical cent(?:er|re) hamburg", r"universitat hamburg"],
    "charite universitatsmedizin berlin": [r"charite\b", r"universitatsmedizin berlin", r"corporate member of freie universitat berlin", r"university hospital charite"],
    "rwth aachen university": [r"(?:.* )?rwth\b", r"university of aachen", r"university hospital aachen"],
    "university of leipzig": [r"university leipzig", r"universitatsklinikum leipzig", r"universitat leipzig"],
    "university of lausanne": [r"university hospital center and university of lausanne"],
    "university of duisburg essen": [r"university of essen\b", r"university duisburg essen", r"universitat duisburg essen", r"universitat essen\b", r"universitatsklinikum essen", r"university hospital essen"],
    "university of bologna": [r"alma mater studiorum"],
    "university of campinas": [r"(universidade estadual|state university) (de|of) campinas", r"university of campinas\b"],
    "universidade federal de minas gerais": [r"federal university of minas gerais", r"universidade federal de minas gerais\b"],
    "university of bari": [r"university of bari\b", r"universita degli studi di bari", r"aldo moro university"],
    "university of rome tor vergata": [r"(?:.* )?tor vergata\b"],
    "university of milano bicocca": [r"(?:.* )?milano bicocca\b", r"university of milan bicocca"],
    "university of milan": [r"university of milano$"],
    "medical university of innsbruck": [r"innsbruck medical university", r"medical university innsbruck", r"medizinische universitat innsbruck"],
    "medical university of graz": [r"medical university graz", r"medizinische universitat graz"],
    "university of graz": [r"karl franzens"],
    "hannover medical school": [r"medizinische hochschule hannover", r"medical school hannover"],
    "leibniz universitat hannover": [r"leibniz university hannover"],
    "universidad complutense de madrid": [r"(?:.* )?complutense\b"],
    "universidad de buenos aires": [r"university of buenos aires\b"],
    "university of malaya": [r"universiti malaya", r"university malaya"],
    "university of valencia": [r"universitat de valencia", r"universidad de valencia"],
    "universitat politecnica de valencia": [r"universidad politecnica de valencia"],
    "universite catholique de louvain": [r"catholic university of louvain", r"university of louvain"],
    "university at buffalo": [r"state university of new york (at )?buffalo", r"university of buffalo"],
    "stony brook university": [r"state university of new york (at )?stony brook", r"stony brook (medicine|school|university)\b"],
    "georgetown university": [r"medstar georgetown university"],
    "university of connecticut": [r"university of connecticut\b"],
    "university of texas medical branch": [r"university of texas medical branch\b"],
    "university of texas health science center at san antonio": [r"university of texas health (science center )?(at )?san antonio", r"ut health san antonio"],
    "university of california davis": [r"(uc )?davis (medical center|school of medicine)\b", r"uc davis\b"],
    "university of california irvine": [r"(uc )?irvine medical center\b", r"uc irvine\b"],
    "thomas jefferson university": [r"jefferson medical college", r"rothman (orthopaedic )?institute"],
    "memorial sloan kettering cancer center": [r"sloan kettering\b"],
    "albert einstein college of medicine": [r"albert einstein college of medicine\b", r"montefiore medical center albert einstein"],
    "national yang ming chiao tung university": [r"national chiao tung university"],
    "chang gung university": [r"(\w+ )?chang gung (memorial|children)\b"],
    "oklahoma state university": [r"oklahoma state university center for health"],
    "university of nebraska medical center": [r"nebraska medical center"],
    "hopital saint louis": [r"saint louis hospital\b"],
    "saint louis university": [r"st louis university\b"],
    "instituto oswaldo cruz": [r"(fundacao |fundacion )?oswaldo cruz( foundation| institute)?$"],
    "technion israel institute of technology": [r"israel institute of technology"],
    "lomonosov moscow state university": [r"moscow state university$", r"m v lomonosov moscow"],
    "siberian branch of the russian academy of sciences": [r"siberian branch of russian academy of sciences?"],
    "university of delhi": [r"university of delhi\b", r"delhi university\b"],
    "maulana azad medical college": [r"maulana azad medical college\b"],
    "leeds general infirmary": [r"general infirmary at leeds"],
    "oslo metropolitan university": [r"oslomet\b"],
    "medical university of warsaw": [r"warsaw medical university"],
    "warsaw university of life sciences": [r"warsaw university of life sciences\b"],
    "universitas indonesia": [r"faculty of medicine universitas indonesia"],
    "universite claude bernard lyon": [r"universite claude bernard lyon\b"],
    "universita cattolica del sacro cuore": [r"catholic university of (the )?sacred heart", r"catholic university of rome", r"(fondazione )?policlinico universitario a gemelli", r"policlinico gemelli"],
    "cedars sinai medical center": [r"cedars sinai\b"],
    "houston methodist hospital": [r"houston methodist\b"],
    "henry ford hospital": [r"henry ford (health|medical|cancer)\b"],
    "roswell park cancer institute": [r"roswell park\b"],
    "st jude children s research hospital": [r"st jude children s\b"],
    # Third reading: German and Italian names with a person in them, and other spellings.
    "goethe university": [r"goethe universit", r"johann wolfgang goethe"],
    "justus liebig university giessen": [r"justus liebig"],
    "philipps universitat marburg": [r"philipps universit"],
    "university of kiel": [r"christian albrechts"],
    "martin luther university halle wittenberg": [r"martin luther universit"],
    "otto von guericke university magdeburg": [r"otto von guericke"],
    "university of greifswald": [r"ernst moritz arndt", r"university medicine greifswald"],
    "carl von ossietzky universitat oldenburg": [r"carl von ossietzky"],
    "g d annunzio university": [r"(?:.* )?g ?d ?annunzio"],
    "magna graecia university of catanzaro": [r"(?:.* )?magna graecia"],
    "vita salute san raffaele university": [r"(?:.* )?vita salute"],
    "campus bio medico university": [r"(?:.* )?campus bio medico"],
    "roma tre university": [r"(?:.* )?roma tre\b"],
    "universidade estadual paulista": [r"universidade estadual paulista", r"sao paulo state university", r"state university of sao paulo", r"unesp\b"],
    "university of naples federico ii": [r"federico ii university", r"university federico ii", r"(?:.* )?napoli federico ii\b"],
    "technische universitat dresden": [r"dresden university of technology", r"technical university (of )?dresden", r"university of technology dresden"],
    "technische universitat berlin": [r"technical university (of )?berlin"],
    "uniformed services university of the health sciences": [r"uniformed services university\b"],
    "medical university of silesia": [r"medical university of silesia\b"],
    "university of tokushima": [r"university of tokushima\b", r"tokushima university\b"],
    "university of sao paulo": [r"(?:.* )?(faculdade de medicina|hospital das clinicas).* (da |de )?universidade de sao paulo", r"universidade de sao paulo\b", r"university of sao paulo\b", r"(?:.* )?faculdade de medicina da usp"],
    "universidade federal de sao paulo": [r"universidade federal de sao paulo\b", r"federal university of sao paulo\b", r"escola paulista de medicina"],
    "virginia tech": [r"virginia polytechnic institute\b", r"virginia tech\b(?! wake forest)"],
    "cnrs": [r"cnrs\b"],
    "inserm": [r"inserm\b", r"unite inserm"],
}
# A hospital or school that carries the whole university's name at its end: "zhongshan hospital fudan university".
CARRIER = re.compile(r"\b(hospitals?|affiliated|medical cent(?:er|re)|school|academy|institute|cent(?:er|re)|faculty|college|clinic)\b")
NOT_CARRIED = {"university of london", "university of texas", "university of wales", "university of maryland", "university of paris", "university of nebraska", "university of alabama", "university of hawaii", "university of massachusetts", "university of north carolina", "university of tennessee", "university of south carolina", "university of california", "state university of new york", "national university of ireland", "university of lyon", "university of newcastle"}
NOT_CARRIER = re.compile(r"^(max planck|cnrs|inserm|nih|national|massachusetts|howard hughes|medical college|medical university|school of oriental)\b")
FIRST = re.compile(r"universi|institute of technology")
GENERIC = {"university hospital", "university hospitals", "university medical center", "university medical centre", "university clinic", "university college", "national university", "state university"}
# Same words in another order or language: "federal university of sao paulo" and "universidade federal de sao paulo".
TRANSLATE = {"universitat": "university", "universite": "university", "universita": "university", "universidad": "university", "universidade": "university", "universiteit": "university", "centre": "center", "hopital": "hospital", "ospedale": "hospital", "institut": "institute", "instituto": "institute", "istituto": "institute", "sciences": "science", "medicine": "medical"}
SMALL_WORDS = {"of", "the", "de", "di", "do", "da", "del", "at", "in", "and", "la", "le", "zu", "du", "des", "degli", "studi", "am", "a", "s", "for"}
# Words that say nothing about which institution it is: names of only these are never joined.
PLAIN_WORDS = {"university", "hospital", "medical", "science", "health", "college", "school", "institute", "center", "national", "general", "graduate", "research", "technology", "cancer", "children", "people", "first", "second", "third", "central", "military", "veterans", "clinic", "state", "federal", "government", "city", "faculty", "academy", "chinese"}
# Same words, different institutions: Washington University and the University of Washington, PGIMER Chandigarh and IPGMER Kolkata, the two Anhui universities.
NOT_SAME = {"washington", "miami", "jinan", "shizuoka", "pacific", "anhui", "postgraduate", "post", "california", "ohio", "lincoln", "victoria", "york", "maine", "salle", "punjab", "joseph", "newcastle"}
# Merged by an earlier rule, but a separate university.
UNDO = {"texas a and m university kingsville"}
# German, Swiss and Dutch names for a city's university hospital.
CITY = re.compile(r"^(?:universitatsmedizin|universitatsspital|universitair medisch centrum|umc|university children s hospital) (\w+)$")
# Spellings of one name, ending in the singular: "tabriz university of medical science".
PLURAL = re.compile(r"\b(university of medical|university of health|academy of) science$")
PLURAL_S = re.compile(r"\b(university of medical|university of health|academy of) sciences$")


def main():
    D, K = V.load()
    keys = list(K["keys"])
    index = {k: i for i, k in enumerate(keys)}
    inst = D["inst"]
    home = V.main_countries(D, K)
    cnt = np.bincount(inst[inst >= 0], minlength=len(keys))
    f = np.bincount(inst[(inst >= 0) & (D["flagship"] > 0)], minlength=len(keys))
    old = list(csv.DictReader(open(os.path.join(DATA, "institution_merge_v11.csv"))))
    base = {r["name"]: r["merged_into"] for r in old}
    root = lambda k: base.get(k, k)  # noqa: E731
    n, fr = collections.Counter(), collections.Counter()
    for k, c, g in zip(keys, cnt.tolist(), f.tolist()):
        if c:
            n[root(k)] += c
            fr[root(k)] += g
    # A root's home: the country of its largest name.
    place = lambda k: int(home[index[k]]) if k in index else -1  # noqa: E731
    n.update({k: 0 for k in UNDO})
    pats = [(p, re.compile("(?:" + "|".join(v) + ")")) for p, v in FAMILIES.items()]
    for p, _ in pats:
        assert root(p) == p and n[p] >= 200, (p, root(p), n[p])
    out = {}
    for k, v in n.items():
        if v < MIN_PAPERS or k in FAMILIES or k in UNDO:
            continue
        hit = next((p for p, rx in pats if rx.match(k)), None)
        rule = "family"
        if not hit and PLURAL.search(k) and k + "s" in n and n[k + "s"] >= v:
            hit, rule = root(k + "s"), "spelling"
        if not hit and PLURAL_S.search(k) and k[:-1] in n and n[k[:-1]] > v:     # the singular is the commoner: Shiga University of Medical Science
            hit, rule = root(k[:-1]), "spelling"
        if not hit:
            m = CITY.match(k)
            c = m and next((x for x in ("university of " + m.group(1), m.group(1) + " university") if n[x] >= 2000), None)
            if c:
                hit, rule = root(c), "city"
        if not hit and v >= 10 and CARRIER.search(k) and not NOT_CARRIER.match(k):
            w = k.split()
            for cut in range(1, len(w) - 1):
                tail = " ".join(w[cut:])
                head = " ".join(w[:cut]).removesuffix(" and")
                if n[tail] >= 2000 and "universi" in tail and tail not in NOT_CARRIED and tail not in V.NEVER_PARENT and tail not in GENERIC and CARRIER.search(head):
                    # Two institutions named: the first keeps it, as with other joint names.
                    joint = (w[cut - 1] == "and" or FIRST.search(head)) and head not in GENERIC and n[root(head)] >= 200 and root(head) != tail
                    if not joint:
                        hit, rule = tail, "carried"
                    break
        if not hit or hit == k:
            continue
        a, b = place(k), place(hit)
        if a >= 0 and b >= 0 and a != b:
            continue
        out[k] = (hit, rule)
    def final(k):
        while k in out:
            k = out[k][0]
        return k

    size = collections.Counter()
    for k, v in n.items():
        size[final(k)] += v
    groups = collections.defaultdict(list)
    for k, v in size.items():
        if v >= 30:
            words = frozenset(TRANSLATE.get(w, w) for w in k.split() if w not in SMALL_WORDS)
            if len(words) >= 2 and words - PLAIN_WORDS and not words & NOT_SAME:
                groups[words].append(k)
    for names in groups.values():
        if len(names) > 1:
            names.sort(key=lambda k: -size[k])
            for k in names[1:]:
                a, b = place(k), place(names[0])
                if a == b or a < 0 or b < 0:
                    out[k] = (names[0], "same words")

    rows = [[r["name"], final(r["merged_into"]), r["rule"], r["papers"], r["flagship_papers"], r["listed_share"]] for r in old if r["name"] not in UNDO]
    rows += [[k, final(p), r, n[k], fr[k], ""] for k, (p, r) in out.items()]
    rows.sort(key=lambda x: -int(x[3]))
    with open(os.path.join(DATA, "institution_merge_v12.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["name", "merged_into", "rule", "papers", "flagship_papers", "listed_share"])
        w.writerows(rows)
    print(len(rows), "rows;", len(out), "new names;", sum(n[k] for k in out), "papers moved")
    for k, (p, r) in sorted(out.items(), key=lambda x: -size[x[0]]):
        if r == "same words" and size[k] >= 150:
            print(size[k], k, "->", p)


if __name__ == "__main__":
    main()
