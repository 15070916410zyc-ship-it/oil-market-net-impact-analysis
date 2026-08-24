import { catalog } from "./_catalog.js";

const EIA_ROOT = "https://api.eia.gov/v2";
const aliases = {
  "原油":"crude oil", "石油":"petroleum oil", "布伦特":"brent", "西德州":"wti", "库存":"inventory stocks storage",
  "产量":"production supply", "消费":"consumption demand", "天然气":"natural gas", "汽油":"gasoline", "柴油":"diesel",
  "电力":"electricity", "煤炭":"coal", "进口":"imports", "出口":"exports", "美元":"dollar", "汇率":"exchange rate",
  "利率":"interest rate yield", "通胀":"inflation cpi", "就业":"employment payroll unemployment", "黄金":"gold", "期货":"futures",
  "地缘政治":"geopolitical risk gpr gprd", "地缘风险":"geopolitical risk gpr gprd", "战争风险":"geopolitical risk gpr gprd",
};
const commonMisspellings = {
  brnt:"brent", prce:"price", pric:"price", invntry:"inventory", inventry:"inventory",
  prodction:"production", consumtion:"consumption", interst:"interest", infltion:"inflation",
  natral:"natural", gass:"gas", petrolium:"petroleum", unemployement:"unemployment",
};
const semanticAliases = {
  gold:["gold","bullion","precious metal"], silver:["silver","precious metal"], copper:["copper","industrial metal"],
  dxy:["broad dollar index","trade weighted dollar"], gdp:["gross domestic product"], cpi:["consumer price index","inflation"],
  ppi:["producer price index"], pce:["personal consumption expenditures","inflation"], vix:["volatility index"],
  spread:["spread","yield spread","credit spread"], shipping:["shipping","freight","transportation"],
  geopolitical:["geopolitical risk","geopolitical uncertainty"], inventory:["inventory","inventories","stocks"],
  黄金:["gold","bullion"], 白银:["silver"], 铜:["copper"], 国内生产总值:["gross domestic product","gdp"],
  利差:["yield spread","credit spread"], 航运:["shipping","freight"], 运价:["freight","shipping"],
};
const normalize = (value) => {
  let text = String(value || "").trim().toLowerCase();
  for (const [zh,en] of Object.entries(aliases)) text = text.replaceAll(zh,` ${en} `);
  return text.replace(/[^a-z0-9\u4e00-\u9fff]+/g," ").replace(/\b(inventories|stocks)\b/g,"inventory").replace(/\bprices\b/g,"price").replace(/\brates\b/g,"rate").trim().split(/\s+/).map((token)=>commonMisspellings[token]||token).join(" ");
};
const words = (value) => normalize(value).split(/\s+/).filter(Boolean);
const trigrams = (value) => { const clean=`  ${normalize(value)} `; return new Set(Array.from({length:Math.max(0,clean.length-2)},(_,i)=>clean.slice(i,i+3))); };
const similarity = (left,right) => { const a=trigrams(left),b=trigrams(right); if(!a.size||!b.size)return 0; let n=0; for(const g of a)if(b.has(g))n++; return 2*n/(a.size+b.size); };
const score = (query,row) => { const hay=normalize(`${row.id||""} ${row.name||""} ${row.nameEn||""} ${row.category||""} ${row.source||""}`); const q=normalize(query), ws=words(query); const coverage=ws.length?ws.filter((w)=>hay.includes(w)).length/ws.length:0; return (hay.includes(q)?4:0)+coverage*3+similarity(q,hay)*2; };
const unique = (rows) => [...new Map(rows.map((row)=>[row.id,row])).values()];
const encodeEia = (route,facet,series) => Buffer.from(JSON.stringify({route,facet,series})).toString("base64url");

