import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import assert from 'node:assert/strict';
const source = await readFile(new URL('../web/controls.js', import.meta.url), 'utf8');
const { analyzeControls, exportControlledGraph } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
globalThis.document = {createElement: () => ({getContext: () => null})};
const node = (id, x, type = 'ImageScale') => ({id, type, mode: 0, properties: {}, isVirtualNode: type.includes('rgthree') || type === 'Reroute', getBounding: () => [x, 0, 20, 20]});
const group = (title, x, width) => ({title, _bounding: [x, -10, width, 100]});
function graph() {
  return {_nodes: [node(1, 10), node(2, 110), node(3, 210), node(29, 310, 'Fast Groups Bypasser (rgthree)')],
    _groups: [group('参考素材', 0, 50), group('独立', 100, 50)], serialize: () => ({})};
}
test('parents including the controller do not suppress independent leaves or change identities', () => {
  const g = graph(); g._groups.unshift(group('输入', 0, 400));
  const {manifest, diagnostics} = analyzeControls(g);
  assert.deepEqual(manifest.nodes[0].controls.map(c => [c.id,c.members]), [['g_1',['1']],['g_2',['2']]]);
  assert.equal(diagnostics[0].group_label, '输入'); assert.equal(diagnostics[0].code, 'parent_group');
  assert.equal(manifest.nodes[0].reason, undefined);
  g._nodes[3].properties.matchTitle = '^输入$';
  assert.equal(analyzeControls(g).diagnostics[0].code, 'unsupported_member');
});
test('duplicates and partial intersections block only conflicting leaves', () => {
  for (const extra of [group('重复', 0, 50), group('交叉', 5, 115)]) {
    const g = graph();
    // Equal raw membership is a conflict regardless of rectangle containment.
    g._groups.push(extra,group('第三组',200,50));
    const {manifest,diagnostics}=analyzeControls(g);
    assert(manifest.nodes[0].controls.some(c=>c.members.includes('3')));
    assert(diagnostics.some(d=>d.code==='overlap' || d.code==='parent_group'));
  }
  const g=graph(); g._nodes.push(node(4,40),node(5,60));
  g._groups=[group('A',0,55),group('B',30,55),group('C',100,50)];
  assert.deepEqual(analyzeControls(g).manifest.nodes[0].controls.map(c=>c.label),['C']);
});
test('cross-controller collisions keep unrelated controls', () => {
  const g=graph(), second=node(30,500,'Fast Groups Muter (rgthree)');
  second.properties.matchTitle='参考素材'; g._nodes.push(second);
  const {manifest,diagnostics}=analyzeControls(g);
  assert.deepEqual(manifest.nodes[0].controls.map(c=>c.label),['独立']);
  assert.equal(manifest.nodes[1].controls.length,0);
  assert.equal(diagnostics.filter(d=>d.code==='controller_overlap').length,2);
});
test('annotations are not targets, wiring and unknown transformations are not guessed', () => {
  const g=graph(); const note=node(4,15,'MarkdownNote'); note.isVirtualNode=true; g._nodes.push(note);
  assert.deepEqual(analyzeControls(g).manifest.nodes[0].controls[0].members,['1']);
  g._nodes.push(node(5,20,'Reroute'));
  assert.deepEqual(analyzeControls(g).manifest.nodes[0].controls.map(c=>c.label),['独立']);
  const unknown=node(6,600,'UnknownTool'); unknown.isVirtualNode=true; unknown.applyToGraph=()=>{}; g._nodes.push(unknown);
  assert(analyzeControls(g).manifest.nodes.every(n=>!n.controls.length));
  g._nodes.pop(); g.serialize=()=>({definitions:{subgraphs:[{}]}});
  assert(analyzeControls(g).manifest.nodes.every(n=>!n.controls.length));
});
test('filters, mixed modes and export failure preserve canvas modes', async () => {
  const g=graph(); g._nodes[3].properties.matchTitle='独立';
  assert.deepEqual(analyzeControls(g).manifest.nodes[0].controls.map(c=>c.id),['g_1']);
  g._nodes[3].properties.matchTitle=''; const second=node(5,20); second.mode=4; g._nodes.push(second);
  assert.equal(analyzeControls(g).manifest.nodes[0].controls[0].default,null);
  const before=g._nodes.map(n=>n.mode); let calls=0;
  await assert.rejects(exportControlledGraph(g,async()=>{if(++calls===2)throw Error('conversion');return {output:{}};}));
  assert.deepEqual(g._nodes.map(n=>n.mode),before);
});
