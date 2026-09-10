"""Exercise the actual precipitation renderer with a deterministic canvas/RAF host."""
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
HARNESS = r"""
const assert = require('node:assert/strict'), vm = require('node:vm');
let now = Date.parse('2026-09-08T16:30:00Z'), nextId = 1;
const frames = new Map(), timers = new Map(), intersections = [], resizes = [], removals = [];
function events(target={}) {
  const listeners = new Map();
  return Object.assign(target, {
    listeners,
    addEventListener(name, fn) { if (!listeners.has(name)) listeners.set(name, new Set()); listeners.get(name).add(fn); },
    removeEventListener(name, fn) { listeners.get(name)?.delete(fn); },
    emit(name) { for (const fn of [...(listeners.get(name) || [])]) fn(); },
  });
}
function context2d() {
  return {
    draws:[], clears:0, transform:[1,0,0,1,0,0],
    createLinearGradient(){return {addColorStop(){}}}, createRadialGradient(){return {addColorStop(){}}},
    beginPath(){}, moveTo(){}, lineTo(){}, quadraticCurveTo(){}, closePath(){}, fill(){}, fillRect(){},
    stroke(){}, ellipse(){},
    setTransform(...args){this.transform=args},
    clearRect(){this.clears++},
    drawImage(image,...dimensions){this.draws.push({image,dimensions,transform:[...this.transform],alpha:this.globalAlpha})},
  };
}
function element(tag) {
  const el = {tag, dataset:{}, children:[], attributes:{}, isConnected:true, width:0, height:0,
    ownerDocument:doc, rect:{width:360,height:630,top:0,left:0,right:360,bottom:630},
    getBoundingClientRect(){return this.rect},
    setAttribute(name,value){this.attributes[name]=value},
    replaceChildren(...children){this.children=children; for (const child of children) child.parent=this;},
    remove(){if(this.parent)this.parent.children=this.parent.children.filter(child=>child!==this);this.isConnected=false},
  };
  if(tag==='canvas'){el.ctx=context2d();el.getContext=()=>el.ctx;}
  return el;
}
const doc=events({hidden:false,createElement:tag=>element(tag),documentElement:{}});
const motion=events({matches:false});
const win=events({innerWidth:1200,innerHeight:1000,devicePixelRatio:3,
  matchMedia:()=>motion,
  requestAnimationFrame(fn){const id=nextId++;frames.set(id,fn);return id},
  cancelAnimationFrame(id){frames.delete(id)},
  setTimeout(fn,delay){const id=nextId++;timers.set(id,{fn,delay});return id},
  clearTimeout(id){timers.delete(id)},
  IntersectionObserver:class{constructor(fn){this.fn=fn;intersections.push(this)}observe(){}disconnect(){this.disconnected=true}},
  ResizeObserver:class{constructor(fn){this.fn=fn;resizes.push(this)}observe(){}disconnect(){this.disconnected=true}},
  MutationObserver:class{constructor(fn){this.fn=fn;removals.push(this)}observe(){}disconnect(){this.disconnected=true}},
});
function tick(time){const current=[...frames.values()];frames.clear();for(const fn of current)fn(time)}
function scene(overrides={}){return {fresh:true,mode:'storm',validAt:now-900000,fetchedAt:now-100000,intensity:1,drift:75,...overrides}}
const root=element('div');
"""


