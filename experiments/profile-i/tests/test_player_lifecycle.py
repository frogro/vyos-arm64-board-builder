"""Exercise real player transitions without retaining the previous decoder."""
from pathlib import Path
import shutil
import subprocess
import unittest


class PlayerLifecycle(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js required for player lifecycle test')
    def test_decoder_released_before_replacement_and_stale_callbacks_ignored(self):
        player = Path(__file__).resolve().parents[1] / 'adapter/player.html'
        script = player.read_text().split('<script>', 1)[1].split('</script>', 1)[0]
        harness = r'''
const vm=require('node:vm'), assert=require('node:assert/strict');
const calls=[];
const previous={onended:()=>{},onplaying:()=>{},onerror:()=>{},
 pause(){calls.push('pause')}, removeAttribute(k){assert.equal(k,'src');calls.push('remove-src')},
 load(){assert.equal(this.onerror,null);calls.push('load')}};
const stage={querySelectorAll(){return [previous]},replaceChildren(){calls.push('remove-element')}};
const context={document:{querySelector:(s)=>s==='#stage'?stage:{}},
 window:{},location:{search:''},URLSearchParams,console,
 fetch:()=>new Promise(()=>{}),clearTimeout:()=>{},setTimeout:()=>{},sessionStorage:{setItem:()=>{}}};
vm.createContext(context);
vm.runInContext(SOURCE,context);
vm.runInContext('next()',context);
assert.deepEqual(calls,['pause','remove-src','load','remove-element']);
assert.equal(previous.onended,null);assert.equal(previous.onplaying,null);assert.equal(previous.onerror,null);
'''
        import json
        subprocess.run(['node', '-e', harness.replace('SOURCE', json.dumps(script))], check=True)


if __name__ == '__main__':
    unittest.main()
