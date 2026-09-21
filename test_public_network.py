"""Guard against silent loss of public evidence and broken entity relationships."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from build_public_network import ROOT, BASE, PERSON_ID, COMPANY_ID, read_graph, project, build


class PublicGraphTests(unittest.TestCase):
    def setUp(self):
        self.graph = read_graph((ROOT / 'index.html').read_text())

    def test_public_evidence_and_founder_connection_survive_export(self):
        payload, ld = project(self.graph)
        ids = {n['id'] for n in payload['nodes']}
        self.assertTrue({n['@id'] for n in self.graph} <= ids)
        for kind in ['Event', 'EducationalOccupationalCredential', 'OrganizationRole',
                     'DefinedTerm', 'ScholarlyArticle', 'Dataset', 'SoftwareSourceCode']:
            self.assertIn(kind, {n['type'] for n in payload['nodes']})
        self.assertIn((COMPANY_ID, 'founder', PERSON_ID),
                      {(r['source'], r['relation'], r['target']) for r in payload['relations']})
        person = next(n for n in ld['@graph'] if n['@id'] == PERSON_ID)
        self.assertFalse(any('/company/' in url for url in person['sameAs']))
        self.assertNotIn(COMPANY_ID, person['sameAs'])
        economia_ia_profile = next(
            n for n in payload['nodes']
            if n['id'] == 'https://www.economiaia.business/henry_roncancio.html'
        )
        self.assertEqual(economia_ia_profile['name'], 'Perfil de Henry en Economía IA')
        researchgate = next(
            n for n in payload['nodes']
            if n['id'] == 'https://www.researchgate.net/profile/Henry-Roncancio-2'
        )
        self.assertEqual(researchgate['name'], 'ResearchGate')
        self.assertIn(
            (PERSON_ID, 'sameAs', researchgate['id']),
            {(r['source'], r['relation'], r['target']) for r in payload['relations']},
        )
        self.assertTrue(all(r['source'] in ids and r['target'] in ids for r in payload['relations']))

    def test_new_entity_type_and_sixth_profile_are_not_silently_dropped(self):
        extra = {'@type': 'Book', '@id': BASE + '#test-book', 'name': 'Test evidence',
                 'author': {'@id': PERSON_ID}}
        self.graph.append(extra)
        person = next(n for n in self.graph if n['@id'] == PERSON_ID)
        person['sameAs'].append('https://example.org/profile')
        payload, ld = project(self.graph)
        self.assertIn(extra, ld['@graph'])
        self.assertIn(extra['@id'], {n['id'] for n in payload['nodes']})
        self.assertIn('https://example.org/profile', {n['id'] for n in payload['nodes']})

    def test_event_reservations_surface_is_visible_in_public_graph(self):
        payload, _ = project(self.graph)
        reservation_id = BASE + '#reservas-eventos-economia-ia'
        node = next(n for n in payload['nodes'] if n['id'] == reservation_id)
        self.assertEqual('CollectionPage', node['type'])
        self.assertEqual('https://reservas.economiaia.business/', node['url'])
        self.assertIn(
            (PERSON_ID, 'subjectOf', reservation_id),
            {(r['source'], r['relation'], r['target']) for r in payload['relations']},
        )

    def test_duplicate_and_dangling_references_fail(self):
        broken = copy.deepcopy(self.graph)
        broken.append(copy.deepcopy(broken[0]))
        with self.assertRaisesRegex(ValueError, 'Duplicate ID'):
            project(broken)
        broken = copy.deepcopy(self.graph)
        broken[0]['mainEntity'] = {'@id': BASE + '#missing'}
        with self.assertRaisesRegex(ValueError, 'Unresolved reference'):
            project(broken)

    def test_build_is_deterministic_and_detects_stale_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'index.html').write_text((ROOT / 'index.html').read_text())
            build(root)
            build(root, check=True)
            (root / 'red-publica.jsonld').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'Stale output'):
                build(root, check=True)


if __name__ == '__main__':
    unittest.main()
