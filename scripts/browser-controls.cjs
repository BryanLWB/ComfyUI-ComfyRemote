// Runs only against an isolated CPU ComfyUI. Never load or queue a real user workflow.
const {chromium} = require('playwright');
const fs = require('node:fs/promises');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({channel:'msedge',headless:true});
  try {
    const page = await browser.newPage();
    await page.goto('http://127.0.0.1:8194', {waitUntil:'networkidle'});
    await page.waitForFunction(() => window.comfyAPI?.app?.app && globalThis.LiteGraph?.registered_node_types['Fast Groups Bypasser (rgthree)']);
    const samples = await page.evaluate(async () => {
      const app = window.comfyAPI.app.app;
      const {exportControlledGraph} = await import('/extensions/comfyremote-connector/controls.js');
      const before = JSON.stringify(app.rootGraph.serialize());
      const results = [];
      for (const annotation of [null, 'Note', 'MarkdownNote']) for (const kind of ['Fast Groups Bypasser (rgthree)', 'Fast Groups Muter (rgthree)']) {
        const graph = new LGraph();
        try {
          const source = LiteGraph.createNode('EmptyImage');
          const resize = LiteGraph.createNode('ImageScale');
          const sink = LiteGraph.createNode('SaveImage');
          const tool = LiteGraph.createNode(kind);
          for (const n of [source,resize,sink,tool]) graph.add(n);
          source.pos=[0,0]; resize.pos=[400,0]; sink.pos=[800,0]; tool.pos=[0,400];
          const widget = (n,name,value) => { const w=n.widgets.find(w=>w.name===name); if(!w) throw Error(name); w.value=value; };
          widget(source,'width',64); widget(source,'height',64);
          widget(resize,'width',32); widget(resize,'height',32);
          widget(sink,'filename_prefix','controls-acceptance');
          source.connect(0,resize,0); resize.connect(0,sink,0);
          const group = new LiteGraph.LGraphGroup('任意分组甲');
          group.pos=[350,-100]; group.size=[360,450]; graph.add(group);
          const parent=new LiteGraph.LGraphGroup('任意分组父');parent.pos=[-100,-200];parent.size=[1400,1000];graph.add(parent);
          const note=annotation ? LiteGraph.createNode(annotation) : null;
          if(note){graph.add(note);note.pos=[360,150];note.size=[150,80];}
          const reroute=LiteGraph.createNode('Reroute');graph.add(reroute);reroute.pos=[230,0];source.connect(0,reroute,0);reroute.connect(0,resize,0);
          tool.properties.matchTitle='任意分组';
          resize.mode = kind.includes('Bypass') ? 4 : 2;
          const payload = await exportControlledGraph(graph, g => app.graphToPrompt(g));
          const states = [];
          for (const enabled of [false,true]) {
            resize.mode=enabled ? 0 : kind.includes('Bypass') ? 4 : 2;
            if(note) note.mode=resize.mode;
            states.push({enabled,prompt:(await app.graphToPrompt(graph)).output});
          }
          if (!payload.control_manifest.nodes[0].controls.length) throw Error(JSON.stringify(payload.control_manifest.nodes));
          results.push({kind,annotation,payload,states,ids:{source:String(source.id),resize:String(resize.id),sink:String(sink.id)}});
        } finally { graph.clear(); }
      }
      if (JSON.stringify(app.rootGraph.serialize()) !== before) throw Error('Original canvas changed');
      return results;
    });
    await fs.mkdir('artifacts',{recursive:true});
    await fs.writeFile('artifacts/native-control-fixtures.json',JSON.stringify(samples,null,2));
    assert.equal(samples.length,6);
    const discovery = await page.evaluate(async () => {
      const {discoverControls, analyzeControls, exportControlledGraph} = await import('/extensions/comfyremote-connector/controls.js');
      const app=window.comfyAPI.app.app, before=JSON.stringify(app.rootGraph.serialize()), graph=new LGraph();
      const assert=(v,message)=>{if(!v)throw Error(message);};
      try {
        const tool=LiteGraph.createNode('Fast Groups Bypasser (rgthree)');graph.add(tool);tool.pos=[0,600];
        const members=[];
        for(let i=0;i<2;i++){
          const n=LiteGraph.createNode('ImageScale');graph.add(n);n.pos=[400+i*500,0];members.push(n);
          const group=new LiteGraph.LGraphGroup('同名分组');group.pos=[350+i*500,-100];group.size=[360,450];graph.add(group);
        }
        let m=discoverControls(graph), controls=m.nodes[0].controls;
        assert(controls.length===2&&controls[0].id!==controls[1].id,'Same names must have separate identities');
        assert(controls[0].members[0]===String(members[0].id)&&controls[1].members[0]===String(members[1].id),'Wrong group membership');
        graph._groups[0].title='改名不改变成员';tool.properties.matchTitle='改名';
        assert(discoverControls(graph).nodes[0].controls[0].members[0]===String(members[0].id),'Rename changed target');
        tool.properties.matchTitle='';
        const mixed=LiteGraph.createNode('ImageScale');graph.add(mixed);mixed.pos=[400,180];mixed.mode=4;
        assert(discoverControls(graph).nodes[0].controls[0].default===null,'Mixed state was guessed');
        tool.properties.toggleRestriction='max one';
        assert(discoverControls(graph).nodes[0].reason.includes('联动'),'Restriction not reported');tool.properties.toggleRestriction='default';
        const overlap=new LiteGraph.LGraphGroup('重叠');overlap.pos=[350,-100];overlap.size=[360,450];graph.add(overlap);
        assert(analyzeControls(graph).diagnostics.some(d=>d.code==='overlap'),'Overlap not reported');graph.remove(overlap);
        const virtual=LiteGraph.createNode('Fast Groups Muter (rgthree)');graph.add(virtual);virtual.type='UnsupportedTool';virtual.pos=[0,1000];
        assert(discoverControls(graph).nodes.some(n=>n.class_type==='UnsupportedTool'&&n.reason.includes('尚未支持')),'Unknown tool missing');
        graph.remove(virtual);
        const serialize=graph.serialize.bind(graph);graph.serialize=()=>({...serialize(),definitions:{subgraphs:[{}]}});
        assert(discoverControls(graph).nodes[0].reason.includes('子图'),'Subgraph unsupported reason missing');graph.serialize=serialize;
        graph.clear();
        const plain=LiteGraph.createNode('EmptyImage');graph.add(plain);
        const ordinary=await exportControlledGraph(graph,g=>app.graphToPrompt(g));
        assert(!ordinary.control_manifest&&ordinary.prompt[String(plain.id)],'Ordinary graph changed');
        assert(JSON.stringify(app.rootGraph.serialize())===before,'Root canvas changed');
        return {sameNames:true,renamed:true,mixed:true,restriction:true,overlap:true,unknown:true,subgraphs:true,ordinary:true,canvasUnchanged:true};
      }finally{graph.clear();}
    });
    await fs.writeFile('artifacts/control-discovery-check.json',JSON.stringify(discovery,null,2));
    console.log('Native Bypass/Muter references exported; original canvas unchanged. No generation submitted.');
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
