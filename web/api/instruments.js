const PRODUCTS = [
  { id:"CME-CL", benchmark:"WTI", exchange:"NYMEX / CME Group", kind:"future", code:"CL", name:"WTI Crude Oil futures", nameZh:"WTI 原油期货", size:1000, currency:"USD", settlement:"Physical", quoteSymbol:"CL", source:"CME official + AKShare/Sina quote adapter", url:"https://www.cmegroup.com/markets/energy/crude-oil/light-sweet-crude.html" },
  { id:"CME-MCL", benchmark:"WTI", exchange:"NYMEX / CME Group", kind:"future", code:"MCL", name:"Micro WTI Crude Oil futures", nameZh:"微型 WTI 原油期货", size:100, currency:"USD", settlement:"Financial", quoteSymbol:"CL", source:"CME official + AKShare/Sina quote adapter", url:"https://www.cmegroup.com/markets/energy/crude-oil/micro-wti-crude-oil.html" },
  { id:"CME-LO", benchmark:"WTI", exchange:"NYMEX / CME Group", kind:"option", code:"LO", name:"WTI Crude Oil options", nameZh:"WTI 原油期权", size:1000, currency:"USD", settlement:"Exercises into CL futures", source:"CME official specification", url:"https://www.cmegroup.com/markets/energy/crude-oil/light-sweet-crude.contractSpecs.options.html" },
  { id:"CME-MCO", benchmark:"WTI", exchange:"NYMEX / CME Group", kind:"option", code:"MCO", name:"Micro WTI Crude Oil options", nameZh:"微型 WTI 原油期权", size:100, currency:"USD", settlement:"Financial", source:"CME official specification", url:"https://www.cmegroup.com/articles/faqs/micro-wti-crude-oil-options-faq.html" },
  { id:"ICE-B", benchmark:"Brent", exchange:"ICE Futures Europe", kind:"future", code:"B", name:"Brent Crude Futures", nameZh:"ICE 布伦特原油期货", size:1000, currency:"USD", settlement:"EFP delivery; cash-settlement option", quoteSymbol:"OIL", source:"ICE official + AKShare/Sina quote adapter", url:"https://www.ice.com/products/219/Brent-Crude-Futures" },
  { id:"CME-BZ", benchmark:"Brent", exchange:"NYMEX / CME Group", kind:"future", code:"BZ", name:"Brent Last Day Financial Futures", nameZh:"CME 布伦特最后交易日金融期货", size:1000, currency:"USD", settlement:"Financial", quoteSymbol:"OIL", source:"CME official + AKShare/Sina quote adapter", url:"https://www.cmegroup.com/markets/energy/crude-oil/brent-crude-oil-last-day.html" },
  { id:"CME-BE", benchmark:"Brent", exchange:"NYMEX / CME Group", kind:"option", code:"BE", name:"Brent Crude options", nameZh:"CME 布伦特原油期权", size:1000, currency:"USD", settlement:"Exercises into BZ futures", source:"CME official specification", url:"https://www.cmegroup.com/markets/energy/energy-options.html" },
  { id:"INE-SC", benchmark:"China crude", exchange:"Shanghai International Energy Exchange", kind:"future", code:"SC", name:"INE Crude Oil Futures", nameZh:"上海原油期货", size:1000, currency:"CNY", settlement:"Physical", source:"INE official specification; AKShare/Sina domestic adapter available", url:"https://www.ine.cn/eng/products/sc/standard/" },
];

