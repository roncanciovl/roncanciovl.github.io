"""Build a static public network from this public site's JSON-LD only.

Never reads a private profile, task store, environment variable or credential.
Run after reviewing public claims: python3 build_public_network.py
"""
import html
import json
from pathlib import Path
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parent
BASE = 'https://roncanciovl.github.io/'
REVIEWED = '2026-09-07'


class JsonLdParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        self.active = tag == 'script' and dict(attrs).get('type') == 'application/ld+json' if tag == 'script' else self.active

    def handle_endtag(self, tag):
        if tag == 'script':
            self.active = False

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)


def build():
    parser = JsonLdParser()
    parser.feed((ROOT / 'index.html').read_text(encoding='utf-8'))
    graph = json.loads(''.join(parser.parts))['@graph']
    person = next(n for n in graph if n['@type'] == 'Person')
    pid = person['@id']
    nodes, relations = [], []

    def node(identifier, kind, name, url, source, description=''):
        nodes.append(dict(id=identifier, type=kind, name=name, url=url,
                          description=description, sources=[source],
                          reviewed_at=REVIEWED))

    def edge(target, relation, source):
        relations.append(dict(source=pid, target=target, relation=relation,
                              evidence_url=source, reviewed_at=REVIEWED))

    node(pid, 'Person', person['name'], BASE, BASE, person['description'])
    labels = ['GitHub', 'ORCID', 'Google Scholar', 'LinkedIn', 'CvLAC']
    assert len(labels) == len(person['sameAs']), 'Review identity profiles before rebuilding'
    for label, url in zip(labels, person['sameAs']):
        node(url, 'ProfilePage', label, url, BASE,
             'Perfil público enlazado desde el portafolio; su disponibilidad depende de la plataforma.')
        edge(url, 'perfil_publico', BASE)

    company = 'https://www.economiaia.business/quienes_somos.html'
    node(company, 'Organization', 'Economía IA', company, company,
         'Iniciativa empresarial fundada y liderada por Henry Roncancio; no es otro perfil de la misma persona.')
    edge(company, 'fundador', company)

    for item in graph:
        kind = item['@type']
        if kind not in ('SoftwareSourceCode', 'Dataset', 'ScholarlyArticle'):
            continue
        url = item.get('url', item.get('identifier'))
        description = item.get('description', '')
        if kind == 'ScholarlyArticle':
            description = 'Publicación académica enlazada en el portafolio; consultar el DOI para autoría completa.'
        elif kind == 'Dataset':
            description += ' No es un artículo arbitrado.'
        node(item['@id'], kind, item['name'], url, BASE, description)
        nodes[-1]['identifiers'] = [item['identifier']]
        if kind == 'Dataset':
            nodes[-1]['concept_doi'] = item['sameAs'][0]
        edge(item['@id'], 'publicacion_en_portafolio' if kind == 'ScholarlyArticle' else 'proyecto_propio', BASE)

    payload = dict(schema_version='1.0', url=BASE+'red-publica.json',
                   reviewed_at=REVIEWED,
                   scope='Mapa editorial de identidad, empresa, proyectos y publicaciones ya públicos. Instantánea estática, no API operativa.',
                   verification_scope='La fecha indica revisión editorial de las fuentes citadas, no certificación independiente, comprobación de cada destino externo ni indexación por motores de IA.',
                   maintenance='Actualizar al cambiar los hechos públicos y reconstruir con build_public_network.py; no hay sincronización en tiempo real.',
                   research_focus='Embodied IA: percepción, aprendizaje y acción en sistemas robóticos.',
                   attribution_notes=['Distinguir proyectos propios de proyectos académicos dirigidos.',
                                      'Un DOI no implica arbitraje, aval de grupo ni reconocimiento institucional.',
                                      'La trayectoria del fundador no equivale a contratos de Economía IA.',
                                      'No inferir clientes, resultados financieros ni acceso a sistemas privados.'],
                   nodes=nodes, relations=relations)
    ids = {n['id'] for n in nodes}
    assert len(ids) == len(nodes)
    assert all(e['source'] in ids and e['target'] in ids for e in relations)
    assert all(n['url'].startswith('https://') for n in nodes)
    (ROOT/'red-publica.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    esc = html.escape
    names = {'perfil_publico':'Perfil público', 'fundador':'Fundador',
             'proyecto_propio':'Proyecto propio', 'publicacion_en_portafolio':'Publicación en el portafolio'}
    by_id = {n['id']: n for n in nodes}
    rows = []
    for relation in relations:
        item = by_id[relation['target']]
        rows.append(f'<tr><td>{esc(names[relation["relation"]])}</td><td><a href="{esc(item["url"], quote=True)}">{esc(item["name"])}</a><p>{esc(item["description"])}</p></td><td><a href="{esc(relation["evidence_url"], quote=True)}">Fuente</a><br><time datetime="{REVIEWED}">{REVIEWED}</time></td></tr>')
    page = f'''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Red pública de Henry Roncancio — perfiles, proyectos y evidencia</title>
<meta name="description" content="Relaciones públicas de Henry Roncancio: identidad académica, Economía IA, Embodied IA, repositorios y publicaciones con fuentes.">
<link rel="canonical" href="{BASE}red-publica.html"><link rel="alternate" type="application/json" href="red-publica.json" title="Mapa público estructurado">
<style>body{{font:17px/1.65 system-ui,sans-serif;margin:0;background:#101723;color:#e7eef7}}main{{max-width:1050px;margin:auto;padding:32px 20px}}a{{color:#8edee8}}h1{{line-height:1.2}}p{{max-width:80ch}}table{{border-collapse:collapse;width:100%}}th,td{{text-align:left;vertical-align:top;padding:16px;border-bottom:1px solid #475369}}td p{{margin:.4em 0;font-size:.9em}}.scroll{{overflow-x:auto}}small{{color:#b5c4d7}}:focus-visible{{outline:3px solid #f9c860;outline-offset:4px}}@media(max-width:600px){{th,td{{padding:10px}}}}</style>
</head><body><main><nav><a href="/">← Portafolio</a> · <a href="llms.txt">Guía para agentes</a> · <a href="red-publica.json">JSON público</a></nav>
<h1>Mi red pública</h1><p>Henry Antonio Roncancio Velandia · Investigación activa en <strong>Embodied IA</strong>. Este mapa conecta mis perfiles, iniciativa empresarial, proyectos propios y publicaciones. Las relaciones parten de mi identidad; Economía IA es una organización distinta, no un alias personal.</p>
<p><strong>Revisión editorial: {REVIEWED}.</strong> {esc(payload['verification_scope'])}</p>
<div class="scroll"><table><caption>Relaciones y fuentes públicas</caption><thead><tr><th scope="col">Relación con Henry</th><th scope="col">Destino</th><th scope="col">Fuente y revisión</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<h2>Cómo interpretar la evidencia</h2><ul>{''.join('<li>'+esc(n)+'</li>' for n in payload['attribution_notes'])}</ul>
<p>Las fuentes de cada relación indican dónde se declara. Los DOI permiten consultar los registros originales. Los proyectos académicos dirigidos del portafolio no se incluyen como software de autoría propia.</p>
<h2>Alcance y actualización</h2><p>Este mapa es público, estático y de solo lectura. No permite consultar tareas, cuentas o documentos privados ni ejecutar acciones. No garantiza que un buscador lo indexe o lo cite.</p><p>{esc(payload['maintenance'])}</p>
</main></body></html>'''
    (ROOT/'red-publica.html').write_text(page+'\n', encoding='utf-8')
    print(f'Public network: {len(nodes)} nodes, {len(relations)} relationships')


if __name__ == '__main__':
    build()
