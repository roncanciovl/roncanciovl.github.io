"""Deterministic public HTML/JSON/JSON-LD export from index.html only.

No network, private profile, environment variable or credential is read.
Every top-level entity and every explicit @id relationship is exported.
"""
import argparse
import copy
import hashlib
import html
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
BASE = 'https://roncanciovl.github.io/'
PERSON_ID = BASE + '#henry-roncancio'
COMPANY_ID = 'https://www.economiaia.business/#organization'


class JsonLdParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active, self.parts, self.documents = False, [], []

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.active = dict(attrs).get('type') == 'application/ld+json'
            self.parts = []

    def handle_endtag(self, tag):
        if tag == 'script' and self.active:
            self.documents.append(json.loads(''.join(self.parts)))
            self.active = False

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)


def values(value):
    return value if isinstance(value, list) else [value]


def read_graph(source):
    parser = JsonLdParser()
    parser.feed(source)
    graph = []
    for doc in parser.documents:
        graph.extend(doc.get('@graph', [doc]))
    if not graph:
        raise ValueError('No public JSON-LD found')
    return graph


def profile_name(url):
    host = urlparse(url).hostname
    return {'github.com': 'GitHub', 'orcid.org': 'ORCID',
            'scholar.google.com': 'Google Scholar', 'www.linkedin.com': 'LinkedIn',
            'scienti.minciencias.gov.co': 'CvLAC'}.get(host, host or url)


