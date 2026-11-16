"""Single-currency transfer journal and deterministic failure replay."""
import hashlib
import json
import random
import sqlite3
from pathlib import Path


class InjectedFailure(RuntimeError):
    pass

class ClosingConnection(sqlite3.Connection):
    def __exit__(self,*args):
        try:return super().__exit__(*args)
        finally:self.close()


class Ledger:
    def __init__(self, path):
        self.path = str(path)
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS commands(id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS journal(id INTEGER PRIMARY KEY, operation TEXT NOT NULL,
              account TEXT NOT NULL, amount INTEGER NOT NULL,
              FOREIGN KEY(operation) REFERENCES commands(id));
            CREATE TABLE IF NOT EXISTS outbox(id TEXT PRIMARY KEY, payload TEXT NOT NULL, delivered INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS inbox(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            ''')

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10, factory=ClosingConnection)
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA synchronous=FULL')
        return db

    def transfer(self, operation, source, destination, amount, fault=None):
        if (not all(isinstance(x, str) and 0 < len(x) <= 100 for x in [operation, source, destination])
                or source == destination or type(amount) is not int or not 0 < amount <= 10**12):
            raise ValueError('Distinct accounts, nonempty IDs, and positive integer minor units required')
        payload = json.dumps([source, destination, amount], separators=(',', ':'))
        fingerprint = hashlib.sha256(payload.encode()).hexdigest()
        db = self.connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT fingerprint FROM commands WHERE id=?', (operation,)).fetchone()
            if old:
                if old[0] != fingerprint:
                    raise ValueError('Idempotency key reused with a different payload')
                db.commit()
                return {'id': operation, 'deduplicated': True}
            db.execute('INSERT INTO commands VALUES (?,?)', (operation, fingerprint))
            db.executemany('INSERT INTO journal(operation,account,amount) VALUES (?,?,?)',
                           [(operation, source, -amount), (operation, destination, amount)])
            db.execute('INSERT INTO outbox(id,payload) VALUES (?,?)', (operation, payload))
            if fault == 'before_commit':
                raise InjectedFailure('Failure before database commit')
            db.commit()
            if fault == 'after_commit':
                raise InjectedFailure('Commit succeeded; response was lost')
            return {'id': operation, 'deduplicated': False}
        finally:
            db.close()  # rolls back an uncommitted transaction

    def dispatch(self, fail_after_delivery=False):
        """Inbox models an idempotent local consumer, not a real payment processor."""
        with self.connect() as db:
            pending = db.execute('SELECT id,payload FROM outbox WHERE delivered=0 ORDER BY id').fetchall()
        for operation, payload in pending:
            with self.connect() as sink:
                sink.execute('INSERT OR IGNORE INTO inbox VALUES (?,?)', (operation, payload))
            if fail_after_delivery:
                raise InjectedFailure('Consumer committed; producer acknowledgement lost')
            with self.connect() as producer:
                producer.execute('UPDATE outbox SET delivered=1 WHERE id=?', (operation,))
        return len(pending)

    def inspect(self):
        with self.connect() as db:
            balances = dict(db.execute('SELECT account,SUM(amount) FROM journal GROUP BY account'))
            bad = db.execute('SELECT operation FROM journal GROUP BY operation HAVING SUM(amount)!=0 OR COUNT(*)!=2').fetchall()
            return {'balances': balances, 'balanced': not bad,
                    'commands': db.execute('SELECT COUNT(*) FROM commands').fetchone()[0],
                    'journal_entries': db.execute('SELECT COUNT(*) FROM journal').fetchone()[0],
                    'consumer_events': db.execute('SELECT COUNT(*) FROM inbox').fetchone()[0],
                    'pending_events': db.execute('SELECT COUNT(*) FROM outbox WHERE delivered=0').fetchone()[0]}


def generate_trace(seed=42, count=20):
    rng = random.Random(seed)
    trace = []
    for i in range(count):
        event = {'id': f'op-{i}', 'amount': rng.randint(1, 10000),
                 'fault': rng.choice([None, 'before_commit', 'after_commit'])}
        trace.append(event)
        trace.append({**event, 'fault': None})  # retry every operation, including successful ones
    rng.shuffle(trace)
    return trace


def replay(path, trace):
    ledger = Ledger(path)
    failures = deduplicated = 0
    reference = {}
    for event in trace:
        try:
            r = ledger.transfer(event['id'], 'payer', 'merchant', event['amount'], event.get('fault'))
            deduplicated += r['deduplicated']
        except InjectedFailure:
            failures += 1
            ledger = Ledger(path)  # reopen persistent state
        reference[event['id']] = event['amount']
    # Explicit retry guarantees all requested operations eventually commit.
    for operation, amount in reference.items():
        ledger.transfer(operation, 'payer', 'merchant', amount)
    try:
        ledger.dispatch(fail_after_delivery=True)
    except InjectedFailure:
        ledger = Ledger(path)
    ledger.dispatch()
    state = ledger.inspect()
    expected = sum(reference.values())
    state['reference_matches'] = (state['balances'].get('merchant', 0) == expected
                                  and state['commands'] == len(reference)
                                  and state['consumer_events'] == len(reference))
    return {'state': state, 'injected_failures': failures, 'deduplicated_calls': deduplicated,
            'expected_merchant_minor_units': expected, 'trace': trace}


def duplicate_bug(trace):
    """Deliberately faulty oracle: applies every delivery instead of every unique ID."""
    total = sum(x['amount'] for x in trace)
    reference = sum({x['id']: x['amount'] for x in trace}.values())
    return total != reference


def minimize(trace, predicate=duplicate_bug):
    """Delta debugging, followed by a 1-minimality sweep."""
    if not predicate(trace):
        raise ValueError('Trace does not reproduce the fault')
    current = list(trace)
    granularity = 2
    while len(current) >= 2:
        size = (len(current) + granularity - 1) // granularity
        for start in range(0, len(current), size):
            candidate = current[:start] + current[start + size:]
            if candidate and predicate(candidate):
                current = candidate
                granularity = max(2, granularity - 1)
                break
        else:
            if granularity >= len(current):
                break
            granularity = min(len(current), granularity * 2)
    return current
