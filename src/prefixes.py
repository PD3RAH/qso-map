# -*- coding: utf-8 -*-
"""
Approximate station position from the callsign prefix (fallback when an ADIF record has no
GRIDSQUARE or LAT/LON). Positions are country centroids, for large countries per call area.
Benadering van de positie uit het prefix van de roepnaam (als er geen locator in de log staat).

Copyright (c) 2026 Richard A. Hendriksen (PD3RAH) - MIT License
"""

# prefixes (comma separated) | country | lat | lon
_TABLE = """
PA,PB,PC,PD,PE,PF,PG,PH,PI|Netherlands|52.2|5.5
ON,OO,OP,OQ,OR,OS,OT|Belgium|50.6|4.6
DA,DB,DC,DD,DE,DF,DG,DH,DI,DJ,DK,DL,DM,DN,DO,DP,DQ,DR|Germany|51.0|10.4
F|France|46.6|2.4
TK|Corsica|42.1|9.1
G,M,2E,2D|England|52.5|-1.5
GW,MW,2W|Wales|52.3|-3.7
GM,MM,2M,GS,MS|Scotland|56.8|-4.2
GI,MI,2I,GN,MN|Northern Ireland|54.6|-6.7
GD,MD,2D|Isle of Man|54.2|-4.5
GJ,MJ,2J,GH,MH|Jersey|49.2|-2.1
GU,MU,2U,GP,MP|Guernsey|49.45|-2.58
EI,EJ|Ireland|53.2|-8.0
LX|Luxembourg|49.8|6.1
HB|Switzerland|46.8|8.2
HB0|Liechtenstein|47.15|9.55
OE|Austria|47.6|14.1
I|Italy|42.8|12.5
IS,IM|Sardinia|40.1|9.0
IT9,IH9|Sicily|37.6|14.1
EA,EB,EC,ED,EE,EF,EG,EH|Spain|40.3|-3.7
EA6,EB6,EC6,ED6,EE6,EF6,EG6,EH6|Balearic Islands|39.6|2.9
EA8,EB8,EC8,ED8,EE8,EF8,EG8,EH8|Canary Islands|28.3|-15.7
EA9,EB9,EC9,ED9,EE9,EF9,EG9,EH9|Ceuta & Melilla|35.9|-5.3
CT,CQ,CR,CS|Portugal|39.6|-8.0
CU,CT8,CQ8,CR8|Azores|38.5|-28.0
CT3,CQ3,CR3|Madeira|32.75|-16.95
C3|Andorra|42.5|1.55
3A|Monaco|43.74|7.42
T7|San Marino|43.94|12.46
HV|Vatican|41.9|12.45
9H|Malta|35.9|14.4
SV,SW,SX,SY,SZ,J4|Greece|39.0|22.0
SV5,J45|Dodecanese|36.2|28.0
SV9,J49|Crete|35.2|24.9
SV/A,SY2A|Mount Athos|40.2|24.3
OZ,OU,OV,5P,5Q|Denmark|56.0|10.0
OX,XP|Greenland|70.0|-42.0
OY|Faroe Islands|62.0|-6.9
LA,LB,LC,LD,LE,LF,LG,LH,LI,LJ,LK,LL,LM,LN|Norway|61.0|9.0
JW|Svalbard|78.2|16.0
JX|Jan Mayen|71.0|-8.5
SA,SB,SC,SD,SE,SF,SG,SH,SI,SJ,SK,SL,SM,7S,8S|Sweden|62.0|15.5
OF,OG,OH,OI,OJ|Finland|63.0|26.0
OH0,OF0,OG0,OI0|Aland Islands|60.2|20.0
OJ0|Market Reef|60.3|19.13
ES|Estonia|58.7|25.5
YL|Latvia|56.9|24.8
LY|Lithuania|55.3|23.9
SN,SO,SP,SQ,SR,3Z,HF|Poland|52.0|19.4
OK,OL|Czech Republic|49.8|15.5
OM|Slovakia|48.7|19.7
HA,HG|Hungary|47.2|19.4
YO,YP,YQ,YR|Romania|45.9|24.9
LZ|Bulgaria|42.7|25.3
YT,YU|Serbia|44.0|20.8
9A|Croatia|45.1|15.2
S5|Slovenia|46.1|14.8
E7|Bosnia-Herzegovina|44.2|17.8
Z3|North Macedonia|41.6|21.7
4O|Montenegro|42.7|19.3
ZA|Albania|41.1|20.0
Z6|Kosovo|42.6|20.9
EU,EV,EW|Belarus|53.7|28.0
EM,EN,EO,UR,US,UT,UU,UV,UW,UX,UY,UZ|Ukraine|49.0|31.4
ER|Moldova|47.2|28.5
4L|Georgia|42.3|43.4
EK|Armenia|40.2|44.9
4J,4K|Azerbaijan|40.3|47.7
TA,TB,TC,YM|Turkey|39.0|35.0
5B,C4,H2,P3|Cyprus|35.0|33.2
4X,4Z|Israel|31.5|34.9
E4|Palestine|31.9|35.2
UN,UO,UP,UQ|Kazakhstan|48.0|67.0
EX|Kyrgyzstan|41.5|74.5
EY|Tajikistan|38.8|71.0
EZ|Turkmenistan|39.0|59.0
UJ,UK,UL,UM|Uzbekistan|41.4|64.6
TF|Iceland|64.9|-18.6
JA,JE,JF,JG,JH,JI,JJ,JK,JL,JM,JN,JO,JP,JQ,JR,JS,7J,7K,7L,7M,7N,8J,8K,8L,8M,8N|Japan|36.2|138.3
JD1|Ogasawara|27.1|142.2
HL,DS,DT,6K,6L,6M,6N|South Korea|36.4|127.9
P5|North Korea|40.0|127.0
B,BA,BD,BG,BH,BI,BJ,BL,BT,BY,BZ,XS,3H,3I,3J,3K,3L,3M,3N,3O,3P,3Q,3R,3S,3T,3U|China|35.0|104.0
BV,BX,BM,BN,BO,BP,BQ,BU,BW|Taiwan|23.7|121.0
VR|Hong Kong|22.3|114.2
XX9|Macao|22.2|113.55
HS,E2|Thailand|15.0|101.0
XV,3W|Vietnam|16.0|107.0
XU|Cambodia|12.6|105.0
XW|Laos|18.5|103.0
XY,XZ|Myanmar|21.9|95.9
9M2,9M4,9W2,9W4|West Malaysia|3.9|102.0
9M6,9M8,9W6,9W8|East Malaysia|3.5|114.0
9V|Singapore|1.35|103.8
V8|Brunei|4.5|114.7
YB,YC,YD,YE,YF,YG,YH,7A,7B,7C,7D,7E,7F,7G,7H,7I,8A,8B,8C,8D,8E,8F,8G,8H,8I|Indonesia|-2.0|118.0
DU,DV,DW,DX,DY,DZ,4D,4E,4F,4G,4H,4I|Philippines|12.5|122.0
4W|Timor-Leste|-8.8|125.7
VU,AT,AU,AV,AW,8T,8U,8V,8W,8X,8Y|India|21.0|78.0
VU4|Andaman & Nicobar|11.7|92.7
VU7|Lakshadweep|10.5|72.6
AP,AQ,AR,AS,6P,6Q,6R,6S|Pakistan|30.0|70.0
4S|Sri Lanka|7.8|80.7
S2,S3|Bangladesh|23.8|90.3
9N|Nepal|28.2|84.0
A5|Bhutan|27.5|90.4
8Q|Maldives|3.2|73.2
EP,EQ,9B,9C,9D|Iran|32.4|53.7
YI,HN|Iraq|33.0|43.7
YK,6C|Syria|35.0|38.5
OD|Lebanon|33.85|35.9
JY|Jordan|31.2|36.5
HZ,7Z,8Z|Saudi Arabia|24.0|45.0
A4|Oman|21.5|56.0
A6|United Arab Emirates|24.0|54.0
A7|Qatar|25.3|51.2
A9|Bahrain|26.0|50.55
9K|Kuwait|29.3|47.6
7O|Yemen|15.5|48.0
JT,JU,JV|Mongolia|46.9|103.8
YA,T6|Afghanistan|33.9|67.7
CN,5C,5D,5E,5F,5G|Morocco|31.8|-7.1
7R,7T,7U,7V,7W,7X,7Y|Algeria|28.0|2.6
3V,TS|Tunisia|34.0|9.5
5A|Libya|27.0|17.0
SU,SS,6A,6B|Egypt|26.8|30.8
ZR,ZS,ZT,ZU,S8|South Africa|-29.0|24.0
V5|Namibia|-22.5|17.0
A2,8O|Botswana|-22.3|24.7
Z2|Zimbabwe|-19.0|29.8
9I,9J|Zambia|-13.1|27.8
C8,C9|Mozambique|-18.7|35.5
7Q|Malawi|-13.25|34.3
5H,5I|Tanzania|-6.4|34.9
5Y,5Z|Kenya|0.0|37.9
5X|Uganda|1.4|32.3
9X|Rwanda|-1.9|29.9
9U|Burundi|-3.4|29.9
ET,9E,9F|Ethiopia|9.1|40.5
6O,T5|Somalia|5.2|46.2
J2|Djibouti|11.8|42.6
E3|Eritrea|15.2|39.8
ST,6T,6U|Sudan|15.6|30.2
Z8|South Sudan|7.0|30.0
TT|Chad|15.5|18.7
5U|Niger|17.6|8.1
TZ|Mali|17.6|-4.0
5T|Mauritania|21.0|-10.9
6V,6W|Senegal|14.5|-14.5
C5|The Gambia|13.45|-15.3
J5|Guinea-Bissau|12.0|-15.0
3X|Guinea|9.9|-9.7
9L|Sierra Leone|8.5|-11.8
EL,5L,5M,6Z,A8,D5|Liberia|6.4|-9.4
TU|Cote d'Ivoire|7.5|-5.5
9G|Ghana|7.9|-1.0
5V|Togo|8.6|0.8
TY|Benin|9.3|2.3
XT|Burkina Faso|12.2|-1.6
5N,5O|Nigeria|9.1|8.7
TJ|Cameroon|7.4|12.4
TL|Central African Rep.|6.6|20.9
TN|Rep. of the Congo|-0.2|15.8
9O,9P,9Q,9R,9S,9T|Dem. Rep. of the Congo|-2.9|23.6
TR|Gabon|-0.8|11.6
3C|Equatorial Guinea|1.6|10.3
3C0|Annobon|-1.43|5.63
D2,D3|Angola|-11.2|17.9
5R,5S,6X|Madagascar|-18.8|46.9
3B8|Mauritius|-20.3|57.6
3B9|Rodrigues|-19.7|63.4
FR|Reunion|-21.1|55.5
S7|Seychelles|-4.7|55.5
D6|Comoros|-11.9|43.9
FH|Mayotte|-12.8|45.15
7P|Lesotho|-29.6|28.2
3DA|Eswatini|-26.5|31.5
D4|Cape Verde|16.0|-24.0
S9|Sao Tome & Principe|0.2|6.6
ZD7|St. Helena|-15.95|-5.7
ZD8|Ascension|-7.95|-14.35
ZD9|Tristan da Cunha|-37.1|-12.3
XA,XB,XC,XD,XE,XF,XG,XH,XI,4A,4B,4C,6D,6E,6F,6G,6H,6I,6J|Mexico|23.6|-102.5
TG,TD|Guatemala|15.6|-90.3
YS,HU|El Salvador|13.8|-88.9
HQ,HR|Honduras|14.8|-86.6
YN,H6,H7|Nicaragua|12.9|-85.2
TI,TE|Costa Rica|9.9|-84.1
TI9|Cocos Island|5.53|-87.06
HO,HP,H3,H8,H9,3E,3F|Panama|8.5|-80.1
V3|Belize|17.2|-88.7
CL,CM,CO,T4|Cuba|21.5|-79.5
HI|Dominican Republic|18.9|-70.4
HH,4V|Haiti|19.0|-72.7
6Y|Jamaica|18.1|-77.3
C6|Bahamas|24.5|-77.5
VP9|Bermuda|32.3|-64.8
ZF|Cayman Islands|19.3|-81.25
VP5|Turks & Caicos|21.7|-71.8
J3|Grenada|12.1|-61.7
J6|St. Lucia|13.9|-61.0
J7|Dominica|15.4|-61.35
J8|St. Vincent|13.25|-61.2
8P|Barbados|13.15|-59.55
9Y,9Z|Trinidad & Tobago|10.45|-61.3
V2|Antigua & Barbuda|17.1|-61.8
V4|St. Kitts & Nevis|17.3|-62.7
FG|Guadeloupe|16.25|-61.55
FM|Martinique|14.65|-61.0
FS|St. Martin|18.07|-63.05
FJ|St. Barthelemy|17.9|-62.83
PJ2|Curacao|12.17|-68.97
PJ4|Bonaire|12.15|-68.27
P4|Aruba|12.52|-69.97
PJ5,PJ6|Saba & St. Eustatius|17.6|-63.1
PJ7|Sint Maarten|18.04|-63.06
VP2E|Anguilla|18.22|-63.05
VP2M|Montserrat|16.74|-62.19
VP2V|British Virgin Islands|18.43|-64.62
FP|St. Pierre & Miquelon|46.8|-56.2
YV,YW,YX,YY,4M|Venezuela|7.1|-66.2
YV0|Aves Island|15.67|-63.62
HJ,HK,5J,5K|Colombia|4.6|-74.1
HK0|San Andres|12.55|-81.72
HC,HD|Ecuador|-1.4|-78.4
HC8,HD8|Galapagos|-0.7|-90.3
OA,OB,OC,4T|Peru|-9.2|-75.0
CP|Bolivia|-16.3|-63.6
PP,PQ,PR,PS,PT,PU,PV,PW,PX,PY,ZV,ZW,ZX,ZY,ZZ|Brazil|-14.2|-51.9
PY0F,PP0F,PQ0F,PR0F,PS0F,PT0F,PU0F,PV0F,PW0F,PX0F,ZV0F,ZW0F,ZX0F,ZY0F,ZZ0F|Fernando de Noronha|-3.85|-32.42
CA,CB,CC,CD,CE,XQ,XR,3G|Chile|-33.4|-70.6
CE0Y,XQ0Y,XR0Y,3G0Y|Easter Island|-27.1|-109.35
CE0Z,XQ0Z,XR0Z,3G0Z|Juan Fernandez|-33.6|-78.8
AY,AZ,L2,L3,L4,L5,L6,L7,L8,L9,LO,LP,LQ,LR,LS,LT,LU,LV,LW|Argentina|-34.6|-63.6
CV,CW,CX|Uruguay|-32.8|-56.0
ZP|Paraguay|-23.4|-58.4
8R|Guyana|5.0|-58.9
PZ|Suriname|4.0|-56.0
FY|French Guiana|4.0|-53.0
VP8|Falkland Islands|-51.7|-59.5
ZL,ZM|New Zealand|-41.0|174.0
ZL7|Chatham Islands|-44.0|-176.5
ZL8|Kermadec Islands|-29.25|-177.9
ZL9|Auckland & Campbell Is.|-50.7|166.1
P2|Papua New Guinea|-6.3|147.0
H4|Solomon Islands|-9.6|160.2
H40|Temotu|-10.7|165.9
YJ|Vanuatu|-16.0|167.0
FK|New Caledonia|-21.3|165.5
3D2|Fiji|-17.7|178.1
5W|Samoa|-13.8|-172.1
A3|Tonga|-21.2|-175.2
E5|Cook Islands|-21.2|-159.8
FO|French Polynesia|-17.65|-149.4
T2|Tuvalu|-8.5|179.2
T30|Western Kiribati|1.4|173.0
T31|Central Kiribati|-2.8|-171.7
T32|Eastern Kiribati|1.87|-157.4
T33|Banaba|-0.87|169.53
V7|Marshall Islands|7.1|171.2
V6|Micronesia|6.9|158.2
T8|Palau|7.5|134.6
C2|Nauru|-0.52|166.93
ZK3|Tokelau|-9.2|-171.8
E6|Niue|-19.05|-169.87
FW|Wallis & Futuna|-13.3|-176.2
VP6|Pitcairn|-25.07|-130.1
VK9N|Norfolk Island|-29.04|167.95
VK9C|Cocos (Keeling)|-12.17|96.83
VK9X|Christmas Island|-10.49|105.62
VK9L|Lord Howe Island|-31.55|159.08
VK0H|Heard Island|-53.1|73.5
VK0M|Macquarie Island|-54.6|158.9
KH6,AH6,NH6,WH6,KH7,AH7,NH7,WH7|Hawaii|20.8|-157.0
KH2,AH2,NH2,WH2|Guam|13.45|144.8
KH0,AH0,NH0,WH0|Mariana Islands|15.2|145.75
KH8,AH8,NH8,WH8|American Samoa|-14.3|-170.7
KH9,AH9,NH9,WH9|Wake Island|19.28|166.65
KH1,AH1,NH1,WH1|Baker & Howland|0.2|-176.5
KH3,AH3,NH3,WH3|Johnston Island|16.73|-169.53
KH4,AH4,NH4,WH4|Midway|28.2|-177.37
KH5,AH5,NH5,WH5|Palmyra & Jarvis|5.88|-162.08
KL,AL,NL,WL|Alaska|64.0|-150.0
KP4,NP4,WP4,KP3,NP3,WP3|Puerto Rico|18.2|-66.5
KP2,NP2,WP2|US Virgin Islands|18.3|-64.9
KP1,NP1,WP1|Navassa Island|18.4|-75.0
KP5,NP5,WP5|Desecheo Island|18.38|-67.48
KG4|Guantanamo Bay|19.9|-75.1
KC4|Antarctica|-77.8|166.7
VP8/S,VP8S|South Shetland|-62.0|-58.5
CY0|Sable Island|43.95|-60.0
CY9|St. Paul Island|47.2|-60.15
4U1I|ITU Geneva|46.2|6.1
4U1U|United Nations HQ|40.75|-73.97
1A|Sov. Mil. Order of Malta|41.9|12.48
"""