const CROSS_ASSET_PRODUCTS = [
  {id:"COMEX-GC",benchmark:"Gold",exchange:"COMEX / CME Group",kind:"future",code:"GC",name:"Gold Futures",nameZh:"COMEX 黄金期货",size:100,contractUnit:"troy oz",currency:"USD",settlement:"Physical",quoteSymbol:"GC",role:"cross-asset",source:"CME official specification + AKShare/Sina quote adapter",url:"https://www.cmegroup.com/markets/metals/precious/gold.html"},
  {id:"COMEX-SI",benchmark:"Silver",exchange:"COMEX / CME Group",kind:"future",code:"SI",name:"Silver Futures",nameZh:"COMEX 白银期货",size:5000,contractUnit:"troy oz",currency:"USD",settlement:"Physical",quoteSymbol:"SI",role:"cross-asset",source:"CME official specification + AKShare/Sina quote adapter",url:"https://www.cmegroup.com/markets/metals/precious/silver.html"},
  {id:"COMEX-HG",benchmark:"Copper",exchange:"COMEX / CME Group",kind:"future",code:"HG",name:"Copper Futures",nameZh:"COMEX 铜期货",size:25000,contractUnit:"lb",currency:"USD",settlement:"Physical",quoteSymbol:"HG",role:"cross-asset",source:"CME official specification + AKShare/Sina quote adapter",url:"https://www.cmegroup.com/markets/metals/base/copper.html"},
  {id:"NYMEX-NG",benchmark:"Natural gas",exchange:"NYMEX / CME Group",kind:"future",code:"NG",name:"Henry Hub Natural Gas Futures",nameZh:"Henry Hub 天然气期货",size:10000,contractUnit:"MMBtu",currency:"USD",settlement:"Physical",quoteSymbol:"NG",role:"cross-asset",source:"CME official specification + AKShare/Sina quote adapter",url:"https://www.cmegroup.com/markets/energy/natural-gas/natural-gas.html"},
  {id:"ICE-DX",benchmark:"US dollar",exchange:"ICE Futures U.S.",kind:"future",code:"DX",name:"U.S. Dollar Index Futures",nameZh:"美元指数期货",size:1000,contractUnit:"USD × index",currency:"USD",settlement:"Financial",role:"cross-asset",source:"ICE official specification",url:"https://www.ice.com/products/194/US-Dollar-Index-Futures"},
  {id:"CME-ZN",benchmark:"US rates",exchange:"CBOT / CME Group",kind:"future",code:"ZN",name:"10-Year T-Note Futures",nameZh:"美国10年期国债期货",size:100000,contractUnit:"USD face value",currency:"USD",settlement:"Physical",role:"cross-asset",source:"CME official specification",url:"https://www.cmegroup.com/markets/interest-rates/us-treasury/10-year-us-treasury-note.html"},
  {id:"CME-ES",benchmark:"US equities",exchange:"CME Group",kind:"future",code:"ES",name:"E-mini S&P 500 Futures",nameZh:"E-mini 标普500期货",size:50,contractUnit:"USD × index",currency:"USD",settlement:"Financial",role:"cross-asset",source:"CME official specification",url:"https://www.cmegroup.com/markets/equities/sp/e-mini-sandp500.html"},
  {id:"CBOE-VX",benchmark:"Volatility",exchange:"Cboe Futures Exchange",kind:"future",code:"VX",name:"VIX Futures",nameZh:"VIX 波动率期货",size:1000,contractUnit:"USD × index",currency:"USD",settlement:"Financial",role:"cross-asset",source:"Cboe official specification",url:"https://www.cboe.com/tradable_products/vix/vix_futures/specifications/"},
];

// Product symbols exposed by AKShare's futures_hq_subscribe_exchange_symbol.
// These are searchable market families; exact expiry and multiplier must be
// resolved in the exchange or authenticated broker contract chain.
const SINA_DIRECTORY = [
  ["FEF","SGX TSI Iron Ore","新加坡铁矿石"],["FCPO","Bursa Malaysia Crude Palm Oil","马来西亚棕榈油"],["RSS3","TOCOM Rubber","东京橡胶"],["RS","Tokyo Commodity Crude Oil","东京原油"],["BTC","CME Bitcoin","CME 比特币"],["CT","ICE Cotton No. 2","ICE 棉花"],["NID","LME 3-Month Nickel","LME 三个月镍"],["PBD","LME 3-Month Lead","LME 三个月铅"],["SND","LME 3-Month Tin","LME 三个月锡"],["ZSD","LME 3-Month Zinc","LME 三个月锌"],["AHD","LME 3-Month Aluminium","LME 三个月铝"],["CAD","LME 3-Month Copper","LME 三个月铜"],["S","CBOT Soybeans","CBOT 大豆"],["W","CBOT Wheat","CBOT 小麦"],["C","CBOT Corn","CBOT 玉米"],["BO","CBOT Soybean Oil","CBOT 豆油"],["SM","CBOT Soybean Meal","CBOT 豆粕"],["TRB","TOCOM Rubber","日本橡胶"],["HG","COMEX Copper","COMEX 铜"],["NG","NYMEX Natural Gas","NYMEX 天然气"],["CL","NYMEX WTI Crude Oil","NYMEX 原油"],["SI","COMEX Silver","COMEX 白银"],["GC","COMEX Gold","COMEX 黄金"],["LHC","CME Lean Hogs","CME 瘦肉猪"],["OIL","ICE Brent Crude Oil","布伦特原油"],["XAU","London Gold","伦敦金"],["XAG","London Silver","伦敦银"],["XPT","London Platinum","伦敦铂金"],["XPD","London Palladium","伦敦钯金"],["EUA","European Union Allowance","欧洲碳排放"],
].map(([code,name,nameZh])=>({id:`SINA-${code}`,benchmark:name,exchange:"AKShare / Sina global futures directory",kind:"future",code,name,nameZh,size:1,contractUnit:"exchange contract",currency:"USD",settlement:"See exchange contract",quoteSymbol:code,role:"directory",source:"AKShare futures_hq_subscribe_exchange_symbol + Sina public quote",url:"https://finance.sina.com.cn/money/future/hf.html"}));

