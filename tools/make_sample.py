#!/usr/bin/env python3
"""Generate docs/voorbeeld.adi with fictitious example contacts (for testing and screenshots)."""
import random, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import qso_map as qm
random.seed(7)
calls = ["DL1ABC","DK5XY","G4ABC","M0XYZ","F5ABC","ON4ABC","OZ1ABC","SM5ABC","LA9ABC","OH2ABC","SP3ABC","OK1ABC",
 "HA5ABC","I2ABC","IK8XYZ","EA3ABC","EA8ABC","CT1ABC","EI5ABC","GM3ABC","GW4ABC","HB9ABC","OE3ABC","S51ABC","9A2ABC",
 "YO3ABC","LZ1ABC","SV1ABC","TA1ABC","UR5ABC","UA3ABC","UA9ABC","UA0ABC","4X1ABC","A65ABC","VU2ABC","JA1ABC","JA6XYZ",
 "BY1ABC","HL2ABC","YB1ABC","9M2ABC","VK2ABC","VK6ABC","ZL2ABC","ZS6ABC","5Z4ABC","CN8ABC","EA9ABC","W1ABC","K2ABC",
 "W4ABC","N5ABC","K6ABC","W7ABC","K9ABC","W0ABC","VE3ABC","VE7ABC","VO1ABC","KP4ABC","XE1ABC","PY2ABC","LU1ABC","CE3ABC",
 "HK3ABC","YV5ABC","KH6ABC","KL7ABC","TF3ABC","OX3ABC","D44ABC","3B8ABC","FR4ABC","PJ2ABC","VP8ABC","HC1ABC","OA4ABC",
 "PA3ABC","PD0XYZ","PE1ABC","PA5ABC","LX1ABC","ES1ABC","YL2ABC","LY1ABC","EU1ABC","4L1ABC","EX8ABC","UN7ABC"]
w = {c: (8 if c[:2] in ("DL","DK","G4","M0","F5","ON","PA","PD","PE","OZ","SP","OK","I2","EA","HB","OE","SM","UR") else 2) for c in calls}
bands = [("40m",7.02,"CW",8),("20m",14.03,"CW",10),("20m",14.074,"FT8",14),("15m",21.074,"FT8",6),("10m",28.074,"FT8",6),
         ("80m",3.55,"CW",4),("17m",18.1,"FT8",5),("12m",24.915,"FT8",3),("30m",10.136,"FT8",4),("6m",50.313,"FT8",2),("40m",7.074,"FT8",8)]
recs = []
day = 0
for n in range(420):
    c = random.choices(calls, weights=[w[x] for x in calls])[0]
    b, f, m, _ = random.choices(bands, weights=[x[3] for x in bands])[0]
    pf = qm.prefixes.lookup(c)
    la, lo = pf[1] + random.uniform(-3, 3), pf[2] + random.uniform(-4, 4)
    if c[:2] in ("W1","K2","W4","N5","K6","W7","K9","W0","VE","VK","UA","JA","PY","LU"):
        la, lo = pf[1] + random.uniform(-4, 4), pf[2] + random.uniform(-7, 7)
    la = max(min(la, 80), -80)
    day += random.choice([0,0,0,0,1,1,2,3])
    d = 20240101 + 0
    import datetime
    dt = datetime.datetime(2023,9,2) + datetime.timedelta(days=day*1.9, minutes=random.randint(0, 1400))
    call = c[:max(i for i, ch in enumerate(c) if ch.isdigit()) + 1] + "".join(random.choice("ABCDEFGHJKLMNPRSTUVWXYZ") for _ in range(random.choice([2,3])))
    r = {"CALL": call, "QSO_DATE": dt.strftime("%Y%m%d"), "TIME_ON": dt.strftime("%H%M%S"), "BAND": b,
         "FREQ": f"{f + random.uniform(0,0.003):.5f}", "MODE": m,
         "RST_SENT": "599" if m=="CW" else f"{random.randint(-20,5):+03d}", "RST_RCVD": "599" if m=="CW" else f"{random.randint(-20,5):+03d}",
         "MY_GRIDSQUARE": "JO22mp", "STATION_CALLSIGN": "PD3RAH"}
    if random.random() > 0.12:
        r["GRIDSQUARE"] = qm.latlon_to_grid(la, lo, 6 if m=="CW" else 4)[:6 if m=="CW" else 4]
    recs.append(r)
qm.write_adif(sys.argv[1] if len(sys.argv) > 1 else "docs/voorbeeld.adi", recs)
print(len(recs))
