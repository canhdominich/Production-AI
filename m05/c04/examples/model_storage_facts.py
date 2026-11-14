import json

from _dock import sh

img = json.loads(sh("docker", "image", "inspect", "ollama/ollama").stdout)[0]
print(f"ollama/ollama image (runtime only):   {img['Size'] / 1e9:5.2f} GB")
inspect = json.loads(sh("docker", "inspect", "anhti-ollama").stdout)[0]
for m in inspect["Mounts"]:
    print(f"mount: type={m['Type']:<6} destination={m['Destination']}")
print("size of /root/.ollama in the volume:  ", sh("docker", "exec", "anhti-ollama", "du", "-sh", "/root/.ollama").stdout.split()[0])
rows = sh("docker", "exec", "anhti-ollama", "ollama", "list").stdout.strip().splitlines()
print("ollama list:")
for row in rows:
    cols = row.split()
    print("  ", cols[0].ljust(24), " ".join(cols[2:4]) if cols[0] != "NAME" else "SIZE")
