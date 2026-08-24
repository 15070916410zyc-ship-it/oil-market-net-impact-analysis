import assert from "node:assert/strict";
import test from "node:test";
import catalogHandler from "../api/catalog.js";
import seriesHandler from "../api/series.js";

function captureResponse() {
  return {
    headers:{}, statusCode:200, body:null,
    setHeader(name,value){ this.headers[name]=value; },
    status(code){ this.statusCode=code; return this; },
    json(value){ this.body=value; return this; },
  };
}

test("catalog keeps Yahoo results visible and reports a failed FRED search", async () => {
  const previousFetch=global.fetch;
  const previousFred=process.env.FRED_API_KEY;
  process.env.FRED_API_KEY="test-key";
  global.fetch=async (input) => {
    const url=new URL(String(input));
    if (url.hostname==="api.stlouisfed.org") return {ok:false,status:403,json:async()=>({})};
    if (url.hostname==="query2.finance.yahoo.com") return {ok:true,status:200,json:async()=>({quotes:[
      {symbol:"GC=F",shortname:"Gold Dec 26",longname:"Gold Futures",quoteType:"FUTURE",currency:"USD",exchange:"CMX",exchDisp:"COMEX"},
      {symbol:"GLD",shortname:"SPDR Gold Shares",quoteType:"ETF",currency:"USD",exchange:"PCX",exchDisp:"NYSE Arca"},
    ]})};
    if (url.hostname==="api.eia.gov") return {ok:true,status:200,json:async()=>({response:{routes:[],facets:[],frequency:[]}})};
    throw new Error(`Unexpected URL ${url}`);
  };
  try {
    const response=captureResponse();
    await catalogHandler({query:{q:"gold"}},response);
    assert.equal(response.statusCode,200);
    assert.ok(response.body.items.some((item)=>item.id==="YAHOO-R0M9Rg"));
    assert.ok(response.body.items.some((item)=>item.source==="Yahoo Finance / supplementary"));
    assert.ok(response.body.warnings.some((warning)=>warning.includes("FRED")));
    assert.equal(response.body.coverage.Yahoo.official,false);
  } finally {
    global.fetch=previousFetch;
    if (previousFred===undefined) delete process.env.FRED_API_KEY;
    else process.env.FRED_API_KEY=previousFred;
  }
});

test("Yahoo series endpoint decodes a symbol and aggregates real closes monthly", async () => {
  const previousFetch=global.fetch;
  global.fetch=async (input) => {
    const url=new URL(String(input));
    assert.equal(url.hostname,"query1.finance.yahoo.com");
    assert.ok(url.pathname.endsWith("/GC%3DF"));
    return {ok:true,status:200,json:async()=>({chart:{result:[{
      meta:{longName:"Gold Futures",currency:"USD"},
      timestamp:[Date.parse("2026-08-20T00:00:00Z")/1000,Date.parse("2026-08-21T00:00:00Z")/1000],
      indicators:{quote:[{close:[3324.625,3330.875]}]},
    }],error:null}})};
  };
  try {
    const response=captureResponse();
    await seriesHandler({query:{id:"YAHOO-R0M9Rg",frequency:"monthly",start:"2026-08-01",end:"2026-08-31"}},response);
    assert.equal(response.statusCode,200);
    assert.equal(response.body.providerId,"GC=F");
    assert.equal(response.body.source,"Yahoo Finance / supplementary");
    assert.deepEqual(response.body.points,[{date:"2026-08",value:3327.75}]);
  } finally {
    global.fetch=previousFetch;
  }
});
