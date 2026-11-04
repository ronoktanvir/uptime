const test = require('node:test');
const assert = require('node:assert/strict');
const {compareDecimal, money, safeURL} = require('./app.js');
test('decimal ordering preserves balances beyond floating point precision', () => {
  assert.ok(compareDecimal('9007199254740993.01', '9007199254740993.00') > 0);
  assert.ok(compareDecimal('10.00', '9.99') > 0);
  assert.ok(compareDecimal('-10', '-2') < 0);
  assert.equal(compareDecimal('0002.10', '2.1000'), 0);
});
test('financial display preserves server precision and unknown state', () => {
  assert.equal(money('12345678901234567890.001', 'USD'), '$12,345,678,901,234,567,890.001');
  assert.equal(money(null, 'USD'), 'Not determined');
  assert.equal(money('0.00', 'USD'), '$0.00');
});
test('clause links reject executable and local schemes', () => {
  for (const uri of ['javascript:alert(1)', 'data:text/html,hi', 'file:///etc/passwd', '/relative']) assert.equal(safeURL(uri), null);
  assert.equal(safeURL('https://example.org/terms'), 'https://example.org/terms');
});
