const test=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
function load(file){const window={};const context={TextEncoder,window,document:{getElementById:()=>null},location:{search:''},URLSearchParams};vm.runInNewContext(fs.readFileSync(__dirname+'/'+file,'utf8'),context);return window;}
test('a denial model job shows the model the server reports and its latest time, in UTC, and nothing it does not report',()=>{
  const {jobTime}=load('interpretation.js').UptimeInterpretation;
  assert.equal(jobTime({state:'SUCCEEDED',provider:{model:'claude-opus-5-5'},submitted_at:'2026-11-09T21:01:00+00:00',started_at:'2026-11-09T21:01:02+00:00',finished_at:'2026-11-09T21:01:40.5+00:00'}),
    ' Model claude-opus-5-5. Finished Nov 9, 2026, 21:01 UTC.');
  assert.equal(jobTime({state:'RUNNING',started_at:'2026-11-09T21:01:02+00:00'}),' Started Nov 9, 2026, 21:01 UTC.');
  assert.equal(jobTime({state:'UNCERTAIN',reason:'provider_timeout'}),'');
  assert.equal(jobTime({state:'REFUSED',provider:{model:''},submitted_at:'not a time'}),' Submitted not a time.');
});
