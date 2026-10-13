const test = require('node:test');
const assert = require('node:assert/strict');
const ui = require('../assets/crypto_pulso/pulso-ui.js');
test('technical summary reports observed prices and no forecast probability', () => {
  const candles = Array.from({length:30}, (_,i) => ({open:100+i,high:102+i,low:99+i,close:101+i}));
  const result = ui.technicalReading(candles, '125');
  assert.equal(result.available,true); assert.equal(result.high,131); assert.equal(result.low,117);
  assert.ok(result.ema9 > result.ema21); assert.match(result.detail,/describe el pasado/);
  assert.equal(Object.hasOwn(result,'probability'),false);
  assert.equal(ui.technicalReading(candles,'').available,false);
});
