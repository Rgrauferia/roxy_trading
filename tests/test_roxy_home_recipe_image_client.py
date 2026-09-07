"""Execute the actual image-loading JS with fake network/DOM objects, not a browser."""
import json
import shutil
import subprocess
from urllib.parse import urlsplit
from pathlib import Path

import pytest


def test_official_pet_product_images_are_allowed_by_the_image_only_policy():
    from fastapi.testclient import TestClient
    from tools import roxy_home_service
    from roxy_os.home_pet_catalog import PRODUCTS

    policy = TestClient(roxy_home_service.app).get('/lista').headers['content-security-policy']
    directives = {parts[0]: parts[1:] for value in policy.split(';') if (parts := value.strip().split())}
    images = [row['image_url'] for rows in PRODUCTS.values() for row in rows if row.get('image_url', '').startswith('https://')]
    assert images
    for image_url in images:
        origin = 'https://' + urlsplit(image_url).netloc
        assert origin in directives['img-src'], f'Official product photo blocked: {image_url}'
    for origin in ['https://www.kaytee.com', 'https://www.midwesthomes4pets.com', 'https://static.wixstatic.com', 'https://www.harrisonsbirdfoods.com']:
        assert origin not in directives['script-src']
        assert origin not in directives['connect-src']
    assert '*' not in directives['img-src'] and 'https:' not in directives['img-src']


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
    const messages=[];
    const document={createElement(){return {remove(){},set textContent(value){messages.push(value)}}}};
    const host={classList:{add(){},remove(){}},append(){}};
    const navigator={onLine:true};
    const setTimeout=(callback)=>callback();
    const URL={createObjectURL(){return 'blob:exact-photo'},revokeObjectURL(){}};
    const fetch=async()=>{const status=statuses[requests++];return {status,ok:status>=200&&status<300,headers:{get(){return status===200?'image/png':'application/json'}},async blob(){assert.equal(status,200,'202 JSON must never be decoded as an image');blobs++;return {}}}};
    """ + functions + r"""
    hydrateRecipeImage(image,{title:'Bocaditos de pavo',audience:'pet'},host).then(()=>{
      console.log(JSON.stringify({requests,blobs,removed,src,messages}));
    }).catch(error=>{console.error(error);process.exitCode=1});
    """
    output = subprocess.run([node, "-e", script], check=True, capture_output=True, text=True)
    result = json.loads(output.stdout)
    assert result["requests"] == expected_fetches
    assert result["removed"] is removed
    assert result["blobs"] == (0 if removed else 1)
    if not removed:
        assert result["src"] == "blob:exact-photo"
    else:
        assert result["messages"][-1] == 'Foto específica pendiente'
    if 202 in statuses:
        assert 'Roxy está preparando la foto específica…' in result['messages']


def test_lazy_grid_keeps_all_new_cards_until_the_render_is_attached():
    """Building cards off-DOM must not cancel every image except the last one."""
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for frontend unit tests")
    source = (Path(__file__).resolve().parents[1] / "assets/roxy_list.js").read_text()
    functions = source[source.index("  const recipeImage ="):source.index("  const dbPromise =")]
    script = r"""
    const assert=require('node:assert/strict');
    const microtasks=[], watched=new Set(); let notify;
    const queueMicrotask=fn=>microtasks.push(fn);
    class IntersectionObserver {
      constructor(fn){notify=fn}
      observe(image){watched.add(image)}
      unobserve(image){watched.delete(image)}
    }
    const image=()=>({isConnected:false,loading:'lazy',classList:{add(){},remove(){}},addEventListener(){}});
    """ + functions + r"""
    const old=image(); old.isConnected=true;
    hydrateRecipeImage(old,{photo_asset:'/assets/old.webp'},null);
    while(microtasks.length)microtasks.shift()();
    old.isConnected=false;
    const cards=Array.from({length:25},image);
    cards.forEach((img,i)=>hydrateRecipeImage(img,{photo_asset:'/assets/recipe-'+i+'.webp'},null));
    assert.equal(watched.size,26,'unattached cards are still being built');
    assert.equal(microtasks.length,1,'cleanup is batched after the render');
    cards.forEach(img=>img.isConnected=true);
    while(microtasks.length)microtasks.shift()();
    assert.equal(watched.size,25,'only stale cards may be pruned');
    assert.equal(watched.has(old),false);
    notify([{target:cards[0],isIntersecting:false}]);
    assert.equal(cards[0].src,undefined,'offscreen photos remain lazy');
    notify(cards.map(target=>({target,isIntersecting:true})));
    cards.forEach((img,i)=>assert.equal(img.src,'/assets/recipe-'+i+'.webp'));
    assert.equal(watched.size,0);
    const detached=image();
    hydrateRecipeImage(detached,{photo_asset:'/assets/never.webp'},null);
    notify([{target:detached,isIntersecting:true}]);
    assert.equal(detached.src,undefined,'removed images never start requests');
    console.log('25 photos scheduled and loaded');
    """
    subprocess.run([node, "-e", script], check=True, capture_output=True, text=True)


def test_product_photo_failure_has_honest_fallback_not_broken_alt_text():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for frontend unit tests")
    source = (Path(__file__).resolve().parents[1] / "assets/roxy_list.js").read_text()
    functions = source[source.index("  function makePetProductPhoto("):source.index("  function renderPetProducts(")]
    script = r"""
    const assert=require('node:assert/strict');
    const document={createElement(tag){return {tag,events:{},addEventListener(name,fn){this.events[name]=fn},replaceWith(node){this.replacement=node}}}};
    """ + functions + r"""
    const product={brand:'Example',name:'Exact model',image_url:'https://official.example/product.jpg'};
    const photo=makePetProductPhoto(product);
    assert.equal(photo.src,product.image_url);
    assert.equal(photo.referrerPolicy,'no-referrer');
    photo.events.error();
    assert.equal(photo.replacement.tag,'div');
    assert.match(photo.replacement.innerHTML,/Foto oficial no disponible/);
    assert.equal(photo.replacement.src,undefined,'do not substitute another product photo');
    assert.equal(makePetProductPhoto({}).tag,'div');
    """
    subprocess.run([node, "-e", script], check=True, capture_output=True, text=True)


def test_ferret_chicken_heart_preparation_avoids_washing_raw_poultry():
    from roxy_os.home_recipe_fallback import local_recipe_catalog
    recipe = next(row for row in local_recipe_catalog({}) if row['catalog_key'] == 'ferret_chicken_heart_bites')
    assert 'No laves los corazones crudos' in ' '.join(recipe['steps'])
    assert 'Enjuágalos' not in ' '.join(recipe['steps'])
    assert any('74 °C' in step for step in recipe['steps'])
