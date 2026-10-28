import av,sys,json
qs=sys.argv[1:]
seen=set()
for q in qs:
    try: res=av.search(q,"FUND",10)
    except Exception as e: print(q,"ERR",e); continue
    for h in res.get("hits",[]):
        i=h.get("orderBookId")
        if not i or i in seen: continue
        seen.add(i)
        try: g=av.get(f"https://www.avanza.se/_api/fund-guide/guide/{i}")
        except Exception as e: continue
        print(f"{q[:14]:14}|{i}|{g['name'][:48]:48}|{g.get('startDate')}|fee {g.get('productFee')}|idx {g.get('indexFund')}|{g.get('primaryBenchmark') or ''}"[:200])