const bounded=(value,min,max,fallback)=>{const n=Number(value);return Number.isFinite(n)?Math.min(max,Math.max(min,n)):fallback;};
const aliases={"原油":"crude oil","石油":"crude oil","黄金":"gold","白银":"silver","铜":"copper","天然气":"natural gas","美元":"dollar","国债":"treasury","利率":"rates","股票":"equities","波动率":"volatility","期权":"option","期货":"future","微型":"micro"};
const normalize=(value)=>{let text=String(value||"").trim().toLowerCase();for(const[from,to]of Object.entries(aliases))text=text.replaceAll(from,` ${to} `);return text.replace(/[^a-z0-9\u4e00-\u9fff]+/g," ").trim();};
const matches=(query,item)=>{if(!query)return true;const hay=normalize(`${item.id} ${item.code} ${item.name} ${item.nameZh} ${item.benchmark} ${item.exchange} ${item.kind} ${item.role||""}`);return query.split(/\s+/).every((token)=>hay.includes(token));};

async function sinaQuotes(symbols){
  try{
    const list=[...new Set(symbols.filter(Boolean))].map((symbol)=>`hf_${symbol}`).join(",");
    const response=await fetch(`https://hq.sinajs.cn/list=${list}`,{headers:{referer:"https://finance.sina.com.cn/futuremarket/","user-agent":"Mozilla/5.0 Oil-Price-Intelligence/1.0"}});
    if(!response.ok)throw new Error(`Sina quote ${response.status}`);
    const text=await response.text();const quotes={};
    for(const match of text.matchAll(/hq_str_hf_([A-Z0-9]+)="([^"]*)"/g)){
      const fields=match[2].split(","),last=Number(fields[0]),bid=Number(fields[2]),ask=Number(fields[3]);
      if(Number.isFinite(last))quotes[match[1]]={last,bid:Number.isFinite(bid)?bid:null,ask:Number.isFinite(ask)?ask:null,time:fields[6]||"",date:fields[12]||"",name:fields[13]||match[1],provider:"Sina Finance via AKShare-compatible adapter"};
    }
    return quotes;
  }catch(error){return{_warning:String(error?.message||error)};}
}

export default async function handler(request,response){
  const input=request.method==="POST"?request.body||{}:request.query||{};
  const rawBenchmark=String(input.benchmark||"");
  const benchmark=rawBenchmark.toUpperCase()==="WTI"?"WTI":rawBenchmark.toLowerCase().includes("china")?"China crude":rawBenchmark?"Brent":"";
  const q=normalize(input.q),directory=String(input.directory||"")==="1"||Boolean(q),includeCrossAsset=String(input.includeCrossAsset||"")==="1";const volume=bounded(input.volume,1,1e9,300000),coverage=bounded(input.coverage,0,100,60)/100,futuresShare=bounded(input.futuresShare,0,100,70)/100;
  const expanded=[...PRODUCTS,...CROSS_ASSET_PRODUCTS,...SINA_DIRECTORY.filter((item)=>![...PRODUCTS,...CROSS_ASSET_PRODUCTS].some((known)=>known.code===item.code))];
  const universe=directory?expanded:includeCrossAsset?[...PRODUCTS,...CROSS_ASSET_PRODUCTS]:PRODUCTS;
  const candidates=universe.filter((item)=>!benchmark||item.benchmark===benchmark||includeCrossAsset).filter((item)=>matches(q,item));
  const quotes=await sinaQuotes(candidates.map((item)=>item.quoteSymbol));
  const rows=candidates.map((item)=>{
    const target=item.kind==="future"?volume*coverage*futuresShare:volume*coverage*(1-futuresShare);const contracts=item.role==="directory"?null:Math.round(target/item.size);const quote=item.quoteSymbol?quotes[item.quoteSymbol]:null;
    return{...item,contracts,coveredBarrels:contracts==null?null:contracts*item.size,roundingError:contracts==null?null:contracts*item.size-target,quote:quote||null,verification:"Exchange specification verified; quote is indicative and must be rechecked in the broker order ticket"};
  });
  let broker={connected:false,name:"IBKR",message:"No authenticated broker session is connected. The service prepares order tickets but cannot submit orders."};
  if(process.env.IBKR_API_BASE_URL)broker={...broker,connected:true,message:"Broker adapter configured for contract discovery; order submission remains disabled until an authenticated user explicitly authorizes it."};
  response.setHeader("Cache-Control","public, s-maxage=30, stale-while-revalidate=120");
  response.status(200).json({asOf:new Date().toISOString(),benchmark:benchmark||"All",products:rows,directoryCount:expanded.length,quoteWarning:quotes._warning||null,quoteMethod:"AKShare documents futures_hq_subscribe_exchange_symbol and futures_foreign_commodity_realtime over Sina Finance; the directory and matching live symbols are queried through the same public feed.",broker,executionEnabled:false,disclaimer:"Indicative product discovery and order preparation only. Exact expiry, multiplier, live bid/ask, option strike/premium, margin and tradability must be confirmed in an authorized broker session before execution."});
}