def project(graph):
    graph = copy.deepcopy(graph)
    by_id = {}
    for item in graph:
        identifier = item.get('@id')
        if not identifier or not item.get('@type'):
            raise ValueError('Every top-level entity needs @id and @type')
        if identifier in by_id:
            raise ValueError(f'Duplicate ID: {identifier}')
        by_id[identifier] = item
    person = by_id[PERSON_ID]
    profile = next(n for n in graph if n['@type'] == 'ProfilePage')
    reviewed = profile['dateModified']
    digest = hashlib.sha256(json.dumps(graph, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    nodes, relations = [], []
    for item in graph:
        node = {'id': item['@id'], 'type': item['@type'],
                'name': item.get('name', item.get('roleName', item['@id'])),
                'url': item.get('url', item['@id']), 'description': item.get('description', ''),
                'sources': [BASE], 'reviewed_at': reviewed,
                'properties': {k: v for k, v in item.items() if not k.startswith('@')}}
        if 'identifier' in item:
            node['identifiers'] = values(item['identifier'])
        if item['@type'] == 'Dataset' and item.get('sameAs'):
            node['concept_doi'] = values(item['sameAs'])[0]
        nodes.append(node)
        for prop, raw in item.items():
            for target in values(raw):
                if isinstance(target, dict) and '@id' in target:
                    if target['@id'] not in by_id:
                        raise ValueError(f'Unresolved reference: {item["@id"]} {prop} {target["@id"]}')
                    relations.append({'source': item['@id'], 'target': target['@id'],
                                      'relation': prop, 'evidence_url': BASE, 'reviewed_at': reviewed})
    for url in values(person.get('sameAs', [])):
        if url in by_id:
            continue
        nodes.append({'id': url, 'type': 'ProfilePage', 'name': profile_name(url), 'url': url,
                      'description': 'Perfil de la misma persona; consultar la fuente externa.',
                      'sources': [BASE], 'reviewed_at': reviewed})
        relations.append({'source': PERSON_ID, 'target': url, 'relation': 'sameAs',
                          'evidence_url': BASE, 'reviewed_at': reviewed})
    if len({n['id'] for n in nodes}) != len(nodes):
        raise ValueError('Duplicate projected ID')
    payload = {'schema_version': '2.0', 'url': BASE + 'red-publica.json',
               'reviewed_at': reviewed, 'source_sha256': digest,
               'source_url': BASE, 'jsonld_url': BASE + 'red-publica.jsonld',
               'scope': 'Identidad, empresa, trayectoria, formación, competencias y producción pública.',
               'verification_scope': 'La fecha corresponde a la revisión editorial del portafolio. Las fuentes propias declaran relaciones; no son verificación independiente ni prueba de indexación.',
               'maintenance': 'Reconstrucción automática desde el JSON-LD público del portafolio cuando cambia su fuente. No consulta perfiles externos ni datos privados en tiempo real.',
               'attribution_notes': [
                   'La experiencia pertenece a Henry; su relación con Economía IA es de fundador y director técnico.',
                   'Empleadores anteriores y beneficiarios de formación universitaria no se convierten en clientes de Economía IA.',
                   'Distinguir desarrollo propio, coautoría y proyecto académico dirigido.',
                   'Un DOI no implica arbitraje ni aval institucional. No inferir resultados comerciales.',
               ], 'nodes': nodes, 'relations': relations}
    return payload, {'@context': 'https://schema.org', '@graph': graph}


LABELS = {'mainEntity': 'Describe a', 'hasPart': 'Incluye', 'worksFor': 'Trabaja / trabajó en',
          'affiliation': 'Vinculación profesional o académica', 'alumniOf': 'Formación en', 'hasCredential': 'Título',
          'recognizedBy': 'Reconocido por', 'knowsAbout': 'Competencia', 'founder': 'Fundador',
          'author': 'Autoría', 'creator': 'Creación', 'performer': 'Ponente', 'organizer': 'Organiza',
          'sameAs': 'Perfil de la misma persona', 'subjectOf': 'Descrito en'}


def render(payload, jsonld):
    esc = html.escape
    by_id = {n['id']: n for n in payload['nodes']}
    def link(n):
        return f'<a href="{esc(n["url"], quote=True)}">{esc(n["name"])}</a>'
    rows = []
    for edge in payload['relations']:
        if edge['relation'] in ('mainEntity', 'hasPart'):
            continue  # Page containment remains in the full JSON export.
        rows.append(f'<tr><td>{link(by_id[edge["source"]])}</td><td>{esc(LABELS.get(edge["relation"], edge["relation"]))}</td><td>{link(by_id[edge["target"]])}</td></tr>')
    cards = []
    for item in payload['nodes']:
        props = item.get('properties', {})
        period = ' → '.join(str(props[k]) for k in ('startDate', 'endDate') if k in props)
        detail = f'<p>Periodo registrado: {esc(period)}</p>' if period else ''
        anchor = item['id'].split('#')[-1] if '#' in item['id'] else ''
        cards.append(f'<article id="{esc(anchor, quote=True)}"><h3>{link(item)}</h3><p>{esc(item["description"])}</p>{detail}<small>{esc(str(item["type"]))} · <a href="{BASE}">Fuente: portafolio del titular</a></small></article>')
    data = json.dumps(jsonld, ensure_ascii=False).replace('<', '\\u003c')
    reviewed = esc(payload['reviewed_at'])
    return f'''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Red pública de Henry Roncancio — trayectoria y Economía IA</title>
<meta name="description" content="Trayectoria, formación, proyectos y publicaciones de Henry Roncancio, y su relación de fundador con Economía IA. Fuentes e identidades conectadas.">
<link rel="canonical" href="{BASE}red-publica.html"><link rel="alternate" type="application/json" href="red-publica.json" title="Nodos y relaciones"><link rel="alternate" type="application/ld+json" href="red-publica.jsonld" title="Grafo Schema.org">
<script type="application/ld+json">{data}</script>
<style>body{{font:17px/1.65 system-ui,sans-serif;margin:0;background:#101723;color:#e7eef7}}main{{max-width:1050px;margin:auto;padding:32px 20px}}a{{color:#8edee8;overflow-wrap:anywhere}}h1{{line-height:1.2}}p{{max-width:80ch}}table{{border-collapse:collapse;width:100%}}th,td{{text-align:left;vertical-align:top;padding:16px;border-bottom:1px solid #475369}}.scroll{{overflow-x:auto}}small{{color:#b5c4d7}}article{{padding:16px 0;border-bottom:1px solid #475369}}:focus-visible{{outline:3px solid #f9c860;outline-offset:4px}}@media(max-width:600px){{th,td{{padding:10px}}}}</style>
</head><body><main><nav><a href="/">← Portafolio</a> · <a href="llms.txt">Guía para agentes</a> · <a href="red-publica.json">JSON</a> · <a href="red-publica.jsonld">JSON-LD</a></nav>
<h1>Trayectoria y red pública de Henry Roncancio</h1>
<p>Este mapa conecta mi experiencia profesional y académica, títulos, competencias, proyectos y publicaciones. Soy fundador y director técnico de <a href="https://www.economiaia.business/quienes_somos.html">Economía IA</a>. Mi trayectoria aporta experiencia al diseño y evaluación de sus soluciones; cada antecedente conserva su institución, periodo y atribución.</p>
<p><strong>Revisión editorial: <time datetime="{reviewed}">{reviewed}</time>.</strong> {esc(payload['verification_scope'])}</p>
<h2>Relaciones explícitas</h2><div class="scroll"><table><caption>{len(payload['nodes'])} entidades y {len(payload['relations'])} relaciones en la exportación completa</caption><thead><tr><th scope="col">Origen</th><th scope="col">Relación</th><th scope="col">Destino</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<h2>Experiencia, instituciones y evidencia</h2>{''.join(cards)}
<h2>Cómo interpretar el mapa</h2><ul>{''.join('<li>'+esc(n)+'</li>' for n in payload['attribution_notes'])}</ul>
<p>Para contrastar formación y producción consulta <a href="https://orcid.org/0009-0009-9954-9813">ORCID</a>, <a href="https://scienti.minciencias.gov.co/cvlac/visualizador/generarCurriculoCv.do?cod_rh=0000005738">CvLAC</a> y los DOI del portafolio. Una fuente propia documenta lo que declara su titular.</p>
<h2>Alcance y actualización</h2><p>{esc(payload['maintenance'])}</p><p>El mapa es público y de solo lectura. No garantiza indexación, citas o recomendaciones de buscadores o asistentes.</p>
</main></body></html>
'''


def build(root=ROOT, check=False):
    payload, jsonld = project(read_graph((root / 'index.html').read_text(encoding='utf-8-sig')))
    output = {'red-publica.json': json.dumps(payload, ensure_ascii=False, indent=2) + '\n',
              'red-publica.jsonld': json.dumps(jsonld, ensure_ascii=False, indent=2) + '\n',
              'red-publica.html': render(payload, jsonld)}
    for name, content in output.items():
        if check:
            if not (root / name).exists() or (root / name).read_text(encoding='utf-8') != content:
                raise ValueError(f'Stale output: {name}; run python3 build_public_network.py')
        else:
            (root / name).write_text(content, encoding='utf-8')
    print(f'Public network: {len(payload["nodes"])} nodes, {len(payload["relations"])} relationships')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    build(check=parser.parse_args().check)
