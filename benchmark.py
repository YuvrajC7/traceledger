import tempfile,time,statistics
from pathlib import Path
from core import generate_trace,replay,minimize
from reporting import save_report

if __name__=='__main__':
    timings=[];passed=0;failures=0;ratios=[]
    with tempfile.TemporaryDirectory() as d:
        for seed in range(100):
            trace=generate_trace(seed,25)
            t=time.perf_counter();r=replay(Path(d)/f'{seed}.db',trace);timings.append((time.perf_counter()-t)*1000)
            passed+=int(r['state']['reference_matches'] and r['state']['balanced'] and r['state']['pending_events']==0)
            failures+=r['injected_failures'];small=minimize(trace);ratios.append(1-len(small)/len(trace))
    save_report({'histories':100,'unique_operations_per_history':25,'submitted_trace_events':5000,
                 'reference_matches':passed,'injected_exceptions':failures,
                 'mean_counterexample_reduction_percent':round(statistics.mean(ratios)*100,2),
                 'median_history_ms':round(statistics.median(timings),3),
                 'p95_history_ms':round(sorted(timings)[94],3),
                 'failure_model':'Exceptions at commit/ack boundaries and connection reopen; not OS power-failure testing.',
                 'minimizer_subject':'Deliberately seeded duplicate-application bug, not a production bug.'})
