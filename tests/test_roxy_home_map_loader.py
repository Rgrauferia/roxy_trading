from pathlib import Path
import subprocess


def test_google_loader_waits_for_callback_and_libraries_not_script_load():
    root = Path(__file__).resolve().parents[1]
    script = r'''
const assert=require('node:assert/strict'),fs=require('node:fs');
const source=fs.readFileSync('assets/roxy_list.js','utf8');
const begin=source.indexOf('  function loadFamilyGoogleMaps(){');
const end=source.indexOf('  function createFamilyMapPerson(',begin);
let familyMapLoader=null, inserted;
const homeFamily={map:{browser_key:'synthetic-test-key'}};
const window={};
const document={createElement:()=>({remove(){}}),head:{append:script=>inserted=script}};
eval(source.slice(begin,end));
(async()=>{
 const first=loadFamilyGoogleMaps(), second=loadFamilyGoogleMaps();
 assert.equal(first,second);
 assert.match(inserted.src,/callback=__roxyHomeMapsReady/);
 assert.equal(inserted.onload,undefined);
 let resolved=false;first.then(()=>resolved=true);
 window.google={maps:{}};
 await Promise.resolve();assert.equal(resolved,false);
 const imports=[];
 window.google.maps.importLibrary=async name=>{
   imports.push(name);
   if(name==='core')window.google.maps.ControlPosition={RIGHT_BOTTOM:9};
   if(name==='maps')Object.assign(window.google.maps,{Map:class{},OverlayView:class{}});
 };
 window.__roxyHomeMapsReady();
 const maps=await first;
 assert.equal(maps.ControlPosition.RIGHT_BOTTOM,9);
 assert.deepEqual(imports.sort(),['core','maps','routes']);
 familyMapLoader=null;
 delete maps.ControlPosition;
 await loadFamilyGoogleMaps(); // Partial namespace must still await core.
 assert.equal(maps.ControlPosition.RIGHT_BOTTOM,9);
 assert.equal(imports.length,6);
 console.log('Map asynchronous readiness verified');
})().catch(error=>{console.error(error);process.exitCode=1});
'''
    result = subprocess.run(['node', '-e', script], cwd=root, text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert 'readiness verified' in result.stdout
