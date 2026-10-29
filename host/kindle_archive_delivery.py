"""Archive downloads → native Kindle documents, with checksum verification."""
import hashlib
import os
from pathlib import Path
import re
import shlex
import subprocess
import unicodedata
import urllib.parse
import urllib.request

SUPPORTED={'.pdf','.epub','.mobi','.azw3','.txt','.fb2','.rtf','.docx'}
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','root@kindle.example.invalid']


def supported_files(data):
    files=[f for f in data.get('files',[]) if not f.get('private') and
           Path(f.get('name','')).suffix.lower() in SUPPORTED and 0<int(f.get('size',0))<=250_000_000]
    priority={'.pdf':0,'.epub':1,'.azw3':2,'.mobi':3}
    return sorted(files,key=lambda f:(priority.get(Path(f['name']).suffix.lower(),9),f['name']))


def download(identifier,file,folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    key=hashlib.sha256((identifier+'/'+file['name']).encode()).hexdigest()[:24]
    path=folder/(key+Path(file['name']).suffix.lower())
    if path.exists() and path.stat().st_size:return path
    url='https://archive.org/download/'+urllib.parse.quote(identifier)+'/'+urllib.parse.quote(file['name'],safe='/')
    tmp=path.with_suffix(path.suffix+'.partial')
    try:
        request=urllib.request.Request(url,headers={'User-Agent':'Cyberdeck native reader/1.0'})
        with urllib.request.urlopen(request,timeout=45) as response,tmp.open('wb') as out:
            size=0
            while chunk:=response.read(256*1024):
                size+=len(chunk)
                if size>250_000_000:raise ValueError('This document exceeds the 250 MB reader limit.')
                out.write(chunk)
        if not tmp.stat().st_size:raise ValueError('Archive returned an empty file.')
        os.replace(tmp,path)
    finally:tmp.unlink(missing_ok=True)
    return path


def deliver_pdf(path,title):
    path=Path(path)
    with path.open('rb') as data:
        if not data.read(1024).lstrip().startswith(b'%PDF-'):raise ValueError('Archive did not return a valid PDF.')
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    label=unicodedata.normalize('NFKD',title).encode('ascii','ignore').decode()
    label=re.sub(r'[^A-Za-z0-9 ._-]','',label).strip(' .')[:100] or 'Archive document'
    folder='/mnt/kindle/documents/Archive';final=folder+'/'+label+'-'+digest[:10]+'.pdf'
    partial=folder+'/.'+Path(final).name+'.partial'
    command='mkdir -p '+shlex.quote(folder)+' && cat >'+shlex.quote(partial)+' && sha256sum '+shlex.quote(partial)
    with path.open('rb') as data:result=subprocess.run(SSH+[command],stdin=data,capture_output=True,text=True,timeout=240)
    if result.returncode:
        raise RuntimeError('Kindle Linux is offline. Wake it and open Linux, then send again. The original is kept on the host.')
    if not result.stdout.split() or result.stdout.split()[0]!=digest:
        raise RuntimeError('The Kindle copy could not be verified. The original is kept on the host.')
    result=subprocess.run(SSH+['mv '+shlex.quote(partial)+' '+shlex.quote(final)],capture_output=True,text=True,timeout=15)
    if result.returncode:raise RuntimeError('Could not finish the Kindle copy.')
    return final.replace('/mnt/kindle/','/mnt/us/',1)


def prepare_and_deliver(source,title,author):
    if Path(source).suffix.lower()=='.pdf':return deliver_pdf(source,title)
    from kindle_books import books
    books.STATE.mkdir(parents=True,exist_ok=True)
    ready=books.prepare_book(source,title,author)
    filename=books.deliver_book(ready,title,author)
    return '/mnt/us/documents/Books/'+filename


def open_reader(destination):
    command='/usr/local/bin/deck-open-book '+shlex.quote(destination)
    result=subprocess.run(SSH+[command],capture_output=True,text=True,timeout=110)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip()[-500:] or 'The document was sent, but the native reader could not be opened.')
    return result.stdout.strip()
