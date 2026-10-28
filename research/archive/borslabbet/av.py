import json,sys,urllib.request
UA={"User-Agent":"SwingEdge-research/1.0","Content-Type":"application/json","Accept":"application/json"}
def search(q,typ=None,n=8):
    body={"query":q,"searchFilter":{"types":[typ] if typ else []},"pagination":{"from":0,"size":n}}
    r=urllib.request.Request("https://www.avanza.se/_api/search/filtered-search",data=json.dumps(body).encode(),headers=UA)
    return json.load(urllib.request.urlopen(r,timeout=30))
def get(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=30))
if __name__=="__main__":
    for q in sys.argv[1:]:
        res=search(q)
        for h in res.get("hits",[])[:8]:
            print(q,"|",h.get("type"),h.get("orderBookId"),h.get("title"),h.get("price",{}).get("last") if isinstance(h.get("price"),dict) else "")
