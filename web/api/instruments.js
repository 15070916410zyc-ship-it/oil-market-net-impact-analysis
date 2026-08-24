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

const bounded=(value,min,max,fallback)=>{const n=Number(value);return Number.isFinite(n)?Math.min(max,Math.max(min,n)):fallback;};
const normalize=(value)=>String(value||"").trim().toLowerCase().replace(/[^a-z0-9\u4e00-\u9fff]+/g," ");

async function sinaQuotes(){
  try{
    const response=await fetch("https://hq.sinajs.cn/list=hf_CL,hf_OIL",{headers:{referer:"https://finance.sina.com.cn/futuremarket/","user-agent":"Mozilla/5.0 Oil-Price-Intelligence/1.0"}});
    if(!response.ok)throw new Error(`Sina quote ${response.status}`);
    const text=await response.text();const quotes={};
    for(const match of text.matchAll(/hq_str_hf_(CL|OIL)="([^"]*)"/g)){
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
  const q=normalize(input.q);const volume=bounded(input.volume,1,1e9,300000),coverage=bounded(input.coverage,0,100,60)/100,futuresShare=bounded(input.futuresShare,0,100,70)/100;
  const quotes=await sinaQuotes();
  const rows=PRODUCTS.filter((item)=>!benchmark||item.benchmark===benchmark).filter((item)=>!q||normalize(`${item.id} ${item.code} ${item.name} ${item.nameZh} ${item.benchmark} ${item.exchange} ${item.kind}`).includes(q)).map((item)=>{
    const target=item.kind==="future"?volume*coverage*futuresShare:volume*coverage*(1-futuresShare);const contracts=Math.round(target/item.size);const quote=item.quoteSymbol?quotes[item.quoteSymbol]:null;
    return{...item,contracts,coveredBarrels:contracts*item.size,roundingError:contracts*item.size-target,quote:quote||null,verification:"Exchange specification verified; quote is indicative and must be rechecked in the broker order ticket"};
  });
  let broker={connected:false,name:"IBKR",message:"No authenticated broker session is connected. The service prepares order tickets but cannot submit orders."};
  if(process.env.IBKR_API_BASE_URL)broker={...broker,connected:true,message:"Broker adapter configured for contract discovery; order submission remains disabled until an authenticated user explicitly authorizes it."};
  response.setHeader("Cache-Control","public, s-maxage=30, stale-while-revalidate=120");
  response.status(200).json({asOf:new Date().toISOString(),benchmark:benchmark||"All",products:rows,quoteWarning:quotes._warning||null,quoteMethod:"AKShare documents futures_foreign_commodity_realtime over Sina Finance; this lightweight adapter reads the same CL/OIL public feed.",broker,executionEnabled:false,disclaimer:"Indicative order preparation only. Expiry, live bid/ask, option strike/premium, margin and tradability must be confirmed in an authorized broker session before execution."});
}
