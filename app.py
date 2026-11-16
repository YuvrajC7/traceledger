import tempfile
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from core import generate_trace, replay, minimize
from ui import page

app=FastAPI(title='TraceLedger', version='0.1.0')
class Config(BaseModel):
    seed:int=42
    operations:int=Field(default=20,ge=1,le=100)

@app.get('/',response_class=HTMLResponse)
def home():
    return page('TraceLedger','Replay transfer failures and inspect balanced journals, deduplication, and minimized counterexamples.',{'seed':42,'operations':20})

@app.post('/demo')
def demo(config:Config):
    trace=generate_trace(config.seed,config.operations)
    with tempfile.TemporaryDirectory() as d:
        result=replay(Path(d)/'ledger.db',trace)
    result['minimal_duplicate_counterexample']=minimize(trace)
    return result
