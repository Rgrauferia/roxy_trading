"""Exercise the real map renderer without Google/network/location access."""
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


HARNESS = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('assets/roxy_list.js', 'utf8');
const begin = source.indexOf('  async function renderFamilyMap(){');
const end = source.indexOf('  async function refreshFamily()', begin);
assert.ok(begin >= 0 && end > begin, 'Real map function must be located');
const realFunction = source.slice(begin, end);

function harness({panel='family', wait=null, existing=false}={}) {
  const calls = {load:0, construct:0, replaced:0, errors:[], options:0, traffic:0, routes:0, markers:0, people:[], mapCenters:[], removed:0};
  const root = {
    replaceChildren(){calls.replaced++},
    set innerHTML(value){calls.errors.push(value)},
    querySelector(){return {addEventListener(){}}},
  };
  const map = {addListener(){return {}}, setOptions(){calls.options++}, setCenter(){}, setZoom(){}, fitBounds(){}, getZoom(){return 14}};
  const context = {
    activePanel:panel, account:{mode:'member',id:'synthetic-A'}, user:'synthetic-home', document:{hidden:false},
    collectionIdentity:()=>`${context.account.mode}:${context.account.id}`,
    homeFamily:{members:[], places:[], map:{provider:'GOOGLE_MAPS'}},
    $: id => id === 'familyMap' ? root : null,
    loadFamilyGoogleMaps:async()=>{calls.load++; if(wait) await wait;},
    familyWeatherMapStyles:styles=>styles,
    google:{maps:{
      Map:class {constructor(_root,options){calls.construct++; calls.mapCenters.push(options.center); return map;}},
      LatLngBounds:class {extend(){} getCenter(){return {lat:0,lng:0}}},
      Circle:class {constructor(){calls.markers++;} setMap(){}},
    }},
    familyMap:existing?map:null, familyMapMarkers:[], familyMapZoomListener:null,
    familyMapStyle:'roadmap', familyMapRetryView:null, familyMapRetryScope:'',
    familyBaseMapScope:()=>JSON.stringify([context.user,context.collectionIdentity()]),
    // The full readiness/controller integration has separate actual-function
    // tests; these fixtures continue to isolate renderer visibility/privacy.
    syncFamilyMapReadiness(){}, trackFamilyBaseMap(){},
    resetFamilyBaseMap(){context.familyMap=null;context.familyMapViewportInitialized=false;},
    familyMapTransitioning:false, familyWeatherGlobeActive:false,
    familySelectedPlaceId:'', familySelectedMemberId:'', familyMapViewportInitialized:false,
    familyHistoryOpen:false, familyHistoryPoints:[],
    createFamilyMapPlace:()=>({setMap(){}}), createFamilyMapPerson:(member,point)=>{calls.people.push({id:member.id,point});return {setMap(){}}},
    syncFamilyTraffic(){calls.traffic++}, familySelectedMember:()=>null,
    clearFamilyRoutes(){}, renderFamilyRouteCard:async()=>{calls.routes++},
    renderFamilyHistoryPanel(){}, activateFamilyWeatherGlobe:async()=>{},
    escapeHtml:value=>String(value), api:async()=>({points:[]}),
  };
  vm.runInNewContext(realFunction+'\nthis.renderMap=renderFamilyMap;',context);
  return {context,calls};
}
"""


def run(body):
    result = subprocess.run(["node", "-e", HARNESS + "\n(async()=>{\n" + body + "\n})().catch(error=>{console.error(error);process.exitCode=1});"], cwd=ROOT, text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr


def test_google_map_never_loads_for_non_nexo_panels():
    run(r"""
for(const panel of ['today','shopping','recipes','plants','pets','fitness','more','']) {
  const h=harness({panel}); await h.context.renderMap();
  assert.equal(h.calls.load,0,`Google loader called from ${panel}`);
  assert.equal(h.calls.construct,0); assert.equal(h.calls.replaced,0);
  assert.equal(h.calls.traffic,0); assert.equal(h.calls.routes,0);
  assert.deepEqual(h.calls.errors,[]);
}
""")


def test_leaving_nexo_while_google_loads_does_not_construct_hidden_map():
    run(r"""
let release; const wait=new Promise(resolve=>{release=resolve});
const h=harness({wait}); const rendering=h.context.renderMap();
assert.equal(h.calls.load,1); assert.equal(h.calls.construct,0);
h.context.activePanel='recipes'; release(); await rendering;
assert.equal(h.calls.construct,0,'Do not construct a map after the user leaves Nexo');
assert.equal(h.calls.replaced,0); assert.equal(h.calls.options,0);
assert.equal(h.calls.traffic,0); assert.equal(h.calls.routes,0);
assert.deepEqual(h.calls.errors,[]);
""")


def test_existing_map_is_not_refreshed_by_background_family_data_on_other_panels():
    run(r"""
