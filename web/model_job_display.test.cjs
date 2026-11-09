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
test('the denial job receipt shows only reported fields: return code, tool events, empty inventories, cost and session',()=>{
  const {jobReceipt}=load('interpretation.js').UptimeInterpretation;
  assert.equal(jobReceipt({provider:{model:'claude-opus-5-5',returncode:0,tool_events:0,tool_inventory:[],mcp_inventory:[],client_reported_cost_usd:0.044891,session:'ce56dc6e'}}),
    ' Receipt: return code 0 · 0 tool events · no tools available · no MCP servers · client-reported cost USD 0.044891 · session ce56dc6e.');
  assert.equal(jobReceipt({provider:{model:'x'}}),'');
  assert.equal(jobReceipt({}),'');
  assert.equal(jobReceipt({provider:{tool_inventory:['Read'],client_reported_cost_usd:'1e3'}}),' Receipt: tools available: Read.');
});
