import test from 'node:test';
import assert from 'node:assert/strict';
import {CDP,keyEvents,summarize,probe} from '../scripts/browser_check.mjs';

class Socket extends EventTarget {
  sent=[];
  send(value){this.sent.push(JSON.parse(value));}
  reply(value){this.dispatchEvent(new MessageEvent('message',{data:JSON.stringify(value)}));}
}

test('Escape sends native key codes with both key events',async()=>{
  const socket=new Socket(),client=new CDP(socket);
  for(const event of keyEvents('Escape')){
    const result=client.send('Input.dispatchKeyEvent',event,'page-session');
    const message=socket.sent.at(-1);
    assert.equal(message.sessionId,'page-session');
    assert.equal(message.params.windowsVirtualKeyCode,27);
    assert.equal(message.params.nativeVirtualKeyCode,27);
    socket.reply({id:message.id,result:{}});await result;
  }
  assert.deepEqual(socket.sent.map(m=>m.params.type),['keyDown','keyUp']);
});
test('out-of-order replies and browser notifications do not mix results',async()=>{
  const socket=new Socket(),client=new CDP(socket);
  const a=client.send('A'),b=client.send('B');
  socket.reply({method:'Page.event',params:{}});
  socket.reply({id:2,result:{name:'B'}});socket.reply({id:1,result:{name:'A'}});
  assert.deepEqual(await a,{name:'A'});assert.deepEqual(await b,{name:'B'});
  assert.equal(client.pending.size,0);
});
test('protocol failures preserve browser error',async()=>{
  const socket=new Socket(),client=new CDP(socket);
  const reply=client.send('Missing.method');
  socket.reply({id:1,error:{message:'Unknown method'}});
  await assert.rejects(reply,/Unknown method/);assert.equal(client.pending.size,0);
});
test('disconnection rejects outstanding and subsequent requests immediately',async()=>{
  const socket=new Socket(),client=new CDP(socket);
  const a=client.send('A'),b=client.send('B');
  socket.dispatchEvent(new Event('close'));
  await assert.rejects(a,/closed/);await assert.rejects(b,/closed/);
  await assert.rejects(client.send('C'),/closed/);assert.equal(socket.sent.length,2);
});
test('malformed response is reported rather than an unhandled parser failure',async()=>{
  const socket=new Socket(),client=new CDP(socket);const reply=client.send('A');
  socket.dispatchEvent(new MessageEvent('message',{data:'not json'}));
  await assert.rejects(reply,/Invalid browser response/);assert.equal(client.pending.size,0);
});
test('silent browser times out and frees pending request',async()=>{
  const socket=new Socket(),client=new CDP(socket);const start=Date.now();
  await assert.rejects(client.send('Never.replies'),/CDP timeout/);
  assert.ok(Date.now()-start<12000);assert.equal(client.pending.size,0);
});
test('automated checks never mark screenshots visually reviewed',()=>{
  const report=summarize([{name:'layout',result:'passed'}],['Hover not tested']);
  assert.equal(report.status,'passed');assert.equal(report.visual_review,'not_run');
  assert.deepEqual(report.limitations,['Hover not tested']);
  assert.equal(summarize([{name:'layout',result:'passed'},{name:'Escape',result:'failed'}]).status,'failed');
  assert.equal(summarize([]).status,'not_run');
});
test('missing browser is unavailable without probing unrelated locations',async()=>{
  const result=await probe('/nonexistent-skill-website-browser');
  assert.equal(result.ready,false);assert.deepEqual(result.browsers,[]);
  assert.equal(result.image_viewing,'unknown');
});