async function fredSearch(query,key){
  if(!key||query.length<2)return {rows:[],warning:key?null:"FRED full-text search is not configured"};
  const rawWords=String(query).trim().toLowerCase().split(/[^a-z0-9\u4e00-\u9fff]+/).filter(Boolean);
  const expansions=rawWords.flatMap((word)=>semanticAliases[word]||[]);
  const candidates=[...new Set([normalize(query),...words(query).filter((word)=>word.length>1),...expansions])].filter(Boolean).slice(0,8);
  const batches=await Promise.all(candidates.map(async(candidate)=>{ try{const url=new URL("https://api.stlouisfed.org/fred/series/search"); url.searchParams.set("api_key",key);url.searchParams.set("file_type","json");url.searchParams.set("search_text",candidate);url.searchParams.set("search_type","full_text");url.searchParams.set("limit","100");url.searchParams.set("order_by","search_rank"); const response=await fetch(url,{headers:{accept:"application/json"}}); if(!response.ok)return{rows:[],error:`HTTP ${response.status}`}; const payload=await response.json(); return{rows:(payload.seriess||[]).map((item,index)=>({id:`FRED-${item.id}`,name:item.title,nameEn:item.title,category:"FRED full-text catalog",source:"FRED",unit:item.units_short||item.units,frequency:item.frequency_short||item.frequency,updated:item.last_updated?.slice(0,10)||"",color:"#587a9a",_apiRank:index})),error:null};}catch(error){return{rows:[],error:error instanceof Error?error.message:"network error"};} }));
  // FRED already ranks these rows for the submitted search. Local similarity only
  // reorders them; it must not silently discard valid official results.
  const rows=unique(batches.flatMap((batch)=>batch.rows)).map((row)=>({...row,_score:score(query,row)})).sort((a,b)=>(b._score-a._score)||(a._apiRank-b._apiRank)).slice(0,100);
  const errors=[...new Set(batches.map((batch)=>batch.error).filter(Boolean))];
  return {rows,warning:rows.length?null:errors.length?`FRED full-text search unavailable (${errors.join(", ")})`:null};
}
const encodeYahoo=(symbol)=>Buffer.from(symbol).toString("base64url");
const yahooTypes=new Set(["FUTURE","ETF","INDEX","CURRENCY","CRYPTOCURRENCY","EQUITY","MUTUALFUND"]);
const yahooCategory=(quoteType)=>({FUTURE:"市场期货",ETF:"交易型基金",INDEX:"市场指数",CURRENCY:"汇率",CRYPTOCURRENCY:"数字资产",EQUITY:"上市公司",MUTUALFUND:"共同基金"}[quoteType]||"市场资产");
async function yahooSearch(query){
  if(query.length<2)return {rows:[],warning:null};
  try{
    const expanded=(semanticAliases[String(query).trim().toLowerCase()]||[])[0]||normalize(query);
    const url=new URL("https://query2.finance.yahoo.com/v1/finance/search");
    url.searchParams.set("q",expanded);url.searchParams.set("quotesCount","60");url.searchParams.set("newsCount","0");url.searchParams.set("enableFuzzyQuery","true");
    const response=await fetch(url,{headers:{accept:"application/json","user-agent":"Mozilla/5.0 (compatible; OilPriceIntelligence/1.0)"}});
    if(!response.ok)return {rows:[],warning:`Yahoo supplementary search unavailable (HTTP ${response.status})`};
    const payload=await response.json();
    const rows=(payload.quotes||[]).filter((item)=>item.symbol&&yahooTypes.has(item.quoteType)).map((item,index)=>({
      id:`YAHOO-${encodeYahoo(item.symbol)}`,providerId:item.symbol,name:item.shortname||item.longname||item.symbol,nameEn:item.longname||item.shortname||item.symbol,
      category:yahooCategory(item.quoteType),source:"Yahoo Finance / supplementary",unit:item.currency||"See market metadata",frequency:"日度",updated:"Live catalog",color:"#477c8d",_apiRank:index,_score:score(query,{id:item.symbol,name:`${item.shortname||""} ${item.longname||""}`,source:item.exchDisp||item.exchange||""}),
    }));
    return {rows:unique(rows).sort((a,b)=>(b._score-a._score)||(a._apiRank-b._apiRank)).slice(0,60),warning:null};
  }catch(error){return {rows:[],warning:`Yahoo supplementary search unavailable (${error instanceof Error?error.message:"network error"})`};}
}
const branchHints={petroleum:"oil crude brent wti gasoline diesel jet fuel inventory stocks refinery imports exports futures price production consumption","natural-gas":"natural gas lng henry hub storage price production consumption pipeline",electricity:"electricity power generation price demand capacity renewable solar wind",coal:"coal production consumption price stocks",international:"international country energy oil gas production consumption imports exports",steo:"forecast projection outlook oil gas price production demand","total-energy":"total energy emissions production consumption price",seds:"state energy price production consumption expenditure emissions","crude-oil-imports":"crude oil imports company country grade quantity"};
const directRouteHints={
  "petroleum/pri/spt":"brent wti crude oil petroleum gasoline diesel spot price",
  "petroleum/pri/fut":"crude oil gasoline heating oil futures price",
  "petroleum/stoc/wstk":"crude oil petroleum inventory stocks storage weekly",
  "petroleum/sum/sndw":"petroleum supply demand production imports exports stocks refinery weekly",
  "natural-gas/pri/sum":"natural gas henry hub spot price",
  "natural-gas/stor/wkly":"natural gas storage inventory stocks weekly",
  "electricity/retail-sales":"electricity retail sales price revenue demand",
};
async function eiaJson(path,key){ const url=new URL(`${EIA_ROOT}/${path.replace(/^\/+|\/+$/g,"")}/`);url.searchParams.set("api_key",key);const response=await fetch(url,{headers:{accept:"application/json"}});if(!response.ok)throw new Error(`EIA ${response.status}`);const payload=await response.json();if(payload.error)throw new Error(payload.error.message||"EIA error");return payload.response||{}; }
async function discoverLeaves(branch,key,maxNodes=48){ const queue=[branch],leaves=[],seen=new Set(); while(queue.length&&seen.size<maxNodes){const batch=[];while(queue.length&&batch.length<8&&seen.size+batch.length<maxNodes){const route=queue.shift();if(!seen.has(route)&&!batch.includes(route))batch.push(route);}if(!batch.length)break;batch.forEach((route)=>seen.add(route));const results=await Promise.all(batch.map(async(route)=>{try{return{route,metadata:await eiaJson(route,key)}}catch{return null;}}));for(const item of results){if(!item)continue;const{route,metadata}=item;if(Array.isArray(metadata.routes)&&metadata.routes.length){for(const child of metadata.routes)queue.push(`${route}/${child.id}`);}else if(Array.isArray(metadata.facets)&&metadata.facets.length)leaves.push(item);}}return leaves; }
async function eiaSearch(query,key){
  if(!key||query.length<2)return[]; const q=normalize(query);const priorityRoutes=Object.entries(directRouteHints).map(([route,name])=>({route,rank:score(q,{id:route,name,source:"EIA"})})).filter((row)=>row.rank>.45).sort((a,b)=>b.rank-a.rank).slice(0,3);const directLeaves=(await Promise.all(priorityRoutes.map(async({route})=>{try{return{route,metadata:await eiaJson(route,key)}}catch{return null;}}))).filter(Boolean);const ranked=Object.entries(branchHints).map(([id,name])=>({id,rank:score(q,{id,name,source:"EIA"})})).sort((a,b)=>b.rank-a.rank);const branches=ranked.filter((row)=>row.rank>.28).slice(0,2).map((row)=>row.id);if(!branches.length)branches.push("petroleum","total-energy");
  const leaves=directLeaves.length?directLeaves:(await Promise.all(branches.map((branch)=>discoverLeaves(branch,key,24)))).flat(); const top=leaves.map((leaf)=>({...leaf,rank:score(q,{id:leaf.route,name:`${leaf.metadata.name||""} ${leaf.metadata.description||""} ${directRouteHints[leaf.route]||""}`,source:"EIA"})})).sort((a,b)=>b.rank-a.rank).slice(0,8);
  const batches=await Promise.all(top.map(async({route,metadata})=>{const facet=metadata.facets.find((item)=>item.id==="series")||metadata.facets.find((item)=>/series|msn|product/i.test(item.id));if(!facet)return[];try{const values=await eiaJson(`${route}/facet/${facet.id}`,key);return(values.facets||[]).map((item)=>{const name=item.name||item.alias||item.id;return{id:`EIA2-${encodeEia(route,facet.id,item.id)}`,name,nameEn:name,category:`EIA · ${metadata.name||route}`,source:"EIA",unit:"See series metadata",frequency:metadata.defaultFrequency||"Multiple frequencies",updated:"Live catalog",color:"#9b6d51",_score:score(q,{id:item.id,name,source:route})};});}catch{return[];}}));
  return unique(batches.flat()).filter((row)=>row._score>.3).sort((a,b)=>b._score-a._score).slice(0,80);
}
export default async function handler(request,response){
  const raw=String(request.query?.q||"").trim(),q=normalize(raw);const builtIn=q?catalog.map((item)=>({...item,_score:score(q,item)})).filter((item)=>item._score>.35).sort((a,b)=>b._score-a._score):catalog;let fred=[],eia=[],yahoo=[];const warnings=[];
  if(q.length>=2){const [fr,er,yr]=await Promise.allSettled([fredSearch(raw,process.env.FRED_API_KEY),eiaSearch(raw,process.env.EIA_API_KEY||"DEMO_KEY"),yahooSearch(raw)]);if(fr.status==="fulfilled"){fred=fr.value.rows;if(fr.value.warning)warnings.push(fr.value.warning);}else warnings.push("FRED full-text search unavailable");if(er.status==="fulfilled")eia=er.value;else warnings.push("EIA catalog search unavailable");if(yr.status==="fulfilled"){yahoo=yr.value.rows;if(yr.value.warning)warnings.push(yr.value.warning);}else warnings.push("Yahoo supplementary search unavailable");}
  const rows=unique([...builtIn,...fred,...eia,...yahoo]).map(({_score,_apiRank,...item})=>item);response.setHeader("Cache-Control",q.length>=2&&!eia.length?"private, no-store":"public, s-maxage=900, stale-while-revalidate=7200");response.status(200).json({items:rows,coverage:{FRED:{configured:Boolean(process.env.FRED_API_KEY),available:fred.length>0},EIA:{available:true},Yahoo:{official:false,available:yahoo.length>0}},warnings});
}
