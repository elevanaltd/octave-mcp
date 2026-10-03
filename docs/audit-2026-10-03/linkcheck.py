import re, os, sys
root = "/home/user/octave-mcp"
files = ["README.md","AGENTS.oct.md","docs/guides/README.md","docs/research/README.md","CONTRIBUTING.md","docs/research/mythology-evidence-synthesis.oct.md","docs/guides/mythological-compression.md","examples/README.md","tools/README.md","docs/usage.md","docs/api.md","docs/mcp-configuration.md","docs/guides/development-setup.md"]
rows=[]
for f in files:
    p=os.path.join(root,f)
    txt=open(p,encoding="utf-8").read()
    for i,line in enumerate(txt.splitlines(),1):
        # markdown links
        for m in re.finditer(r'\]\(([^)\s#]+)(#[^)]*)?\)', line):
            tgt=m.group(1)
            if tgt.startswith(("http","mailto")): continue
            full=os.path.normpath(os.path.join(os.path.dirname(p),tgt))
            rows.append((f,i,tgt,"OK" if os.path.exists(full) else "MISSING"))
        # quoted paths in oct.md
        if f.endswith(".oct.md") or f=="AGENTS.oct.md":
            for m in re.finditer(r'"((?:docs|src|specs|tests|README)[^"§]*)"?', line):
                tgt=m.group(1).split("§")[0].rstrip('"').rstrip("/")
                if "*" in tgt or "[" in tgt: continue
                full=os.path.join(root,tgt)
                rows.append((f,i,tgt,"OK" if os.path.exists(full) else "MISSING"))
out=open("/tmp/claude-0/-home-user-octave-mcp/7c2eca1b-5373-54c5-8c52-34495cf0cf02/scratchpad/docs/linkcheck.tsv","w")
out.write("file\tline\ttarget\tstatus\n")
for r in rows: out.write("\t".join(map(str,r))+"\n")
out.close()
miss=[r for r in rows if r[3]=="MISSING"]
print(f"total links {len(rows)}, missing {len(miss)}")
for r in miss: print(*r, sep="\t")