# Large countries: position per call area (digit) / grote landen per call-gebied
USA = {"1": (43.0, -71.5), "2": (41.5, -74.5), "3": (40.2, -77.0), "4": (34.5, -83.0),
       "5": (32.5, -97.0), "6": (36.8, -119.5), "7": (43.5, -114.0), "8": (41.0, -83.5),
       "9": (41.5, -88.5), "0": (41.5, -97.0)}
CANADA = {"1": (45.0, -63.0), "2": (47.0, -71.5), "3": (45.0, -79.0), "4": (50.0, -98.0),
          "5": (52.0, -106.0), "6": (53.0, -114.0), "7": (50.0, -123.0), "8": (62.5, -114.4),
          "9": (46.5, -66.0), "0": (64.0, -90.0)}
VK = {"1": (-35.3, 149.1), "2": (-32.5, 147.0), "3": (-37.0, 144.5), "4": (-22.5, 145.0),
      "5": (-30.5, 136.0), "6": (-26.0, 121.0), "7": (-42.0, 146.6), "8": (-19.5, 133.5)}
RUSSIA = {"1": (59.9, 30.3), "2": (54.7, 20.5), "3": (55.75, 37.6), "4": (53.2, 50.2),
          "5": (55.75, 37.6), "6": (45.0, 40.0), "7": (45.0, 40.0),
          "8": (52.3, 104.3), "9": (56.0, 73.0), "0": (62.0, 110.0)}