def run_renderer(script: str) -> None:
    source = (ROOT / "assets/roxy_home_weather_renderer.js").read_text()
    import json

    program = HARNESS + "\nvm.runInNewContext(" + json.dumps(source) + ", {window:win, Date:{now:()=>now}});\n" + script
    result = subprocess.run(["node", "-e", program], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_continuous_rain_has_depth_variation_and_bounded_drawing_cost():
    run_renderer(r"""
const render=win.RoxyWeatherRenderer.render;
const weather=scene();render(root,weather);
assert.equal(root.children.length,1);const canvas=root.children[0];
assert.equal(canvas.width,540);assert.equal(canvas.height,945); // DPR is bounded at 1.5.
assert.equal(canvas.attributes['aria-hidden'],'true');assert.equal(canvas.attributes.role,'presentation');
const count=Number(canvas.dataset.particleCount);assert(count>=200&&count<=320);
tick(0);const first=canvas.ctx.draws.splice(0);assert.equal(first.length,count);
tick(40);const next=canvas.ctx.draws.splice(0); // Sample after the 30fps draw interval.
assert(new Set(first.map(drop=>drop.dimensions[3].toFixed(1))).size>40);
assert(new Set(first.map(drop=>drop.alpha.toFixed(2))).size>20);
const travel=next.map((drop,i)=>drop.transform[5]-first[i].transform[5]);
assert(new Set(travel.map(value=>value.toFixed(1))).size>40);
assert(travel.every((value,i)=>value>0||(first[i].transform[5]/1.5>canvas.height/1.5&&next[i].transform[5]/1.5<=-55))); // Only offscreen drops recycle.
render(root,weather);assert.equal(root.children[0],canvas);assert.equal(frames.size,1);
render(root,scene({mode:'rain',intensity:.12}));
assert(Number(canvas.dataset.particleCount)<count/2);
root.rect={width:2000,height:1200,top:0,left:0,right:2000,bottom:1200};
resizes[0].fn();render(root,scene());assert(Number(canvas.dataset.particleCount)<=320);
""")


def test_snow_and_wind_have_distinct_motion_without_storm_flashes():
    run_renderer(r"""
const render=win.RoxyWeatherRenderer.render;render(root,scene({drift:90}));tick(0);
const canvas=root.children[0];let drawn=canvas.ctx.draws.splice(0);
assert(drawn.every(drop=>drop.transform[1]<0));
render(root,scene({drift:-90}));tick(40);drawn=canvas.ctx.draws.splice(0);
assert(drawn.every(drop=>drop.transform[1]>0));
render(root,scene({mode:'snow',drift:0}));tick(80);drawn=canvas.ctx.draws.splice(0);
assert(drawn.every(drop=>drop.dimensions[2]===drop.dimensions[3]));
tick(120);const second=canvas.ctx.draws.splice(0);
const travel=second.map((drop,i)=>(drop.transform[5]-drawn[i].transform[5])/1.5);
assert(travel.every(value=>value>0&&value<3)); // Under 75px/s: slow flakes at a 40ms sample, not rain.
render(root,scene({mode:'sunny'}));assert.equal(root.children.length,0);assert.equal(frames.size,0);
assert.equal(root.dataset.weatherMotion,'on');
""")


def test_pause_visibility_reduced_motion_and_offscreen_cancel_frames():
    run_renderer(r"""
const render=win.RoxyWeatherRenderer.render;render(root,scene());tick(0);
const canvas=root.children[0], clearBefore=canvas.ctx.clears;
render(root,scene(),{paused:true});assert.equal(frames.size,0);assert.equal(root.dataset.weatherMotion,'off');
assert(canvas.ctx.clears>clearBefore);render(root,scene());assert.equal(frames.size,1);
motion.matches=true;motion.emit('change');assert.equal(frames.size,0);
render(root,scene());assert.equal(frames.size,0);
motion.matches=false;motion.emit('change');assert.equal(frames.size,1);
doc.hidden=true;doc.emit('visibilitychange');assert.equal(frames.size,0);
doc.hidden=false;doc.emit('visibilitychange');assert.equal(frames.size,1);
intersections[0].fn([{isIntersecting:false}]);assert.equal(frames.size,0);
render(root,scene());assert.equal(frames.size,0);
intersections[0].fn([{isIntersecting:true}]);assert.equal(frames.size,1);
win.emit('pagehide');assert.equal(frames.size,0);render(root,scene());assert.equal(frames.size,0);
win.emit('pageshow');assert.equal(frames.size,1);
""")


def test_expired_missing_or_future_model_data_fail_closed_and_cleanup():
    run_renderer(r"""
const render=win.RoxyWeatherRenderer.render;
for(const patch of [{fresh:false},{mode:''},{validAt:NaN},{fetchedAt:NaN},{validAt:now-2700000},{fetchedAt:now+300001}]){
 render(root,scene(patch));assert.equal(root.children.length,0);assert.equal(frames.size,0);
}
render(root,scene());tick(0);assert.equal(frames.size,1);
const expiry=[...timers.values()][0];assert.equal(expiry.delay,1800000);
now+=expiry.delay;expiry.fn();assert.equal(frames.size,0);assert.equal(root.children.length,0);
assert.equal(root.dataset.weatherMotion,'off');assert.equal(timers.size,0);
assert(intersections[0].disconnected&&resizes[0].disconnected&&removals[0].disconnected);
for(const source of [doc,motion,win])assert([...source.listeners.values()].every(set=>set.size===0));
render(root,scene());root.isConnected=false;removals.at(-1).fn();
assert.equal(frames.size,0);assert.equal(timers.size,0);assert.equal(root.children.length,0);
""")


def test_canvas_unavailable_never_breaks_the_map():
    run_renderer(r"""
const original=doc.createElement;doc.createElement=tag=>{const el=original(tag);if(tag==='canvas')el.getContext=()=>null;return el};
assert.doesNotThrow(()=>win.RoxyWeatherRenderer.render(root,scene()));
assert.equal(frames.size,0);assert.equal(root.children.length,0);assert.equal(root.dataset.weatherMotion,'off');
assert([...doc.listeners.values()].every(set=>set.size===0));
""")
