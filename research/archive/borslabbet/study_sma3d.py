"""SMA150 med tredagarsregeln (byte först efter tre stängningar i rad på nya sidan) mot daglig SMA150, NR7Trend-Krypto
och köp och behåll på samma 22 USD-kryptor och fönster som study_nr7_vs_sma.py. 0,40 % per sida, kontanter 0 %."""
import sys, json, math, datetime
sys.stdout.reconfigure(encoding="utf-8")
from study_nr7_vs_sma import YH, yahoo, nr7

def bt(C, n=150, confirm=1, cost=0.004):
    s, eq, pos, streak, peak, dd, tr = 0.0, 1.0, False, 0, 1.0, 0.0, 0
    for i, c in enumerate(C):
        if i > n - 1:
            eq *= 1 + ((c / C[i - 1] - 1) if pos else 0.0); peak = max(peak, eq); dd = min(dd, eq / peak - 1)
        s += c
        if i >= n: s -= C[i - n]
        if i >= n - 1:
            flip = (c < s / n) if pos else (c > s / n)
            streak = streak + 1 if flip else 0
            if streak >= confirm: pos = not pos; streak = 0; eq *= 1 - cost; tr += 1
    return eq - 1, dd, tr

print(f"\n{'Krypto':6} {'år':>4} | {'SMA150 daglig':>22} | {'SMA150 3 dagar':>22} | {'NR7':>6} | {'B&H':>8}")
print(f"{'':6} {'':>4} | {'tot':>8} {'maxDD':>6} {'aff/år':>6} | {'tot':>8} {'maxDD':>6} {'aff/år':>6} | {'tot':>6} | {'tot':>8}")
A = []
for k, sym in YH.items():
    D, C = zip(*yahoo(sym)); C = list(C); yrs = (len(C) - 150) / 365.25
    start = datetime.date.fromisoformat(D[150])
    e = 1.0
    for d, w in nr7.get(k, []):
        if d >= start and w <= 1000: e *= 1 + w / 100
    d1, d3, bh = bt(C), bt(C, confirm=3), C[-1] / C[150] - 1
    A.append((k, yrs, d1, d3, e - 1, bh))
    print(f"{k:6} {yrs:4.1f} | {d1[0]*100:7.0f}% {d1[1]*100:5.0f}% {d1[2]/yrs:6.1f} | {d3[0]*100:7.0f}% {d3[1]*100:5.0f}% {d3[2]/yrs:6.1f} | {(e-1)*100:5.0f}% | {bh*100:7.0f}%")
ann = lambda x, y: (1 + x) ** (1 / y) - 1 if x > -1 else -1.0
med = lambda xs: sorted(xs)[len(xs) // 2]
print(f"\nMedian per år: daglig {med([ann(a[2][0], a[1]) for a in A])*100:.0f} %, 3 dagar {med([ann(a[3][0], a[1]) for a in A])*100:.0f} %, "
      f"NR7 {med([ann(a[4], a[1]) for a in A])*100:.0f} %, B&H {med([ann(a[5], a[1]) for a in A])*100:.0f} %")
print(f"Median maxDD: daglig {med([a[2][1] for a in A])*100:.0f} %, 3 dagar {med([a[3][1] for a in A])*100:.0f} % | "
      f"affärer/år median: daglig {med([a[2][2]/a[1] for a in A]):.1f}, 3 dagar {med([a[3][2]/a[1] for a in A]):.1f}")
print(f"3 dagar bättre än daglig på {sum(a[3][0] > a[2][0] for a in A)} av {len(A)}, bättre än B&H på {sum(a[3][0] > a[5] for a in A)}, "
      f"bättre än NR7 på {sum(a[3][0] > a[4] for a in A)}")