PFX = {}
for _line in _TABLE.strip().splitlines():
    _p, _n, _la, _lo = _line.split("|")
    for _x in _p.split(","):
        PFX[_x.strip().upper()] = (_n, float(_la), float(_lo))
_MAXLEN = max(len(k) for k in PFX)

SUFFIXES = {"P", "M", "MM", "AM", "QRP", "A", "R", "T", "B", "LH", "J", "E", "X", "PM", "N", "LGT"}


def base_call(call):
    """Prefix-bepalend deel van een roepnaam: PA/DL1ABC -> PA, DL1ABC/P -> DL1ABC, W1AW/6 -> W6AW."""
    c = call.upper().strip()
    parts = [p for p in c.split("/") if p]
    if not parts:
        return "", None
    area = None
    keep = []
    for p in parts:
        if p in SUFFIXES:
            continue
        if len(p) == 1 and p.isdigit():
            area = p
            continue
        keep.append(p)
    if not keep:
        return "", None
    if len(keep) == 1:
        core = keep[0]
    else:
        core = min(keep, key=len)          # kortste deel is meestal het prefix (PA/DL1ABC)
        if len(core) > 4 and len(keep[0]) <= len(keep[-1]):
            core = keep[0]
    if area is not None:
        m = next((i for i, ch in enumerate(core) if ch.isdigit()), None)
        if m is not None:
            core = core[:m] + area + core[m + 1:]
    return core, area


