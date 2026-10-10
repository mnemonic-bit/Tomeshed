"""Browser checks for document drag, picker, import drawer, and file actions."""

import base64
import http.server
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from test_documents import pdf_bytes,epub_bytes,json_bytes
ARTIFACTS=Path('/tmp/tomeshed-feature-0006-browser')
ARTIFACTS.mkdir(exist_ok=True)


def main():
    with tempfile.TemporaryDirectory() as temporary:
        folder=Path(temporary)
        pdf=folder/'Drop Good.pdf'; pdf.write_bytes(pdf_bytes(2))
        epub=folder/'Picker Book.epub'; epub.write_bytes(epub_bytes(10))
        structured=folder/'Drop Notes.json'; structured.write_bytes(json_bytes())
        picker_pdf=folder/'Picker Good.pdf'; picker_pdf.write_bytes(pdf.read_bytes())
        picker_json=folder/'Picker Notes.json'; picker_json.write_bytes(structured.read_bytes())
        bad=folder/'Drop Bad.pdf'; bad.write_bytes(b'not a document')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
        base=f'http://127.0.0.1:{port}'
        class Remote(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200); self.send_header('Content-Type','application/pdf'); self.end_headers(); self.wfile.write(pdf.read_bytes())
            def log_message(self,*args): pass
        remote=http.server.ThreadingHTTPServer(('127.0.0.1',0),Remote)
        remote_thread=threading.Thread(target=remote.serve_forever,daemon=True); remote_thread.start()
        env=dict(os.environ,TOMESHED_DB=str(folder/'library.db'),TOMESHED_LIBRARY_DIR=str(folder/'library'),HOST='127.0.0.1',PORT=str(port),TOMESHED_URL_ALLOWED_CIDRS='127.0.0.0/8')
        server=subprocess.Popen([sys.executable,'tomeshed.py'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                try:
                    with urlopen(base+'/api/health',timeout=.2): break
                except Exception: time.sleep(.1)
            else: raise AssertionError('server did not start')
            checks=[]
            with sync_playwright() as playwright:
                browser=playwright.chromium.launch(headless=True)
                context=browser.new_context(viewport={'width':390,'height':800},has_touch=True)
                page=context.new_page()
                page.goto(base+'/login')
                page.locator('#password').fill('browser-password')
                page.locator('#password_confirmation').fill('browser-password')
                page.get_by_role('button',name='Set password and open library').click()
                page.wait_for_url(base+'/')
                page.evaluate("""() => {const data=new DataTransfer();data.setData('text/plain','text');document.dispatchEvent(new DragEvent('dragenter',{dataTransfer:data,bubbles:true,cancelable:true}));}""")
                assert page.locator('#fileDropTarget').is_hidden()
                page.evaluate("""() => {const data=new DataTransfer();data.setData('text/uri-list','https://example.com');document.dispatchEvent(new DragEvent('dragenter',{dataTransfer:data,bubbles:true,cancelable:true}));}""")
                assert page.locator('#fileDropTarget').is_hidden()
                page.evaluate("""() => {const data=new DataTransfer();data.items.add(new File(['x'],'sample.pdf'));document.dispatchEvent(new DragEvent('dragenter',{dataTransfer:data,bubbles:true,cancelable:true}));}""")
                assert page.locator('#fileDropTarget').is_visible()
                overlay=page.locator('#fileDropTarget').bounding_box()
                assert overlay['x']==0 and overlay['y']==0 and overlay['width']==390 and overlay['height']==800
                page.evaluate("""() => document.dispatchEvent(new DragEvent('dragleave',{bubbles:true,relatedTarget:null}))""")
                assert page.locator('#fileDropTarget').is_hidden()
                checks.append('file overlay, text/link ignored, leave closes')
                with page.expect_file_chooser() as chooser:
                    page.get_by_role('button',name='Add document').tap()
                chooser.value.set_files(str(epub))
                page.wait_for_function("document.querySelector('#libraryCount').textContent === '1 document'",timeout=60000)
                assert page.locator('.document-card').count()==1
                picker_button=page.get_by_role('button',name='Add document')
                picker_button.focus()
                assert picker_button.evaluate('(node) => document.activeElement === node')
                with page.expect_file_chooser() as chooser:
                    picker_button.press('Enter')
                chooser.value.set_files([str(picker_pdf),str(picker_json)])
                page.wait_for_function("document.querySelector('#libraryCount').textContent === '3 documents'",timeout=60000)
                checks.append('touch EPUB picker and keyboard PDF/JSON picker')
                page.evaluate("""() => {window.workflowSnapshots=[];window.workflowSampler=setInterval(async()=>{try{const jobs=(await (await fetch('/api/imports')).json()).jobs;window.workflowSnapshots.push(...jobs.filter(j=>j.original_filename.startsWith('Drop ') && j.original_filename!=='Drop Bad.pdf').map(j=>({name:j.original_filename,state:j.state,bytes:j.bytes_received})));}catch(_){ }},25)}""")
                payload=[{'name':path.name,'data':base64.b64encode(path.read_bytes()).decode()} for path in (pdf,structured,bad)]
                page.evaluate("""files => {const data=new DataTransfer();for(const item of files){const bytes=Uint8Array.from(atob(item.data),c=>c.charCodeAt(0));data.items.add(new File([bytes],item.name));}document.dispatchEvent(new DragEvent('dragenter',{dataTransfer:data,bubbles:true,cancelable:true}));document.dispatchEvent(new DragEvent('drop',{dataTransfer:data,bubbles:true,cancelable:true}));}""",payload)
                page.wait_for_function("document.querySelector('#libraryCount').textContent === '5 documents'",timeout=60000)
                page.wait_for_function("[...document.querySelectorAll('.import-job')].some(row => row.textContent.includes('Drop Bad.pdf') && row.textContent.includes('failed'))")
                assert page.locator('#fileDropTarget').is_hidden()
                assert page.locator('.document-card').count()==5
                page.evaluate('() => loadImportJobs()')
                page.wait_for_function("[...document.querySelectorAll('.import-job')].some(row=>row.textContent.includes('bytes received'))")
                assert 'bytes received' in page.locator('#importsDrawer').text_content(), page.locator('#importsDrawer').text_content()
                page.screenshot(path=str(ARTIFACTS/'imports-390.png'),full_page=True)
                jobs=page.evaluate("async () => (await (await fetch('/api/imports')).json()).jobs")
                snapshots=page.evaluate("() => {clearInterval(window.workflowSampler);return window.workflowSnapshots}")
                assert len([job for job in jobs if job['original_filename'].startswith('Drop ')])==3
                assert len([job for job in jobs if job['state']=='failed'])==1
                assert any(item['state']=='processing' and item['bytes']>0 for item in snapshots),snapshots
                checks.append('three independent drop jobs, valid processing and bytes, one filename-specific failure')
                # A pending job can be cancelled in the drawer, then retried with a fresh file selection.
                pending=page.evaluate("async () => (await (await fetch('/api/imports/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({filename:'Cancel Me.pdf',size:5})})).json())")
                page.evaluate('() => loadImportJobs()')
                cancel_row=page.locator('.import-job').filter(has_text='Cancel Me.pdf')
                cancel_row.get_by_role('button',name='Cancel').click()
                page.wait_for_function("async id => (await (await fetch('/api/imports')).json()).jobs.find(j=>j.id===id)?.error==='Cancelled by user'",arg=pending['id'])
                checks.append('drawer cancellation')
                failed_row=page.locator('.import-job').filter(has_text='Drop Bad.pdf')
                with page.expect_file_chooser() as chooser:
                    failed_row.get_by_role('button',name='Retry').click()
                chooser.value.set_files(str(pdf))
                page.wait_for_function("document.querySelector('#libraryCount').textContent === '6 documents'",timeout=60000)
                checks.append('failed browser retry with selected file')
                page.locator('#closeImports').click()
                card=page.locator('.document-card').filter(has_text='Drop Good').first
                card.get_by_role('button',name='Info for Drop Good').click()
                panel=card.locator('.document-info')
                assert panel.get_by_role('link',name='Download original (PDF)').is_visible()
                assert panel.get_by_role('link',name='Download Docling JSON').is_visible()
                panel.locator('.source-rename-form input').fill('Renamed shelf.pdf')
                panel.get_by_role('button',name='Rename file').click()
                page.wait_for_function("[...document.querySelectorAll('.document-info')].some(p=>p.textContent.includes('Renamed shelf.pdf'))")
                page.screenshot(path=str(ARTIFACTS/'info-390.png'),full_page=True)
                checks.append('Info exports and stored filename rename')
                dialog_text=[]
                page.on('dialog',lambda dialog: (dialog_text.append(dialog.message),dialog.accept()))
                card=page.locator('.document-card').filter(has_text='Drop Good').first
                card.get_by_role('button',name='Remove document').click()
                page.wait_for_function("document.querySelector('#libraryCount').textContent === '5 documents'")
                checks.append('confirmed single document removal')
                page.locator('#importsButton').click()
                url=f'http://127.0.0.1:{remote.server_port}/Url_Book.pdf?token=secret#fragment'
                page.locator('#importUrl').fill(url)
                page.locator('#urlImportForm button').click()
                page.wait_for_function("document.querySelector('#libraryCount').textContent === '6 documents'",timeout=60000)
                page.locator('#closeImports').click()
                url_card=page.locator('.document-card').filter(has_text='Url Book').first
                url_card.get_by_role('button',name='Info for Url Book').click()
                info_text=url_card.locator('.document-info').inner_text()
                assert 'token=REDACTED' in info_text and 'secret' not in info_text and 'fragment' not in info_text
                page.screenshot(path=str(ARTIFACTS/'url-info-390.png'),full_page=True)
                checks.append('URL import and redacted Info source URL')
                page.set_viewport_size({'width':1280,'height':800})
                page.screenshot(path=str(ARTIFACTS/'library-1280.png'),full_page=True)
                preview=page.evaluate("async () => await (await fetch('/api/library/clear/preview')).json()")
                assert preview['document_count']==6 and preview['file_count']>=6
                page.locator('#bulkClearButton').click()
                page.wait_for_function("document.querySelector('#libraryCount').textContent === '0 documents'")
                assert dialog_text and '6 documents' in dialog_text[-1]
                checks.append('administrator bulk preview and confirmed clear')
                browser.close()
            report={'result':'passed','checks':checks}
            (ARTIFACTS/'report.json').write_text(json.dumps(report,indent=2))
            print(f'passed: {ARTIFACTS / "report.json"}')
        finally:
            remote.shutdown(); remote.server_close()
            server.terminate()
            try: server.wait(timeout=5)
            except subprocess.TimeoutExpired: server.kill()


if __name__=='__main__': main()
