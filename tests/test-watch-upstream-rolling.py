import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import json, base64
p=Path(__file__).resolve().parents[1]/'tools/watch-upstream-rolling.py'
s=importlib.util.spec_from_file_location('watch',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Tests(unittest.TestCase):
    def test_selection(self):
        rows=[{'tag_name':t} for t in ['2026.09.17-0028-rolling','2026.09.19-0028-rolling','2026.09.18-0028-rolling','bad-tag']]
        rows += [{'tag_name':'2026.09.20-0028-rolling','draft':True},{'tag_name':'2026.09.21-0028-rolling','prerelease':True}]
        self.assertEqual([r['tag_name'] for r in m.pending(rows,{'baseline':'2026.09.17-0028-rolling'})],['2026.09.18-0028-rolling','2026.09.19-0028-rolling'])
    def test_exact_scope(self):
        self.assertEqual(set(m.BOARDS),{'radxa-e52c','rock-5b','raspberry-pi-5'})
        self.assertEqual(m.title('rock-5b','tag'),'rock-5b / tag / network=true tailscale=false kvm=false')
    def test_dispatch_and_resume(self):
        state={'baseline':'2026.09.17-0028-rolling','releases':{}}
        dispatched=[]
        def api(path):
            if 'contents/' in path:
                return {'sha':'state-sha','content':base64.b64encode(json.dumps(state).encode()).decode()}
            if '/releases?' in path:
                return [{'tag_name':'2026.09.18-0028-rolling'}]
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
        self.assertEqual(len(dispatched),3)
        self.assertEqual(len(state['releases']['2026.09.18-0028-rolling']['boards']),3)
        self.assertTrue(all('kvm_over_ip=false' in a for a in dispatched))

unittest.main()
