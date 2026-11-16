import concurrent.futures
import pytest
from fastapi.testclient import TestClient
from app import app
from core import Ledger, InjectedFailure, generate_trace, replay, minimize, duplicate_bug

@pytest.mark.parametrize('fault',['before_commit','after_commit'])
def test_crash_and_retry(tmp_path,fault):
    l=Ledger(tmp_path/'x.db')
    with pytest.raises(InjectedFailure):l.transfer('a','x','y',123,fault)
    l=Ledger(tmp_path/'x.db'); l.transfer('a','x','y',123); l.dispatch()
    assert l.inspect()['balances']=={'x':-123,'y':123}
    assert l.inspect()['journal_entries']==2

def test_conflicting_payload(tmp_path):
    l=Ledger(tmp_path/'x.db'); l.transfer('a','x','y',1)
    with pytest.raises(ValueError):l.transfer('a','x','y',2)

def test_concurrent_same_key(tmp_path):
    l=Ledger(tmp_path/'x.db')
    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        values=list(pool.map(lambda _:l.transfer('same','a','b',50),range(32)))
    assert sum(not v['deduplicated'] for v in values)==1
    assert l.inspect()['journal_entries']==2

def test_delivery_ack_failure(tmp_path):
    l=Ledger(tmp_path/'x.db');l.transfer('a','x','y',1)
    with pytest.raises(InjectedFailure):l.dispatch(True)
    l.dispatch();assert l.inspect()['consumer_events']==1

@pytest.mark.parametrize('seed',range(10))
def test_reference_and_minimizer(tmp_path,seed):
    trace=generate_trace(seed,12)
    assert replay(tmp_path/'x.db',trace)['state']['reference_matches']
    small=minimize(trace)
    assert duplicate_bug(small)
    assert all(not duplicate_bug(small[:i]+small[i+1:]) for i in range(len(small)))

def test_api_limits():
    client=TestClient(app)
    assert client.post('/demo',json={'operations':101}).status_code==422
    assert client.post('/demo',json={'operations':5}).json()['state']['balanced']
