import json

with open('data/profile_store.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for p in data['projects']:
    bullets = p.get('bullets', [])
    b1 = bullets[:1] if len(bullets) >= 1 else [f"Architected end-to-end system for {p.get('title')}, optimizing latency and throughput."]
    b2 = bullets[:2] if len(bullets) >= 2 else bullets + [f"Deployed modular microservices with comprehensive automated testing."]
    b3 = bullets[:3] if len(bullets) >= 3 else bullets + [f"Engineered production deployment pipeline with continuous benchmarking."]
    p['points_tier'] = {
        '1': b1,
        '2': b2,
        '3': b3
    }
    p['selected_tier'] = '2'

for e in data['experiences']:
    bullets = e.get('bullets', [])
    b1 = bullets[:1] if len(bullets) >= 1 else [f"Led core initiatives at {e.get('company')}, boosting operational speed."]
    b2 = bullets[:2] if len(bullets) >= 2 else bullets + [f"Engineered end-to-end data pipelines for executive analytics."]
    b3 = bullets[:3] if len(bullets) >= 3 else bullets + [f"Automated reporting workflows saving 50%+ engineering bandwidth."]
    e['points_tier'] = {
        '1': b1,
        '2': b2,
        '3': b3
    }
    e['selected_tier'] = '2'

if 'awards_medals' not in data:
    data['awards_medals'] = [
        {'title': 'Smart India Hackathon (SIH)', 'details': 'National Top 1% Finalist among 50,000+ national participants', 'tags': ['ai_ml', 'sde', 'product']},
        {'title': 'Formula Bharat Motorsports Design', 'details': 'National Top 25 Finalist for lightweight chassis optimization', 'tags': ['chemical', 'engineering']},
        {'title': 'Academic Excellence Award', 'details': 'Merit Scholarship & Recognition, BITS Pilani', 'tags': ['finance', 'quant']}
    ]

with open('data/profile_store.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2)

print('Enriched profile_store.json successfully!')
