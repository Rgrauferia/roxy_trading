"""Synthetic atmosphere performance/appearance contracts; no live weather assertions."""
from test_roxy_home_weather_renderer import run_renderer


PAINT_HOST = r"""
const originalElement=doc.createElement;
doc.createElement=tag=>{
 const element=originalElement(tag);
 if(element.ctx){
  const ctx=element.ctx;ctx.fills=[];ctx.gradients=[];ctx.patterns=[];
  for(const kind of ['Linear','Radial'])ctx['create'+kind+'Gradient']=(...coordinates)=>{
   const gradient={kind,coordinates,stops:[],addColorStop(position,color){this.stops.push({position,color})}};
   ctx.gradients.push(gradient);return gradient;
  };
  ctx.createPattern=(image,repetition)=>{const pattern={image,repetition};ctx.patterns.push(pattern);return pattern};
  ctx.fillRect=(...dimensions)=>ctx.fills.push({style:ctx.fillStyle,alpha:ctx.globalAlpha,dimensions,transform:[...ctx.transform]});
 }
 return element;
};
"""


def test_high_refresh_display_does_not_draw_120_frames_per_second():
    run_renderer(r"""
win.RoxyWeatherRenderer.render(root,scene());const canvas=root.children[0];
assert.equal(canvas.dataset.frameRate,'30');tick(0);canvas.ctx.draws=[];
for(let time=8;time<33;time+=8)tick(time);
assert.equal(canvas.ctx.draws.length,0);assert.equal(frames.size,1);
tick(34);assert.equal(canvas.ctx.draws.length,Number(canvas.dataset.particleCount));
assert.equal(frames.size,1);
""")


def test_large_display_has_pixel_budget_not_only_a_dpr_cap():
    run_renderer(r"""
root.rect={width:3840,height:2160,top:0,left:0,right:3840,bottom:2160};
win.RoxyWeatherRenderer.render(root,scene());const canvas=root.children[0];
assert(canvas.width*canvas.height<=1200000);assert(Number(canvas.dataset.particleCount)<=320);
assert(canvas.width<root.rect.width);assert(canvas.width>0&&canvas.height>0);
root.rect={width:360,height:630,top:0,left:0,right:360,bottom:630};resizes[0].fn();
assert.equal(canvas.width,540);assert.equal(canvas.height,945);
""")


def test_low_capability_or_save_data_reduces_work_without_new_permissions():
    for navigator in (
        "{connection:{saveData:true}}",
        "{hardwareConcurrency:4}",
        "{deviceMemory:2}",
    ):
        run_renderer(f"win.navigator={navigator};" + r"""
win.RoxyWeatherRenderer.render(root,scene());const canvas=root.children[0];
assert.equal(canvas.width,360);assert.equal(canvas.height,630);
assert.equal(canvas.dataset.frameRate,'24');assert(Number(canvas.dataset.particleCount)<160);
tick(0);canvas.ctx.draws=[];tick(34);assert.equal(canvas.ctx.draws.length,0);
tick(43);assert(canvas.ctx.draws.length>0);
""")


def test_cloud_texture_is_cached_small_and_drift_does_not_regenerate_it():
    run_renderer(PAINT_HOST + r"""
win.RoxyWeatherRenderer.render(root,scene({clouds:95,wind:25}));const canvas=root.children[0];
const pattern=canvas.ctx.patterns[0],texture=pattern.image;
assert.equal(texture.width,512);assert.equal(texture.height,256);
assert.equal(pattern.repetition,'no-repeat');assert.equal(texture.ctx.gradients.length,26);
const textureFills=texture.ctx.fills.length;tick(0);
const before=canvas.ctx.fills.filter(fill=>fill.style===pattern);
assert.equal(before.length,2);assert(before.every(fill=>fill.alpha>0&&fill.alpha<1));
canvas.ctx.fills=[];tick(10000);
const after=canvas.ctx.fills.filter(fill=>fill.style===pattern);
assert.equal(after.length,2);assert.notDeepEqual(before[0].transform,after[0].transform);
assert.equal(texture.ctx.fills.length,textureFills);assert.equal(canvas.ctx.patterns[0],pattern);
""")


def test_explicit_zero_cloud_cover_does_not_gain_cloud_volumes():
    run_renderer(PAINT_HOST + r"""
win.RoxyWeatherRenderer.render(root,scene({clouds:0}));const canvas=root.children[0];tick(0);
assert.equal(canvas.ctx.fills.filter(fill=>canvas.ctx.patterns.includes(fill.style)).length,0);
assert(canvas.ctx.draws.length>0); // Precipitation condition is separate from cloud coverage.
""")


def test_storm_shading_is_stronger_than_rain_but_never_flashes():
    run_renderer(PAINT_HOST + r"""
const render=win.RoxyWeatherRenderer.render;render(root,scene({clouds:90}));
const canvas=root.children[0];tick(0);
const stormShade=canvas.ctx.fills[0].style.stops[0].color;
canvas.ctx.fills=[];tick(10000);
assert.equal(canvas.ctx.fills[0].style.stops[0].color,stormShade);
render(root,scene({mode:'rain',clouds:90}));canvas.ctx.fills=[];tick(10040);
const rainShade=canvas.ctx.fills[0].style.stops[0].color;
const alpha=value=>Number(value.split(',').at(-1).replace(')',''));
assert(alpha(stormShade)>alpha(rainShade));assert(alpha(stormShade)<.3);
assert(!canvas.ctx.fills.some(fill=>fill.style==='white'||fill.style==='#fff'));
render(root,scene({mode:'sunny'}));assert.equal(root.children.length,0);assert.equal(frames.size,0);
""")


def test_rain_has_sparse_long_near_drops_and_fine_distant_drops():
    run_renderer(r"""
win.RoxyWeatherRenderer.render(root,scene());tick(0);const drops=root.children[0].ctx.draws;
const lengths=drops.map(drop=>drop.dimensions[3]);
assert(lengths.some(length=>length>50));assert(lengths.some(length=>length<8));
assert(lengths.filter(length=>length>45).length<drops.length/4);
const widths=drops.map(drop=>drop.dimensions[2]);assert(Math.max(...widths)>Math.min(...widths)*4);
""")


def test_throttled_frames_still_stop_immediately_on_expiry_or_reduced_motion():
    run_renderer(r"""
win.RoxyWeatherRenderer.render(root,scene());tick(0);const canvas=root.children[0];canvas.ctx.draws=[];
motion.matches=true;tick(8);assert.equal(frames.size,0);assert.equal(root.dataset.weatherMotion,'off');
assert.equal(canvas.ctx.draws.length,0);motion.matches=false;motion.emit('change');tick(10);
now+=2700000;tick(18);assert.equal(frames.size,0);assert.equal(root.children.length,0);
assert.equal(timers.size,0);
""")
