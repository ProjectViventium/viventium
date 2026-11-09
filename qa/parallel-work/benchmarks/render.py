"""Render the benchmark guide from sanitized measurements and the shared source SVG."""
from pathlib import Path
import html
import json
import re
ROOT = Path(__file__).resolve().parents[3]
DATA = json.loads(Path(__file__).with_name('results.json').read_text())
G = {(g['variant'], g['case']): g for g in DATA['groups']}
V = DATA['variants']
esc = html.escape

def timing(stat):
    if not stat:
        return 'No completed sample'
    return f'<span class="timing">{stat["median_s"]:.2f} s</span><small>{stat["min_s"]:.2f}–{stat["max_s"]:.2f} s · n={stat["n"]}</small>'

def row(key):
    variant = V[key]
    natural, handoff, negative = (G.get((key, c)) for c in ('full_natural', 'full_handoff', 'full_reply'))
    if natural:
        samples = f'Reply {natural["completed"]}/{natural["attempts"]}'
    else:
        samples = 'Rejected before full frame' if key == 'sol-api-rejected' else 'No full-frame sample'
    if handoff and negative:
        samples += f'<small>Yes {handoff.get("expected_flag", 0)}/{handoff["completed"]} · No {negative.get("expected_flag", 0)}/{negative["completed"]}</small>'
    if handoff and negative and (handoff['attempts'] != handoff['completed'] or negative['attempts'] != negative['completed']):
        samples += f'<small>Transport failures: yes {handoff["attempts"]-handoff["completed"]}, no {negative["attempts"]-negative["completed"]}</small>'
    return '<tr><td><strong>'+esc(variant['label'])+'</strong><small>'+esc(variant['setting'])+'</small></td><td>'+samples+'</td><td>'+timing(natural['first_text'] if natural else None)+'</td><td>'+timing(handoff['completion'] if handoff else None)+'</td><td>'+esc(variant['note'])+'</td></tr>'

def table(provider, keys):
    icon = provider.lower()
    title = 'Anthropic · Opus 5 only' if provider == 'Anthropic' else provider
    return f'<div class="provider-head"><img src="assets/fast-queen/{icon}.svg" class="{icon}-mark" alt=""><h3>{title}</h3></div><p class="mobile-hint">Swipe to see all timings.</p><div class="table-scroll" tabindex="0" role="region" aria-label="{provider} comparison"><table><caption>Full frame, about 200k characters. Median and observed range. Separate reply and decision probes.</caption><thead><tr><th scope="col">Account route</th><th scope="col">Samples</th><th scope="col">First reply text</th><th scope="col">Complete flag</th><th scope="col">What this proves</th></tr></thead><tbody>'+''.join(row(k) for k in keys)+'</tbody></table></div>'

block = '<div class="mini-grid"><article class="card"><p class="label">Matrix attempts</p><div class="metric">'+str(DATA['sample_total'])+'</div><p class="muted">'+str(DATA['transport_completed'])+' complete. Failures and cold seed retained.</p></article><article class="card"><p class="label">Quota-native candidate</p><div class="metric">Warm Opus 5</div><p class="muted">Isolated retained session. Not Direct.</p></article><article class="card"><p class="label">Official Direct tested</p><div class="metric">ChatGPT sign-in</div><p class="muted">Actual app grant and plan-quota inference.</p></article></div>'
block += table('OpenAI', ['sol-native','sol-official-direct','sol-api-rejected','gpt52-api-low','gpt52-api-none'])
block += '<p class="bench-verdict"><strong>OpenAI:</strong> official ChatGPT Direct is the preferred Direct candidate. Keep the native route available. Sol rejects thinking <code>none</code>; the API-credit model is different.</p>'
block += table('Anthropic', ['opus-native-warm','opus-native-low','opus-native-off','opus-direct-low','opus-direct-off'])
block += '<p class="bench-verdict"><strong>Anthropic:</strong> warm native Opus 5 is the strongest documented quota candidate in this small sample. The saved Direct adapter is fast, with a separate compatibility/support caveat. Warm reuse is now verified locally on Telegram and browser Voice; see the separate channel receipt. Thinking off gave no consistent gain.</p><p class="note">A flag here means “background action needed.” It is not a receipt that work started. Flag rates use completed decisions; transport failures are counted separately. Correct flags do not clear the remaining quality gate. Warm and fresh-session rows differ in startup, history and cache state; no universal fastest-route claim is made.</p>'
context='<div class="table-scroll" tabindex="0" role="region" aria-label="Context-size comparison"><table><thead><tr><th>Route / setting</th><th>60k frame: first reply</th><th>200k frame: first reply</th></tr></thead><tbody>'
for key in ['sol-native','sol-official-direct','gpt52-api-low','opus-native-low','opus-native-off','opus-direct-low','opus-direct-off']:
    small, full = (G.get((key,c)) for c in ['cognition_natural','full_natural'])
    context += '<tr><td>'+esc(V[key]['label'])+'<small>'+esc(V[key]['setting'])+'</small></td><td>'+timing(small['first_text'] if small else None)+'</td><td>'+timing(full['first_text'] if full else None)+'</td></tr>'
context += '</tbody></table></div><p class="note">No consistent context-size effect is established. Fixed order, cache state and different outputs confound the comparison. The warm seed is reported separately in the data; later warm turns retain earlier probe turns.</p>'
for rel,sections in [('docs/architecture/fast-queen.html',{'FLOW':(ROOT/'docs/architecture/assets/fast-queen/flow.svg').read_text(),'BENCHMARKS':block,'CONTEXT':context})]:
    p=ROOT/rel;text=p.read_text()
    for marker,value in sections.items():
        text,n=re.subn(rf'<!-- {marker}:START -->.*?<!-- {marker}:END -->',lambda _:f'<!-- {marker}:START -->{value}<!-- {marker}:END -->',text,flags=re.S)
        if n!=1:raise ValueError(f'Expected one {marker} region in {rel}')
    p.write_text(text)
print('Rendered shared diagram and measured tables')
