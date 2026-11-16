import hashlib, json, platform, sys
from datetime import datetime, timezone
from pathlib import Path

def save_report(data):
    root=Path(__file__).parent
    data['environment']={'python':sys.version.split()[0], 'platform':platform.platform(), 'processor':platform.processor()}
    data['generated_at_utc']=datetime.now(timezone.utc).isoformat()
    data['scope']='Synthetic local benchmark, not production traffic or independent validation.'
    data['source_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.glob('*.py'))}
    (root/'reports').mkdir(exist_ok=True)
    (root/'reports/benchmark.json').write_text(json.dumps(data,indent=2),encoding='utf8')
    print(json.dumps(data,indent=2))
