from pathlib import Path
import sys
root = Path(sys.argv[1])
def edit(p, old, new):
    f = root / p
    s = f.read_text()
    assert s.count(old) == 1, (p, s.count(old))
    f.write_text(s.replace(old, new))
edit('lib/circuit-breaker.js', '    this.threshold = Math.max(1, threshold | 0);\n    this.openMs = Math.max(100, openMs | 0);\n    this.halfOpenProbes = Math.max(1, halfOpenProbes | 0);', '    this.configure({ threshold, openMs, halfOpenProbes });')
edit('lib/circuit-breaker.js', 'openedAt:number, probes:number}>', 'openedAt:number, probes:number, generation:number}>')
edit('lib/circuit-breaker.js', '  _entry(provider) {', '''  configure({ threshold = 5, openMs = 30_000, halfOpenProbes = 1 } = {}) {
    const integer = (value, fallback, min) => Number.isFinite(value)
      ? Math.max(min, Math.min(Number.MAX_SAFE_INTEGER, Math.floor(value))) : fallback;
    this.threshold = integer(threshold, 5, 1);
    this.openMs = integer(openMs, 30_000, 100);
    this.halfOpenProbes = integer(halfOpenProbes, 1, 1);
  }

  _entry(provider) {''')
edit('lib/circuit-breaker.js', 'openedAt: 0, probes: 0 };', 'openedAt: 0, probes: 0, generation: 0 };')
edit('lib/circuit-breaker.js', '''        e.probes = 0;
        return true;
      }
      return false;''', '''        e.probes = 0;
        e.generation += 1;
      } else {
        return false;
      }''')
edit('lib/circuit-breaker.js', '  onSuccess(provider) {', '''  // A permit is settled exactly once. Late outcomes from an older circuit
  // generation (or a removed provider) cannot close/reopen a newer circuit.
  acquire(provider) {
    if (!this.canRequest(provider)) return null;
    const entry = this._entry(provider);
    const generation = entry.generation;
    const probing = entry.state === BREAKER_HALF_OPEN;
    let settled = false;
    const settle = (fn) => {
      if (settled) return;
      settled = true;
      if (this._st.get(provider) === entry && entry.generation === generation) fn();
    };
    return {
      success: () => settle(() => this.onSuccess(provider)),
      failure: () => settle(() => this.onFailure(provider)),
      release: () => settle(() => {
        if (probing && entry.state === BREAKER_HALF_OPEN) {
          entry.probes = Math.max(0, entry.probes - 1);
        }
      }),
    };
  }

  onSuccess(provider) {''')
edit('lib/circuit-breaker.js', '''    e.fails = 0;
    e.probes = 0;
    e.state = BREAKER_CLOSED;''', '''    if (e.state !== BREAKER_CLOSED) e.generation += 1;
    e.fails = 0;
    e.probes = 0;
    e.openedAt = 0;
    e.state = BREAKER_CLOSED;''')
edit('lib/circuit-breaker.js', '''    const now = this._now();
    if (e.state === BREAKER_HALF_OPEN) {''', '''    const now = this._now();
    // In-flight failures arriving after opening must not extend the cooldown.
    if (e.state === BREAKER_OPEN) return e.state;
    if (e.state === BREAKER_HALF_OPEN) {''')
edit('lib/circuit-breaker.js', '''      e.fails = this.threshold;
      return e.state;''', '''      e.fails = this.threshold;
      e.probes = 0;
      e.generation += 1;
      return e.state;''')
edit('lib/circuit-breaker.js', '''      e.openedAt = now;
    }
    return e.state;''', '''      e.openedAt = now;
      e.probes = 0;
      e.generation += 1;
    }
    return e.state;''')
edit('lib/circuit-breaker.js', 'openedAt: e.openedAt || null', 'openedAt: e.state === BREAKER_CLOSED ? null : e.openedAt')
edit('lib/circuit-breaker.js', 'restore(snapshot) {', 'restore(snapshot, { preserveExisting = false } = {}) {')
edit('lib/circuit-breaker.js', "if (!snapshot || typeof snapshot !== 'object') return 0;", "if (!snapshot || typeof snapshot !== 'object' || Array.isArray(snapshot)) return 0;")
edit('lib/circuit-breaker.js', "      if (!e || typeof e !== 'object') continue;", "      if (!e || typeof e !== 'object' || Array.isArray(e)) continue;\n      if (preserveExisting && this._st.has(provider)) continue;")
edit('lib/circuit-breaker.js', '''        probes: 0,
      });''', '''        probes: 0,
        generation: 0,
      });''')