def _digit(core):
    return next((ch for ch in core if ch.isdigit()), None)


def lookup(call):
    """(country, lat, lon) uit het prefix, of None. Positie is een benadering."""
    if "/MM" in call.upper() or "/AM" in call.upper():
        return None
    core, _ = base_call(call)
    if not core:
        return None
    hit = None
    for n in range(min(_MAXLEN, len(core)), 0, -1):
        e = PFX.get(core[:n])
        if e:
            hit = (core[:n], e)
            break
    d = _digit(core)
    c0 = core[0]
    two = core[:2]
    # USA: K, W, N, AA-AK (if no more specific entry matched)
    us = c0 in "KWN" or (c0 == "A" and len(core) > 1 and "A" <= core[1] <= "K")
    if us and (hit is None or len(hit[0]) == 1 or hit[0][:1] in "KWN" and len(hit[0]) < 2):
        if hit is None or hit[1][0] not in ("Alaska",):
            la, lo = USA.get(d or "", (39.8, -98.6))
            return ("United States", la, lo)
    if two in ("VA", "VE", "VO", "VY", "CF", "CG", "CH", "CI", "CJ", "CK", "CY", "CZ", "VB",
               "VC", "VD", "VF", "VG", "XJ", "XK", "XL", "XM", "XN", "XO") and (hit is None or len(hit[0]) < 3):
        if two == "VO":
            return ("Canada", 48.5, -55.0) if d == "1" else ("Canada", 53.5, -61.0)
        if two == "VY":
            return ("Canada",) + {"1": (61.0, -135.0), "2": (46.3, -63.2)}.get(d, (64.0, -90.0))
        la, lo = CANADA.get(d or "", (52.0, -90.0))
        return ("Canada", la, lo)
    if two in ("VK", "AX", "VH", "VI", "VJ", "VL", "VM", "VN", "VZ") and (hit is None or len(hit[0]) < 3):
        la, lo = VK.get(d or "", (-25.0, 134.0))
        return ("Australia", la, lo)
    if c0 == "R" or (c0 == "U" and len(core) > 1 and "A" <= core[1] <= "I"):
        if hit is None or len(hit[0]) < 3:
            if d == "2" and len(core) > 3 and core[core.index("2") + 1] in "FK":
                return ("Kaliningrad", 54.7, 20.5)
            la, lo = RUSSIA.get(d or "", (55.75, 37.6))
            return ("Asiatic Russia" if d in ("8", "9", "0") else "European Russia", la, lo)
    if hit:
        return hit[1]
    return None
