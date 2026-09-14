const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../assets/roxy_list.js'), 'utf8');
const bridge = source.slice(source.indexOf('  function openFitnessCalendarDraft('), source.indexOf('  function mountFitness()'));

function harness(mode = 'member') {
  const controls = {}, opened = [], navigated = [], notices = [];
  const context = {account: {mode}, Date, Number, announce: s => notices.push(s),
    $: id => controls[id] ||= {value: 'previous'},
    selectPanel: p => navigated.push(p), openCalendarEvent: (...args) => opened.push(args)};
  vm.runInNewContext(bridge + '\nthis.open = openFitnessCalendarDraft;', context);
  return {...context, controls, opened, navigated, notices};
}

test('saved private activity opens only a generic review draft at the server-confirmed instant', () => {
  const h = harness();
  h.open({date: '2026-09-14', time: '08:00', timezone: 'America/Los_Angeles',
    starts_at: '2026-09-14T15:00:00+00:00', program_id: 'gentle-strength', title: 'Private title'});
  assert.deepEqual(h.navigated, ['calendar']);
  const draft = h.opened[0][0];
  assert.equal(draft._draft, true);
  assert.equal(draft.starts_at, '2026-09-14T15:00:00.000Z');
  assert.equal(draft.title, 'Actividad personal');
  assert.equal(draft.notes, '');
  assert.equal(draft.reminder_minutes, 0);
  assert.equal(h.controls.calendarEventDuration.value, '');
  assert.doesNotMatch(JSON.stringify(draft), /gentle-strength|Private title/);
  assert.match(h.notices[0], /visible en el calendario del hogar/);
});

test('unconfirmed clock, invalid date and signed-out callbacks do not open a calendar draft', () => {
  const h = harness();
  h.open({date: '2026-09-14', time: '08:00'});
  h.open({date: 'invalid', starts_at: '2026-09-14T15:00:00Z'});
  assert.equal(h.opened.length, 0);
  const expired = harness('signed_out');
  expired.open('2026-09-14');
  assert.equal(expired.opened.length, 0);
});

test('legacy educational agenda still opens its chosen day and requires a duration choice', () => {
  const h = harness();
  h.open('2026-09-14');
  assert.equal(h.opened[0][0], null);
  assert.equal(h.opened[0][1].getDate(), 14);
  assert.equal(h.controls.calendarEventDuration.value, '');
  assert.match(fs.readFileSync(require('node:path').join(__dirname, '../assets/roxy_list.html'), 'utf8'), /id="calendarEventDuration" required/);
});

test('calendar review includes chosen end, duration and an honest no-reminder label before confirmation', () => {
  const nodes = {}, opened = [];
  const context = {Date, Number, Math, pendingCalendarDraft: null,
    document: {createElement: tag => ({tag, textContent: ''})},
    $: id => nodes[id] ||= {replaceChildren() {this.children = [];}, append(...els) {this.children.push(...els);}, showModal() {opened.push(id);}},
    dateKey: d => d.toISOString().slice(0,10),
    formatCalendarDay: d => d.toISOString().slice(0,10),
    formatCalendarTime: d => d.toISOString().slice(11,16), calendarCategories: {PERSONAL: 'Personal'}};
  const code = source.slice(source.indexOf('  function showCalendarConfirmation('), source.indexOf('  async function submitCalendarEvent('));
  vm.runInNewContext(code + '\nthis.show = showCalendarConfirmation;', context);
  const draft = {title: 'Actividad personal', starts_at: '2026-09-16T22:30:00Z', ends_at: '2026-09-16T23:00:00Z', category: 'PERSONAL', reminder_minutes: 0};
  context.show(draft);
  assert.match(nodes.calendarConfirmSummary.children[1].textContent, /22:30 – 23:00 \(30 min\).*Sin aviso/);
  assert.deepEqual(opened, ['calendarConfirmDialog']);
  assert.equal(context.pendingCalendarDraft._mode, 'create');
  context.show({...draft, starts_at: '2026-09-16T23:30:00Z', ends_at: '2026-09-17T00:00:00Z', reminder_minutes: 60}, [], 'edit');
  assert.match(nodes.calendarConfirmSummary.children[1].textContent, /2026-09-17 00:00 \(30 min\).*Aviso 1 hora antes/);
  assert.equal(context.pendingCalendarDraft._mode, 'edit');
});
