"""Actual route renderer with synthetic directions and revocable member data."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r"""
const assert=require('node:assert/strict'), fs=require('node:fs'), vm=require('node:vm');
const source=fs.readFileSync('assets/roxy_list.js','utf8');
const begin=source.indexOf('  async function renderFamilyRouteCard(member){');
const end=source.indexOf('  async function readFamilyProfilePhoto(',begin);
const clearBegin=source.indexOf('  function clearFamilyRoutes(){');
const clearEnd=source.indexOf('  function renderFamilyHistory(',clearBegin);
assert.ok(begin>=0&&end>begin&&clearBegin>=0&&clearEnd>clearBegin);
const actual=source.slice(clearBegin,clearEnd)+source.slice(begin,end);
const response=(name='synthetic')=>({name,routes:[{legs:[{duration:{value:600},duration_in_traffic:{value:720}}]}]});
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}};
function harness(){
  const calls={requests:[],renderers:[],detach:[],html:[]},pending=[];
  const sheet={classList:{add(){},remove(){}}};
  const button={addEventListener(){}};
  const nodes={familyRouteCard:{hidden:true,closest:()=>sheet,set innerHTML(value){calls.html.push(value)},insertAdjacentHTML(){},querySelector:()=>button},familyFocusCard:{hidden:false},familyTrafficSummary:{textContent:'Selecciona una ruta'},familyWeatherSummary:{textContent:'Dato sintético'}};
  const member=id=>({id,display_name:`Persona ${id}`,sharing_enabled:true,updated_at:'2026-09-10T14:00:00Z',location:{latitude:id==='a'?12:56,longitude:id==='a'?34:78}});
  const google={maps:{TravelMode:{DRIVING:'DRIVING'},TrafficModel:{BEST_GUESS:'BEST_GUESS'},
    DirectionsService:class {route(query){calls.requests.push(query);const task=deferred();pending.push(task);return task.promise;}},
    DirectionsRenderer:class {constructor(options){this.options=options;calls.renderers.push(this);}setMap(value){calls.detach.push({renderer:this,value});}},
  }};
  const context={user:'household-a',account:{mode:'member',id:'account-a'},activePanel:'family',familyRouteMode:true,familyRouteRenderGeneration:0,
    homeFamily:{members:[member('a'),member('b')]},familySelectedMemberId:'a',familyMap:{},familyRoutes:[],familyRouteSnapshot:null,familyDirectionsRenderer:null,
    event:{id:'calendar-a',title:'Evento sintético',location:'Destino sintético',starts_at:'2110-09-10T19:00:00Z'},
    $:id=>nodes[id]||null,
    familySelectedMember:()=>context.homeFamily.members.find(row=>row.id===context.familySelectedMemberId)||null,
    familyNextCalendarEvent:()=>context.event,
    localStorage:{getItem:()=>null,setItem(){}},google,window:{google,prompt:()=>null},
    familyClock:()=> 'hora',familyInitials:()=> 'QA',escapeHtml:value=>String(value),
    openFamilyRoute(){},announce(){},renderFamilyExperience(){},renderFamilyMap:async()=>{},
  };
  vm.runInNewContext(actual+'\nthis.renderRoute=renderFamilyRouteCard;this.clearRoutes=clearFamilyRoutes;',context);
  return {context,calls,nodes,pending,member:()=>context.homeFamily.members.find(row=>row.id===context.familySelectedMemberId)};
}
"""


def run(body):
    result = subprocess.run(["node", "-e", HARNESS + "\n(async()=>{\n" + body + "\n})().catch(e=>{console.error(e);process.exitCode=1});"], cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


def test_route_never_requests_directions_outside_nexo_or_without_current_consent():
    run(r"""
for(const change of [h=>h.context.activePanel='recipes',h=>h.context.familyRouteMode=false,h=>h.member().sharing_enabled=false,h=>h.context.account.mode='signed_out',h=>h.context.familySelectedMemberId='b']) {
 const h=harness(),old=h.member();change(h);await h.context.renderRoute(old);
 assert.equal(h.calls.requests.length,0);assert.equal(h.nodes.familyRouteCard.hidden,true);assert.equal(h.context.familyRouteSnapshot,null);
}
""")


def test_revocation_during_directions_prevents_any_result_rendering():
    run(r"""