f = root / 'lib/circuit-breaker.js'
s = f.read_text()
f.write_text(s if s.endswith('\n') else s + '\n')
edit('lib/index.js', '    const switchCodes = cfg.switchCodes ?? DEFAULT_SWITCH_CODES;', '''    moduleBreaker.configure({
      threshold: cfg.circuitBreakerThreshold ?? 5,
      openMs: cfg.circuitBreakerOpenMs ?? 30000,
      halfOpenProbes: cfg.circuitBreakerHalfOpenProbes ?? 1,
    });
    const switchCodes = cfg.switchCodes ?? DEFAULT_SWITCH_CODES;''')
edit('lib/index.js', '    if (moduleBreaker) moduleBreaker.onFailure(provider);', '    if (buildRuntime().circuitBreakerEnabled && moduleBreaker) moduleBreaker.onFailure(provider);')
edit('lib/lifecycle.js', 'moduleBreaker.restore(snap.circuit);', 'moduleBreaker.restore(snap.circuit, { preserveExisting: true });')
edit('lib/rotate.js', '      let lastFailure = null;', '''      let lastFailure = null;
      const breaker = runtime0.circuitBreakerEnabled === false ? null : circuitBreaker;
      let activePermit = null;''')
edit('lib/rotate.js', '        if (circuitBreaker) circuitBreaker.onFailure(pool.base ?? options?.provider);', '        activePermit?.failure();')
edit('lib/rotate.js', '''      // #260: fail fast when provider circuit is open
      if (circuitBreaker && !circuitBreaker.canRequest(options.provider)) {
        logWarn(`[dsh-key-rotation] ${options.provider}: circuit open — skipping dispatch`);
        yield finishError('CIRCUIT_OPEN', `[dsh-key-rotation] provider '${options.provider}' circuit is open`);
        return;
      }

      for (let attempt = 0; attempt < attemptList.length; attempt++) {
        let yielded = false;''', '''      for (let attempt = 0; attempt < attemptList.length; attempt++) {
        activePermit = breaker ? breaker.acquire(options.provider) : null;
        if (breaker && !activePermit) {
          logWarn(`[dsh-key-rotation] ${options.provider}: circuit open — skipping dispatch`);
          yield finishError('CIRCUIT_OPEN', `[dsh-key-rotation] provider '${options.provider}' circuit is open`);
          return;
        }
        try {
        let yielded = false;''')
edit('lib/rotate.js', '                // cost tracking if provider returns usage.cost', '''                // Error/abort terminals are not successful responses. After a
                // content delta we may penalize, but must never replay the request.
                if (kind === 'error' || kind === 'aborted') {
                  if (kind === 'error' && isSwitchableError(failure, effectiveSwitchCodes)) {
                    penalizeRef(activeRef, code ?? 'UNKNOWN', message);
                  }
                  yield chunk;
                  return;
                }
                // cost tracking if provider returns usage.cost''')
edit('lib/rotate.js', '''                yield chunk;
                recordLatency(pool, reqStore);
                if (circuitBreaker) circuitBreaker.onSuccess(options.provider);
                return;''', '''                recordLatency(pool, reqStore);
                activePermit?.success();
                yield chunk;
                return;''')
edit('lib/rotate.js', '''            yield finishError(e?.code ?? 'TRANSPORT', String(e?.message ?? e));
            return;''', '''            if (yielded && isSwitchableError(e, effectiveSwitchCodes)) {
              penalizeRef(activeRef, e?.code ?? 'TRANSPORT', String(e?.message ?? e));
            }
            yield finishError(e?.code ?? 'TRANSPORT', String(e?.message ?? e));
            return;''')
edit('lib/rotate.js', '''          if (_pickedRef && yielded) {
            recordSuccess(pool, _pickedRef, now());
          }''', '''          if (yielded) {
            const activeRef = reqStore.pickedRef ?? _pickedRef ?? pool.state.lastUsed;
            if (activeRef) recordSuccess(pool, activeRef, now());
            recordLatency(pool, reqStore);
            activePermit?.success();
          }''')
edit('lib/rotate.js', '''        }
      }

      // pool exhausted''', '''        }
        } finally {
          // Also runs on consumer return(), abort, empty EOF and local errors.
          activePermit?.release();
        }
      }

      // pool exhausted''')
f = root / 'lib/rotate.js'
s = f.read_text()
start = s.index('        try {\n        let yielded')
end = s.index('        } finally {\n          // Also runs', start)
s = s[:start] + s[start:end].split('\n', 1)[0] + '\n' + ''.join('  ' + line + '\n' if line else '\n' for line in s[start:end].split('\n')[1:-1]) + s[end:]
f.write_text(s)
(root / 'test').mkdir(exist_ok=True)
(root / 'test/circuit-stream-lifecycle.test.mjs').write_text((Path(__file__).parent / 'tests/circuit-stream-lifecycle.test.mjs').read_text())
