const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('assets/roxy_list.js','utf8');
const code=source.slice(source.indexOf('  function weatherMeasurement('),source.indexOf('  function renderUpcomingEvent('));
function harness(weather){
  const elements=new Map();
  const $=id=>{if(!elements.has(id))elements.set(id,{textContent:'',attrs:{},children:{},setAttribute(key,value){this.attrs[key]=value},querySelector(key){return this.children[key]??(this.children[key]={textContent:''})}});return elements.get(id)};
  const scope={homeWeather:weather,$,weatherForDay:()=>weather.daily?.[0]||null};vm.createContext(scope);vm.runInContext(code,scope);
  return{scope,elements,render:()=>vm.runInContext('renderWeather()',scope)};
}
test('unknown values never turn into zero readings',()=>{
  const {scope}=harness({});
  for(const value of [null,undefined,true,false,'',' ',NaN,Infinity,[],[0],{},'bad'])assert.equal(scope.weatherMeasurement(value),null);
  for(const value of [0,'0',-4,'82.5'])assert.equal(scope.weatherMeasurement(value),Number(value));
});
test('daily partial data is explicit and real zero survives',()=>{
  const {scope}=harness({});
  assert.equal(scope.weatherDaySummary({temperature_min:0,temperature_max:0,rain_probability:0}),'0–0 °F · 0% de lluvia');
  assert.equal(scope.weatherDaySummary({temperature_max:80,rain_probability:null}),'Máx. 80 °F · Probabilidad de lluvia no disponible');
  assert.equal(scope.weatherDaySummary({temperature_min:32,rain_probability:101}),'Mín. 32 °F · Probabilidad de lluvia no disponible');
  assert.equal(scope.weatherDaySummary({}),'Temperatura no disponible · Probabilidad de lluvia no disponible');
});
test('today and calendar do not display unknown temperature as zero',()=>{
  for(const value of [null,undefined,false,'',NaN]){
    const {render,elements}=harness({status:'READY',current:{temperature:value,feels_like:value,condition:'Nublado'},daily:[]});render();
    for(const prefix of ['today','calendar']){
      assert.match(elements.get(prefix+'WeatherTitle').textContent,/Temperatura no disponible/);
      assert.equal(elements.get(prefix+'WeatherDetail').textContent,'Sensación térmica no disponible');
      assert.doesNotMatch(elements.get(prefix+'WeatherTitle').textContent,/0 °F|NaN|null|undefined/);
    }
  }
});
test('today retains zero Fahrenheit and zero apparent temperature',()=>{
  const {render,elements}=harness({status:'READY',current:{temperature:0,feels_like:0,condition:'Nublado'},daily:[]});render();
  assert.equal(elements.get('todayWeatherTitle').textContent,'0 °F · Nublado');
  assert.equal(elements.get('todayWeatherDetail').textContent,'Sensación de 0 °F');
});
test('partial daily forecast renders known values without invented probability',()=>{
  const {render,elements}=harness({status:'READY',current:{temperature:75,condition:'Nublado'},daily:[{temperature_max:81,temperature_min:null,rain_probability:null}]});render();
  assert.equal(elements.get('calendarWeatherDetail').textContent,'Máx. 81 °F · Probabilidad de lluvia no disponible');
});
test('weather provider outage is not presented as a missing permission',()=>{
  const {render,elements}=harness({status:'UNAVAILABLE'});render();
  assert.equal(elements.get('todayWeatherTitle').textContent,'Clima no disponible');
  assert.equal(elements.get('todayWeatherAction').children.b.textContent,'Reintentar');
  assert.match(elements.get('calendarWeatherAsk').attrs['aria-label'],/ubicación ya guardada/);
  const missing=harness({status:'LOCATION_REQUIRED'});missing.render();
  assert.equal(missing.elements.get('todayWeatherTitle').textContent,'Activa tu ubicación aproximada');
  assert.equal(missing.elements.get('todayWeatherAction').children.b.textContent,'Activar');
});
test('unavailable forecast retry does not request GPS',()=>{
  const handlers={};let gps=0,reloads=0;
  const lines=source.split('\n').filter(line=>line.includes("addEventListener('click'")&&(line.includes("$('todayWeatherAction')")||line.includes("$('calendarWeatherAsk')"))).join('\n');
  const scope={homeWeather:{status:'UNAVAILABLE'},$:id=>({addEventListener:(_event,fn)=>handlers[id]=fn}),captureCommerceLocation:()=>gps++,load:()=>reloads++};
  vm.createContext(scope);vm.runInContext(lines,scope);
  handlers.todayWeatherAction();handlers.calendarWeatherAsk();assert.equal(gps,0);assert.equal(reloads,2);
  scope.homeWeather.status='LOCATION_REQUIRED';handlers.todayWeatherAction();assert.equal(gps,1);
});
test('calendar week and agenda use the nullable daily formatter',()=>{
  const week=source.slice(source.indexOf('  function renderCalendarWeekStrip('),source.indexOf('  function renderCalendarAgenda('));
  const agenda=source.slice(source.indexOf('  function renderCalendarAgenda('),source.indexOf('  function renderCalendarMonth('));
  assert.match(week,/weatherDaySummary\(weather\)/);assert.match(agenda,/weatherDaySummary\(weather\)/);
  assert.doesNotMatch(week+agenda,/\$\{weather\.(temperature_min|temperature_max|rain_probability)\}/);
});