const h=harness();const task=h.context.renderRoute(h.member());assert.equal(h.pending.length,1);
h.member().sharing_enabled=false;h.pending[0].resolve(response());await task;
assert.equal(h.calls.renderers.length,0);assert.deepEqual(h.calls.html,[]);assert.equal(h.context.familyRouteSnapshot,null);assert.equal(h.nodes.familyRouteCard.hidden,true);
""")


def test_pending_route_is_discarded_when_panel_mode_member_identity_or_destination_changes():
    run(r"""
for(const change of [h=>h.context.activePanel='plants',h=>h.context.familyRouteMode=false,h=>h.context.familySelectedMemberId='b',h=>h.context.user='household-b',h=>h.context.account.id='account-b',h=>h.context.account.mode='signed_out',h=>h.context.event={...h.context.event,location:'Otro destino'},h=>h.context.event={...h.context.event,starts_at:'2110-09-10T20:00:00Z'},h=>h.context.homeFamily.members=[]]) {
 const h=harness();const task=h.context.renderRoute(h.member());change(h);h.pending[0].resolve(response());await task;
 assert.equal(h.calls.renderers.length,0);assert.equal(h.calls.html.length,0);assert.equal(h.context.familyRouteSnapshot,null);
}
""")


def test_location_changed_while_loading_cannot_render_route_from_old_point():
    run(r"""
const h=harness();const task=h.context.renderRoute(h.member());h.member().location={latitude:90,longitude:0};h.pending[0].resolve(response());await task;
assert.equal(h.calls.renderers.length,0);assert.equal(h.calls.html.length,0);assert.equal(h.context.familyRouteSnapshot,null);
""")


def test_old_response_never_removes_or_overwrites_new_member_route():
    run(r"""
const h=harness();const first=h.context.renderRoute(h.member());h.context.familySelectedMemberId='b';
const second=h.context.renderRoute(h.member());h.pending[1].resolve(response('new'));await second;
const renderer=h.context.familyDirectionsRenderer;const html=h.calls.html[0];
h.pending[0].resolve(response('old'));await first;
assert.equal(h.calls.renderers.length,1);assert.equal(h.context.familyDirectionsRenderer,renderer);assert.equal(h.calls.detach.length,0);
assert.equal(h.context.familyRouteSnapshot.result.name,'new');assert.equal(h.calls.html.length,1);assert.equal(h.calls.html[0],html);assert.equal(h.nodes.familyRouteCard.hidden,false);
""")


def test_late_rejection_does_not_show_old_fallback_or_clear_new_route():
    run(r"""
const h=harness();const first=h.context.renderRoute(h.member());h.context.familySelectedMemberId='b';
const second=h.context.renderRoute(h.member());h.pending[1].resolve(response('new'));await second;
h.pending[0].reject(new Error('Provider timeout'));await first;
assert.equal(h.calls.html.length,1);assert.equal(h.context.familyRouteSnapshot.result.name,'new');assert.equal(h.calls.detach.length,0);
""")


def test_clear_routes_invalidates_pending_request_and_clears_both_map_layers():
    run(r"""
const h=harness();let detached=0;h.context.familyRoutes=[{setMap(value){assert.equal(value,null);detached++}}];
const first=h.context.renderRoute(h.member());h.context.clearRoutes();h.pending[0].resolve(response('obsolete'));await first;
assert.equal(detached,1);assert.equal(h.calls.renderers.length,0);assert.equal(h.calls.html.length,0);assert.equal(h.context.familyRouteSnapshot,null);
const second=h.context.renderRoute(h.member());h.pending[1].resolve(response('visible'));await second;
assert.equal(h.calls.renderers.length,1);h.context.clearRoutes();assert.equal(h.calls.detach.length,1);assert.equal(h.context.familyDirectionsRenderer,null);assert.equal(h.context.familyRouteSnapshot,null);
""")


def test_valid_current_route_still_renders_and_uses_latest_selected_member():
    run(r"""
const h=harness();const obsolete={...h.member(),location:{latitude:1,longitude:2}};
const task=h.context.renderRoute(obsolete);assert.equal(h.calls.requests[0].origin.lat,12);assert.equal(h.calls.requests[0].origin.lng,34);
h.pending[0].resolve(response('current'));await task;
assert.equal(h.calls.renderers.length,1);assert.equal(h.context.familyRouteSnapshot.result.name,'current');assert.equal(h.calls.html.length,1);assert.equal(h.nodes.familyRouteCard.hidden,false);
""")
