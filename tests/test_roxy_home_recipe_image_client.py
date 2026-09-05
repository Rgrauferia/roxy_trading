"""Execute the actual image-loading JS with fake network/DOM objects, not a browser."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("statuses,expected_fetches,removed", [([202, 200], 2, False), ([200], 1, False), ([404], 1, True)])
def test_pending_photo_is_not_treated_as_an_image_blob(statuses, expected_fetches, removed):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for frontend unit tests")
    source = (Path(__file__).resolve().parents[1] / "assets/roxy_list.js").read_text()
    functions = source[source.index("  const recipeImage ="):source.index("  const dbPromise =")]
    script = "const statuses=" + json.dumps(statuses) + ";" + r"""
    const assert=require('node:assert/strict');
    let requests=0, blobs=0, removed=false, src='';
    const image={classList:{add(){},remove(){}},addEventListener(){},remove(){removed=true},set src(v){src=v}};
    const host={classList:{add(){},remove(){}}};
    const navigator={onLine:true};
    const setTimeout=(callback)=>callback();
    const URL={createObjectURL(){return 'blob:exact-photo'},revokeObjectURL(){}};
    const fetch=async()=>{const status=statuses[requests++];return {status,ok:status>=200&&status<300,headers:{get(){return status===200?'image/png':'application/json'}},async blob(){assert.equal(status,200,'202 JSON must never be decoded as an image');blobs++;return {}}}};
    """ + functions + r"""
    hydrateRecipeImage(image,{title:'Bocaditos de pavo',audience:'pet'},host).then(()=>{
      console.log(JSON.stringify({requests,blobs,removed,src}));
    }).catch(error=>{console.error(error);process.exitCode=1});
    """
    output = subprocess.run([node, "-e", script], check=True, capture_output=True, text=True)
    result = json.loads(output.stdout)
    assert result["requests"] == expected_fetches
    assert result["removed"] is removed
    assert result["blobs"] == (0 if removed else 1)
    if not removed:
        assert result["src"] == "blob:exact-photo"
