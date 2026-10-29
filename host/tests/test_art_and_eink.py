import hashlib
import importlib.machinery
import importlib.util
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image, ImageDraw, ImageChops

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'host'))
import kindle_eink as eink

def load(name,path):
    loader=importlib.machinery.SourceFileLoader(name,str(path));spec=importlib.util.spec_from_loader(name,loader)
    module=importlib.util.module_from_spec(spec);loader.exec_module(module);return module

art=load('artgen',ROOT/'overlay/usr/local/bin/artgen')
hub=load('art_eink_hub',ROOT/'host/kindle-hub')


class ArtTests(unittest.TestCase):
    def test_all_modes_are_reproducible_and_one_bit(self):
        hashes=set()
        for mode in art.MODES:
            a=art.Drawing(480,640,123,complexity=3).render(mode)
            b=art.Drawing(480,640,123,complexity=3).render(mode)
            self.assertEqual(a.mode,'1');self.assertEqual(a.tobytes(),b.tobytes())
            self.assertNotEqual(a.getextrema()[0],a.getextrema()[1])
            hashes.add(hashlib.sha256(a.tobytes()).hexdigest())
        self.assertEqual(len(hashes),len(art.MODES))

    def test_daily_piece_is_never_replaced_without_force(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(art,'ROOT',Path(tmp)):
            args=art.parser().parse_args(['generate-daily','--date','2020-01-02','--width','480','--height','640'])
            path=art.generate(args,True);original=path.read_bytes();mtime=path.stat().st_mtime_ns
            args.mode='geometric_grid'
            self.assertEqual(art.generate(args,True),path)
            self.assertEqual(path.read_bytes(),original);self.assertEqual(path.stat().st_mtime_ns,mtime)
            meta=json.loads(path.with_suffix('.json').read_text())
            self.assertEqual(meta['date'],'2020-01-02');self.assertEqual(meta['mode'],'lsystem_flower')
            self.assertEqual(meta['seed'],art.seed_number('cyberdeck-art-v1:2020-01-02'))
            args.force=True;art.generate(args,True)
            self.assertNotEqual(path.read_bytes(),original)

    def test_inversion_is_exact_black_white_complement(self):
        a=art.Drawing(480,640,7).render('topology_map').convert('L')
        b=art.Drawing(480,640,7,invert=True).render('topology_map').convert('L')
        self.assertEqual(ImageChops.add(a,b).getextrema(),(255,255))


class EinkTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.source=self.root/'photo.png'
        image=Image.new('RGB',(1600,1000));draw=ImageDraw.Draw(image)
        for x in range(1600):draw.line((x,0,x,1000),fill=(int(x/1600*255),90,int((1600-x)/1600*255)))
        draw.text((200,200),'A clear page / 12345',fill='white',stroke_width=1)
        image.save(self.source)
    def tearDown(self):self.tmp.cleanup()

    def test_display_copies_preserve_source_and_have_expected_modes(self):
        original=self.source.read_bytes()
        for style in eink.STYLES:
            data=eink.convert(self.source,width=800,style=style)
            with Image.open(BytesIO(data)) as image:
                self.assertEqual(image.width,800)
                self.assertEqual(image.mode,'RGB' if style=='original' else '1')
        self.assertEqual(self.source.read_bytes(),original)

    def test_crop_invert_and_style_validation(self):
        a=eink.convert(self.source,width=800,style='crisp',crop='left')
        b=eink.convert(self.source,width=800,style='crisp',crop='left',invert=True)
        with Image.open(BytesIO(a)) as first,Image.open(BytesIO(b)) as second:
            self.assertEqual(ImageChops.add(first.convert('L'),second.convert('L')).getextrema(),(255,255))
        with self.assertRaises(ValueError):eink.convert(self.source,style='invalid')

    def test_pdf_page_renders_through_actual_poppler_and_remembers_options(self):
        old=hub.STATE;hub.STATE=self.root;(self.root/'cache').mkdir()
        try:
            metadata={'metadata':{'title':'Test magazine'},'files':[{'name':'issue.pdf','size':'5000'}]}
            key,pdf=hub.pdf_paths('test-magazine',metadata['files'][0])
            with Image.open(self.source) as image:image.save(pdf,format='PDF')
            with patch.object(hub,'metadata',return_value=metadata):
                raw=hub.pdf_image('test-magazine',1,style='crisp')
                with Image.open(BytesIO(raw)) as image:self.assertEqual(image.mode,'1')
                get=lambda key,default='':{'zoom':'150','crop':'left'}.get(key,default)
                page=hub.archive_reader('test-magazine',1,get)
                self.assertIn('Back to item',page);self.assertIn('Zoom +',page);self.assertIn('crop=left',page)
                progress=json.loads((self.root/'cache/reading-test-magazine.json').read_text())
                self.assertEqual(progress['zoom'],150)
                with self.assertRaisesRegex(ValueError,'last page'):hub.pdf_image('test-magazine',2)
        finally:hub.STATE=old

if __name__=='__main__':unittest.main()