const h=harness({panel:'fitness',existing:true}); await h.context.renderMap();
assert.equal(h.calls.load,0); assert.equal(h.calls.construct,0);
assert.equal(h.calls.options,0); assert.equal(h.calls.traffic,0); assert.equal(h.calls.routes,0);
""")


def test_visible_nexo_still_constructs_then_reuses_the_map():
    run(r"""
const h=harness(); await h.context.renderMap();
assert.equal(h.calls.load,1); assert.equal(h.calls.construct,1);
assert.equal(h.calls.replaced,1); assert.equal(h.calls.traffic,1);
assert.deepEqual(h.calls.errors,[]);
await h.context.renderMap();
assert.equal(h.calls.construct,1,'Do not duplicate the Google Map instance');
assert.equal(h.calls.options,1); assert.equal(h.calls.traffic,2);
assert.deepEqual(h.calls.errors,[]);
""")


def test_revoked_sharing_during_loader_never_renders_captured_old_location():
    run(r"""
let release; const wait=new Promise(resolve=>{release=resolve});
const h=harness({wait});
h.context.homeFamily.members=[{id:'synthetic-person',sharing_enabled:true,location:{latitude:12,longitude:34}}];
const rendering=h.context.renderMap(); assert.equal(h.calls.load,1);
h.context.homeFamily={members:[{id:'synthetic-person',sharing_enabled:false,location:{latitude:12,longitude:34}}],places:[],map:{provider:'GOOGLE_MAPS'}};
release(); await rendering;
assert.deepEqual(h.calls.people,[],'Revoked sharing must prevent the pre-await member from creating a marker');
assert.equal(h.calls.mapCenters[0]?.lat,28.5383,'Do not center on a location that was revoked while loading');
assert.equal(h.calls.mapCenters[0]?.lng,-81.3792);
assert.deepEqual(h.calls.errors,[]);
""")


def test_removed_member_during_loader_is_not_restored_from_captured_snapshot():
    run(r"""
let release; const wait=new Promise(resolve=>{release=resolve});
const h=harness({wait});
h.context.homeFamily.members=[{id:'removed-person',sharing_enabled:true,location:{latitude:12,longitude:34}}];
const rendering=h.context.renderMap();
h.context.homeFamily={members:[],places:[],map:{provider:'GOOGLE_MAPS'}};
release(); await rendering;
assert.deepEqual(h.calls.people,[]); assert.equal(h.calls.mapCenters[0]?.lat,28.5383);
assert.deepEqual(h.calls.errors,[]);
""")


def test_location_changed_during_loader_uses_the_latest_authorized_location():
    run(r"""
let release; const wait=new Promise(resolve=>{release=resolve});
const h=harness({wait});
h.context.homeFamily.members=[{id:'moving-person',sharing_enabled:true,location:{latitude:12,longitude:34}}];
const rendering=h.context.renderMap();
h.context.homeFamily={members:[{id:'moving-person',sharing_enabled:true,location:{latitude:56,longitude:78}}],places:[],map:{provider:'GOOGLE_MAPS'}};
release(); await rendering;
assert.equal(h.calls.people.length,1); assert.equal(h.calls.people[0].id,'moving-person');
assert.equal(h.calls.people[0].point.lat,56); assert.equal(h.calls.people[0].point.lng,78);
assert.equal(h.calls.mapCenters[0].lat,56); assert.equal(h.calls.mapCenters[0].lng,78);
assert.deepEqual(h.calls.errors,[]);
""")


def test_refresh_removes_old_marker_without_readding_revoked_member():
    run(r"""
let release; const wait=new Promise(resolve=>{release=resolve});
const h=harness({wait,existing:true});
h.context.familyMapMarkers=[{setMap(value){assert.equal(value,null);h.calls.removed++}}];
h.context.homeFamily.members=[{id:'old-marker',sharing_enabled:true,location:{latitude:12,longitude:34}}];
const rendering=h.context.renderMap();
h.context.homeFamily={members:[{id:'old-marker',sharing_enabled:false,location:null}],places:[],map:{provider:'GOOGLE_MAPS'}};
release(); await rendering;
assert.equal(h.calls.removed,1); assert.deepEqual(h.calls.people,[]);
assert.equal(h.context.familyMapMarkers.length,0); assert.deepEqual(h.calls.errors,[]);
""")
