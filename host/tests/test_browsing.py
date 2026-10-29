import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import urllib.parse

HOST = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOST))

loader = importlib.machinery.SourceFileLoader('browse_hub', str(HOST / 'kindle-hub'))
spec = importlib.util.spec_from_loader(loader.name, loader)
hub = importlib.util.module_from_spec(spec)
loader.exec_module(hub)


class ArchiveTests(unittest.TestCase):
    def test_filters_sort_and_pagination_survive(self):
        response = {'response': {'numFound': 30, 'docs': []}}
        with patch.object(hub, 'fetch', return_value=json.dumps(response).encode()) as fetch:
            page = hub.archive_search('space travel', 'texts', 2, creator='A "Writer"',
                collection='gutenberg', language='eng', year_from='1800', year_to='1920',
                format='EPUB', sort='date_asc', access='public', scope='title', adv='1')
        params = urllib.parse.parse_qs(urllib.parse.urlsplit(fetch.call_args.args[0]).query)
        self.assertEqual(params['sort[]'], ['date asc'])
        query = params['q'][0]
        for part in ['title:"space travel"', 'mediatype:texts', 'creator:"A \\"Writer\\""',
                     'date:[1800-01-01 TO 1920-12-31]', 'collection:"gutenberg"',
                     'format:"EPUB"', 'NOT access-restricted-item:true']:
            self.assertIn(part, query)
        self.assertIn('page=3', page)
        self.assertIn('language=eng', page)
        self.assertIn('year_to=1920', page)
        self.assertIn('name="scope"', page)

    def test_invalid_dates_do_not_reach_api(self):
        with patch.object(hub, 'fetch') as fetch:
            for start, end in [('2020', '1900'), ('xyz', '2000')]:
                with self.assertRaises(ValueError):
                    hub.archive_search('test', year_from=start, year_to=end)
            fetch.assert_not_called()

    def test_default_sort_and_upstream_errors(self):
        with patch.object(hub,'fetch',return_value=b'{"response":{"numFound":0,"docs":[]}}') as fetch:
            hub.archive_search('astronomy')
            params=urllib.parse.parse_qs(urllib.parse.urlsplit(fetch.call_args.args[0]).query)
            self.assertNotIn('sort[]',params)
        with patch.object(hub,'fetch',return_value=b'{"error":"unsupported"}'):
            with self.assertRaisesRegex(ValueError,'simpler query'): hub.archive_search('bad')

    def test_collection_and_file_format_navigation(self):
        data = {'metadata': {'title': '<Title>', 'mediatype': 'collection', 'creator': ['Author'],
                            'collection': ['gutenberg'], 'subject': ['<topic>']},
                'files': [{'name': 'book.epub', 'format': 'EPUB', 'size': '1000'},
                          {'name': 'hidden.pdf', 'format': 'PDF', 'private': 'true'},
                          {'name': 'book.pdf', 'format': 'Text PDF', 'size': '2000'}]}
        with patch.object(hub, 'metadata', return_value=data):
            page = hub.archive_item('test', 'EPUB')
        self.assertIn('Browse this collection', page)
        self.assertIn('book.epub', page)
        self.assertNotIn('hidden.pdf', page)
        self.assertNotIn('book.pdf', page)
        self.assertIn('&lt;topic&gt;', page)
        self.assertIn('creator=Author', page)


if __name__ == '__main__':
    unittest.main()
