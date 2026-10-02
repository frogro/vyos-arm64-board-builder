import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import json, base64
p=Path(__file__).resolve().parents[1]/'tools/watch-upstream-rolling.py'
s=importlib.util.spec_from_file_location('watch',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Tests(unittest.TestCase):
    def setUp(self):
        a=patch.object(m,'current_source',return_value=('a'*40,'6.18.54'));a.start();self.addCleanup(a.stop)
        b=patch.object(m,'kernel_at',return_value='6.18.54');b.start();self.addCleanup(b.stop)
    def test_selection(self):
        rows=[{'tag_name':t} for t in ['2026.09.17-0028-rolling','2026.09.19-0028-rolling','2026.09.18-0028-rolling','bad-tag']]
        rows += [{'tag_name':'2026.09.20-0028-rolling','draft':True},{'tag_name':'2026.09.21-0028-rolling','prerelease':True}]
        self.assertEqual([r['tag_name'] for r in m.pending(rows,{'baseline':'2026.09.17-0028-rolling'})],['2026.09.18-0028-rolling','2026.09.19-0028-rolling'])
    def test_exact_scope(self):
        self.assertEqual(set(m.BOARDS),{'radxa-e52c','rock-5b','raspberry-pi-5','orangepi5-plus'})
        self.assertEqual(m.title('rock-5b','tag'),'rock-5b / tag / network=true tailscale=false kvm=false kiosk-f=false receiver-g=false')
    def test_legacy_title_normalization(self):
        self.assertEqual(m.normalized_title('rock-5b / tag / network=true tailscale=false kvm=false'),m.title('rock-5b','tag'))
        self.assertEqual(m.normalized_title(m.title('rock-5b','tag')),m.title('rock-5b','tag'))

    def test_orangepi_enrollment(self):
        self.assertEqual(m.BOARDS['orangepi5-plus'], 'efi-firmware-dtb')
        self.assertEqual(m.BOARD_FIRST_ROLLING['orangepi5-plus'], '2026.09.28-0746-rolling')

    def test_dispatch_and_resume(self):
        self.dispatch_and_resume('2026.09.18-0028-rolling', 3)

    def test_current_release_includes_orangepi(self):
        self.dispatch_and_resume('2026.09.28-0746-rolling', 4)

    def dispatch_and_resume(self, tag, count):
        state={'baseline':'2026.09.17-0028-rolling','releases':{}}
        dispatched=[]
        def api(path):
            if 'contents/' in path:
                return {'sha':'state-sha','content':base64.b64encode(json.dumps(state).encode()).decode()}
            if '/releases?' in path:
                return [{'tag_name':tag}]
            return [{'sha':'a'*40}]
        def gh(*args):
            if args[0]=='run': return '[]'
            dispatched.append(args)
            return ''
        def save(*args, **kwargs):
            payload=json.loads(kwargs['input'])
            state.clear();state.update(json.loads(base64.b64decode(payload['content'])))
            return json.dumps({'content':{'sha':'new-sha'}})
        with patch.object(m,'api',side_effect=api), patch.object(m,'gh',side_effect=gh), patch.object(m.subprocess,'check_output',side_effect=save), patch.dict(m.os.environ,{'DRY_RUN':'false'}):
            m.main();m.main()
        self.assertEqual(len(dispatched),count)
        self.assertEqual(len(state['releases'][tag]['boards']),count)
        self.assertTrue(all('kvm_over_ip=false' in a for a in dispatched))
        self.assertTrue(all(a[a.index('--ref') + 1] == 'main' for a in dispatched))

    def test_retry_decisions(self):
        run={'status':'completed','conclusion':'failure','run_attempt':1}
        self.assertEqual(m.retry_action({},run),'retry')
        self.assertEqual(m.retry_action({'retry_request_error_for_attempt':1},run),'attention')
        self.assertEqual(m.retry_action({},dict(run,run_attempt=2)),'retry')
        self.assertEqual(m.retry_action({},dict(run,run_attempt=3)),'exhausted')
        self.assertEqual(m.retry_action({'retry_requested_for_attempt':1},run),'waiting')
        self.assertEqual(m.retry_action({'retry_disabled':True},run),'suppressed')
        self.assertEqual(m.retry_action({},run,latest=False),'suppressed')
        self.assertEqual(m.retry_action({},dict(run,status='in_progress')),'waiting')
        self.assertEqual(m.retry_action({},dict(run,conclusion='success')),'success')
        self.assertEqual(m.retry_action({},dict(run,conclusion='cancelled')),'attention')
        self.assertEqual(m.retry_action({},dict(run,conclusion='timed_out')),'retry')

    def test_existing_failure_retry_and_dry_run(self):
        tag='2026.09.29-0028-rolling'
        initial={'baseline':'2026.09.17-0028-rolling','releases':{tag:{
            'vyos_commit':'a'*40,'boards':{b:{'dispatched':True} for b in m.BOARDS}}}}
        for dry in (True,False):
            state=json.loads(json.dumps(initial)); calls=[]; writes=[]
            def api(path):
                if 'contents/' in path:
                    return {'sha':'state-sha','content':base64.b64encode(json.dumps(state).encode()).decode()}
                if '/releases?' in path: return [{'tag_name':tag}]
                return {'status':'completed','conclusion':'failure','run_attempt':1,'html_url':'https://example.test/run'}
            def gh(*args):
                if args[:2]==('run','list'):
                    return json.dumps([{'displayTitle':m.title(b,tag),'databaseId':i} for i,b in enumerate(m.BOARDS,1)])
                calls.append(args); return ''
            def save(*args,**kwargs):
                payload=json.loads(kwargs['input']); writes.append(payload)
                state.clear();state.update(json.loads(base64.b64decode(payload['content'])))
                return json.dumps({'content':{'sha':'new-sha'}})
            with patch.object(m,'api',side_effect=api), patch.object(m,'gh',side_effect=gh), patch.object(m.subprocess,'check_output',side_effect=save), patch.dict(m.os.environ,{'DRY_RUN':str(dry).lower()}):
                m.main();m.main()
            self.assertEqual(len(calls),0 if dry else len(m.BOARDS))
            self.assertTrue(all(a[:2]==('run','rerun') and '--failed' in a for a in calls))
            if dry: self.assertEqual(writes,[])

    def test_kernel_advance_refreshes_once_and_waits_for_active_builds(self):
        tag='2026.10.01-0035-rolling'
        for active in (False,True):
            state={'baseline':'2026.09.17-0028-rolling','releases':{tag:{'vyos_commit':'b'*40,
                'kernel_version':'6.18.50','boards':{b:{'run_id':i,'conclusion':'success'} for i,b in enumerate(m.BOARDS,1)}}}}
            calls=[]
            def api(path):
                if 'contents/' in path:return {'sha':'x','content':base64.b64encode(json.dumps(state).encode()).decode()}
                if '/releases?' in path:return [{'tag_name':tag}]
                return {'status':'completed','conclusion':'success','run_attempt':1,'html_url':'https://example.test'}
            def gh(*args):
                if args[:2]==('run','list'):
                    if 'rebuild-community-ab.yml' in args:return json.dumps([{'status':'in_progress'}] if active else [])
                    return json.dumps([{'displayTitle':m.title(b,tag),'databaseId':i,'status':'completed','createdAt':'2026-10-01T00:00:00Z'} for i,b in enumerate(m.BOARDS,1)])
                calls.append(args);return ''
            def save(*args,**kwargs):
                payload=json.loads(kwargs['input']);state.clear();state.update(json.loads(base64.b64decode(payload['content'])))
                return json.dumps({'content':{'sha':'y'}})
            with patch.object(m,'api',side_effect=api),patch.object(m,'gh',side_effect=gh),patch.object(m.subprocess,'check_output',side_effect=save),patch.dict(m.os.environ,{'DRY_RUN':'false'}):
                m.main();m.main()
            self.assertEqual(len(calls),0 if active else 4)
            if not active:
                self.assertEqual(state['releases'][tag]['kernel_version'],'6.18.54')
                self.assertEqual(len(state['releases'][tag]['history']),1)
                self.assertTrue(all('vyos_ref='+('a'*40) in c for c in calls))

    def test_current_e52c_explicitly_excluded(self):
        state=json.loads((p.parents[1]/'.github/rolling-build-state.json').read_text())
        entry=state['releases']['2026.09.28-0746-rolling']['boards']['radxa-e52c']
        self.assertTrue(entry['retry_disabled'])

unittest.main()
