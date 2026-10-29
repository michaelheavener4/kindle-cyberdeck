import hashlib
import io
import importlib.machinery
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.parse
from unittest.mock import patch, Mock

HOST=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HOST))
import kindle_archive_delivery as delivery
loader=importlib.machinery.SourceFileLoader('delivery_hub',str(HOST/'kindle-hub'))
spec=importlib.util.spec_from_loader(loader.name,loader);hub=importlib.util.module_from_spec(spec);loader.exec_module(hub)


class DeliveryTests(unittest.TestCase):
    def test_real_post_handler_keeps_selected_file_and_action_after_metadata_lookup(self):
        filename='magazines/Issue #1 – été.pdf'
        metadata={'metadata':{'title':'A magazine'},'files':[{'name':filename,'size':'1000'}],
                  'file':['wrong-file.pdf'],'action':['wrong-action']}
        with tempfile.TemporaryDirectory() as tmp,patch.object(hub,'STATE',Path(tmp)):
            hub.init()
            for action in ['send','open']:
                with self.subTest(action=action):
                    handler=object.__new__(hub.Handler)
                    body=urllib.parse.urlencode({'csrf':hub.TOKEN,'item':'a-magazine','file':filename,'action':action}).encode()
                    handler.path='/archive/send';handler.headers={'Content-Length':str(len(body))}
                    handler.rfile=io.BytesIO(body);handler.send=Mock();handler.redirect=Mock()
                    with patch.object(hub,'metadata',return_value=metadata),patch.object(hub.POOL,'submit') as submit:
                        handler.do_POST()
                    handler.send.assert_not_called();handler.redirect.assert_called_once()
                    job_id=handler.redirect.call_args.args[0].rsplit('/',1)[1]
                    with hub.db() as con:job=con.execute('SELECT * FROM archive_jobs WHERE id=?',(job_id,)).fetchone()
                    self.assertEqual(job['file'],filename)
                    submit.assert_called_once_with(hub.archive_transfer,job_id,action=='open')

    def test_each_public_document_has_unambiguous_send_forms(self):
        data={'metadata':{'title':'Two documents'},'files':[
            {'name':'Issue & one.pdf','size':'1000'}, {'name':'two.epub','size':'1000'},
            {'name':'private.pdf','size':'1000','private':True}, {'name':'image.jpg','size':'1000'}]}
        with patch.object(hub,'metadata',return_value=data):page=hub.archive_item('test')
        self.assertIn('name="file" value="Issue &amp; one.pdf"',page)
        self.assertIn('name="file" value="two.epub"',page)
        self.assertEqual(page.count('type="hidden" name="action" value="send"'),2)
        self.assertEqual(page.count('type="hidden" name="action" value="open"'),2)
        self.assertNotIn('private.pdf',page)
        self.assertNotIn('name="file" value="image.jpg"',page)
        self.assertIn('Save original · browser download',page)
        self.assertNotIn('<strong>image.jpg</strong>',page)
        with patch.object(hub,'metadata',return_value=data):all_files=hub.archive_item('test','all')
        self.assertIn('<strong>image.jpg</strong>',all_files)

    def test_public_supported_files_only(self):
        data={'files':[{'name':'issue.pdf','size':'1000'}, {'name':'book.epub','size':'2000'},
                       {'name':'private.pdf','size':'1000','private':True},
                       {'name':'large.pdf','size':'300000000'},{'name':'image.jpg','size':'1000'}]}
        self.assertEqual([f['name'] for f in delivery.supported_files(data)],['issue.pdf','book.epub'])

    def test_pdf_checksum_before_final_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'book.pdf';source.write_bytes(b'%PDF-1.4\noriginal document\n')
            digest=hashlib.sha256(source.read_bytes()).hexdigest()
            result=lambda code,text:type('Result',(),{'returncode':code,'stdout':text,'stderr':''})()
            with patch.object(delivery.subprocess,'run',side_effect=[result(0,digest+' file'),result(0,'')]) as run:
                path=delivery.deliver_pdf(source,'A title / <unsafe>')
            self.assertTrue(path.startswith('/mnt/us/documents/Archive/'))
            self.assertTrue(path.endswith('.pdf'));self.assertEqual(run.call_count,2)
            with patch.object(delivery.subprocess,'run',return_value=result(0,'wrong checksum')) as run:
                with self.assertRaisesRegex(RuntimeError,'verified'):delivery.deliver_pdf(source,'Title')
                self.assertEqual(run.call_count,1)

    def test_send_and_read_job_uses_native_handoff(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(hub,'STATE',Path(tmp)):
            hub.init()
            with hub.db() as c:c.execute('INSERT INTO archive_jobs VALUES(?,?,?,?,?,?,?)',('job','archive-id','issue.pdf','Title','queued','',''))
            data={'metadata':{'title':'Title','creator':['Author']},'files':[{'name':'issue.pdf','size':'1000'}]}
            with patch.object(hub,'metadata',return_value=data),patch.object(delivery,'download',return_value=Path(tmp)/'issue.pdf'),patch.object(delivery,'prepare_and_deliver',return_value='/mnt/us/documents/Archive/issue.pdf'),patch.object(delivery,'open_reader') as opened:
                hub.archive_transfer('job',True)
                opened.assert_called_once_with('/mnt/us/documents/Archive/issue.pdf')
                item=hub.archive_item('archive-id')
            with hub.db() as c:job=c.execute('SELECT * FROM archive_jobs WHERE id="job"').fetchone()
            self.assertEqual(job['state'],'sent');self.assertIn('Send to Kindle &amp; Read',item)
            self.assertNotIn('Read PDF / magazine',item)


if __name__=='__main__':unittest.main()
