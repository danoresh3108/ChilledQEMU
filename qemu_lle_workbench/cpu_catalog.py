"""Friendly CPU choices. Retail families are approximate architecture mappings."""

INTEL_GENERATIONS = [
    ('1 — Westmere', 'Westmere'), ('2 — Sandy Bridge', 'SandyBridge'),
    ('3 — Ivy Bridge', 'IvyBridge'), ('4 — Haswell', 'Haswell'),
    ('5 — Broadwell', 'Broadwell'), ('6 — Skylake', 'Skylake-Client'),
    ('7 — Kaby Lake, Skylake-derived (approx.)', 'Skylake-Client'),
    ('8 — Coffee Lake, Skylake-derived (approx.)', 'Skylake-Client'),
    ('9 — Coffee Lake Refresh, Skylake-derived (approx.)', 'Skylake-Client'),
    ('10 — Comet Lake, Skylake-derived (approx.)', 'Skylake-Client'),
]
RYZEN_SERIES = [
    ('1000 — Zen (approx.)', 'EPYC'),
    ('2000 — Zen/Zen+ (approx.)', 'EPYC'),
    ('3000 — Zen 2 desktop, except APUs (approx.)', 'EPYC-Rome'),
    ('5000 — Zen 3 desktop (approx.)', 'EPYC-Milan'),
    ('7000 — Zen 4 desktop (approx.)', 'EPYC-Genoa'),
    ('9000 — Zen 5 desktop (approx.)', 'EPYC-Turin'),
]
CPU_CATALOG = {
    'Intel Core i3': INTEL_GENERATIONS,
    'Intel Core i5': INTEL_GENERATIONS,
    'Intel Core i7': INTEL_GENERATIONS,
    'Intel Core i9': INTEL_GENERATIONS[-2:],
    'Intel Xeon': [(name, name) for name in (
        'Skylake-Server', 'Cascadelake-Server', 'Cooperlake',
        'Icelake-Server', 'SapphireRapids', 'GraniteRapids')],
    'AMD Ryzen 3': RYZEN_SERIES[:4],
    'AMD Ryzen 5': RYZEN_SERIES,
    'AMD Ryzen 7': RYZEN_SERIES,
    'AMD Ryzen 9': RYZEN_SERIES[2:],
    'AMD EPYC': [('7001 — Naples / Zen', 'EPYC'), ('7002 — Rome / Zen 2', 'EPYC-Rome'),
        ('7003 — Milan / Zen 3', 'EPYC-Milan'), ('9004 — Genoa / Zen 4', 'EPYC-Genoa'),
        ('9005 — Turin / Zen 5', 'EPYC-Turin')],
    'AMD legacy': [('Athlon', 'athlon'), ('Opteron G1', 'Opteron_G1'),
        ('Opteron G2', 'Opteron_G2'), ('Opteron G3', 'Opteron_G3'),
        ('Opteron G4', 'Opteron_G4'), ('Opteron G5', 'Opteron_G5')],
}
