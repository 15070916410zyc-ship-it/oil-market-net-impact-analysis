import { expect, test } from "@playwright/test";

test("professional controls and English dates are fully localized", async ({ page }) => {
  await page.goto("http://localhost:4174/professional");
  await expect(page.getByRole("heading", { name: "多尺度净影响分析" })).toBeVisible();
  await page.locator(".utility button").click();
  await expect(page.getByRole("heading", { name: "Multi-scale net-impact analysis" })).toBeVisible();
  await expect(page.locator("input[type=date]")).toHaveCount(0);
  await expect(page.locator(".date-field input").first()).toHaveAttribute("placeholder", "YYYY-MM-DD");
  await expect(page.locator(".date-field em").first()).toHaveText("YYYY-MM-DD");
});

test("number steppers and mode switching respond immediately", async ({ page }) => {
  await page.goto("http://localhost:4174/professional");
  const componentField = page.locator(".field").filter({ hasText: "分量数量" });
  await expect(componentField.locator("input")).toHaveValue("5");
  await componentField.locator(".stepper button").last().click();
  await expect(componentField.locator("input")).toHaveValue("6");
  await page.getByRole("button", { name: "决策模式" }).click();
  await expect(page).toHaveURL(/\/decision$/);
  await page.getByRole("button", { name: "专业模式" }).click();
  await expect(page).toHaveURL(/\/professional$/);
});

test("decision accounting, advanced variables and multiple real-product plans render together", async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/health")) return route.fulfill({ json: { ok:true } });
    if (url.pathname.endsWith("/catalog")) return route.fulfill({ json: { items: [{ id:"GPRD",name:"地缘政治风险指数（传统日度 GPR）",nameEn:"Geopolitical Risk Index (traditional daily GPR)",source:"Caldara-Iacoviello GPR",unit:"指数",frequency:"日度",updated:"2026-08-17",color:"#c47d59" },{ id:"FRED-DGS10",name:"美国10年期国债收益率",nameEn:"US 10-Year Treasury Yield",source:"FRED",unit:"%",frequency:"Daily",updated:"2026-08-20",color:"#587a9a" }] } });
    if (url.pathname.endsWith("/gprd")) return route.fulfill({ json: { updated:"2026-08-17",points:[{date:"2026-08-17",value:144.473}] } });
    if (url.pathname.endsWith("/series")) return route.fulfill({ json: { updated:"2026-08-20",points:[{date:"2026-08-20",value:86.48}] } });
    if (url.pathname.endsWith("/instruments")) return route.fulfill({ json: { asOf:"2026-08-24",benchmark:"Brent",broker:{connected:false,name:"IBKR",message:"not configured"},executionEnabled:false,disclaimer:"scenario only",products:[
      {id:"ICE-B",benchmark:"Brent",exchange:"ICE Futures Europe",kind:"future",code:"B",name:"Brent Crude Futures",nameZh:"ICE 布伦特原油期货",size:1000,settlement:"EFP delivery",url:"https://www.ice.com/products/219/Brent-Crude-Futures",contracts:126,coveredBarrels:126000,roundingError:0,verification:"Exchange product specification",quote:{last:91,bid:90.99,ask:91.01,time:"12:00:00",date:"2026-08-24",name:"布伦特原油",provider:"Sina"}},
      {id:"CME-BZ",benchmark:"Brent",exchange:"NYMEX / CME Group",kind:"future",code:"BZ",name:"Brent Last Day Financial Futures",size:1000,settlement:"Financial",url:"https://www.cmegroup.com/",contracts:126,coveredBarrels:126000,roundingError:0,verification:"Exchange product specification"},
      {id:"CME-BE",benchmark:"Brent",exchange:"NYMEX / CME Group",kind:"option",code:"BE",name:"Brent Crude options",size:1000,settlement:"Financial",url:"https://www.cmegroup.com/",contracts:54,coveredBarrels:54000,roundingError:0,verification:"Exchange product specification"},
    ] } });
    const body = route.request().postDataJSON() as { action:string };
    if (body.action === "forecast") return route.fulfill({ json: { mode:"verified-live",method:"test",asOf:"2026-08-20",latestPrice:100,history:[{Date:"2026-08-20",Actual:100}],forecast:[{Date:"2026-09-20",PointForecast:100,Lower50:95,Upper50:105,Lower80:90,Upper80:110,Lower95:80,Upper95:120}],metrics:{},components:[] } });
    if (body.action === "risk") return route.fulfill({ json: { mode:"verified-live",method:"test",latestDate:"2026-08-20",riskScore:60,alertThreshold:80,alert:false,history:[{date:"2026-08-20",score:60}] } });
    return route.fulfill({ json: { mode:"verified-live",method:"test",asOf:"2026-08-20",observations:200,estimationWindow:{start:"2018-01-01",end:"2019-12-31"},eventWindow:{start:"2020-01-01",end:"2026-08-20"},rSquared:.5,drivers:[{id:"FRED-DGS10",nameZh:"美国10年期国债收益率",nameEn:"US 10-Year Treasury Yield",impact:.2,coefficient:.1}],granger:[],scaleGranger:[],selectedScales:[],components:[{imf:"IMF1",channelZh:"短周期",channelEn:"Short cycle",centerFrequency:.2,volatilityShare:100,points:[{date:"2026-08-20",value:100}]}],hht:[],scaleEffect:{selectedScale:"IMF1",minimumDate:"2026-01-01",minimumValue:80,maximumDate:"2026-08-20",maximumValue:100,tradingDayInterval:20,calendarDayInterval:30,netEffect:20,originalResponse:20,shareInOriginalResponse:100},fevd:[],fevdOwnShare:100,fevdHorizon:20,varLag:1,rolling:[],rollingFevd:[],breakTest:{fixed:{breakDate:"2020-01-01",fStatistic:1,pValue:.1,preSlope:0,postSlope:0,slopeChange:0,levelShift:0,significant:false},optimal:{candidateCount:1,bestDate:"2020-01-01",rssImprovementPercent:1,profile:[]}},sources:[] } });
  });
  await page.goto("http://localhost:4174/decision");
  await expect(page.getByRole("heading", { name: "采购成本预警测算" })).toBeVisible();
  await expect(page.getByText("口径已校正")).toBeVisible();
  await expect(page.getByText(/相对未套保节省|保险与机会成本/)).toBeVisible();
  await expect(page.locator(".portfolio-grid>.portfolio-card")).toHaveCount(6);
  await page.locator(".portfolio-card summary").first().click();
  await expect(page.locator(".portfolio-card").first().getByText(/BUY \/ LONG|买入/).first()).toBeVisible();
  await expect(page.locator(".portfolio-card").first().getByText(/Initial margin|初始保证金/).first()).toBeVisible();
  await expect(page.locator(".product-grid")).toHaveCount(0);
  await page.getByRole("button", { name: /展开/ }).click();
  await expect(page.getByText("美国10年期国债收益率").first()).toBeVisible();
});

test("data center is independent and searches GPRD plus financial products", async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    const url=new URL(route.request().url());
    if(url.pathname.endsWith("/health"))return route.fulfill({json:{ok:true}});
    if(url.pathname.endsWith("/catalog"))return route.fulfill({json:{items:[{id:"GPRD",name:"地缘政治风险指数（传统日度 GPR）",nameEn:"Geopolitical Risk Index (traditional daily GPR)",category:"地缘政治与事件风险",source:"Caldara-Iacoviello GPR",unit:"指数",frequency:"日度",updated:"2026-08-17",color:"#c47d59"},{id:"FRED-DGS10",name:"美国10年期国债收益率",nameEn:"US 10-Year Treasury Yield",category:"金融条件",source:"FRED",unit:"%",frequency:"Daily",updated:"2026-08-20",color:"#587a9a"}]}});
    if(url.pathname.endsWith("/gprd"))return route.fulfill({json:{updated:"2026-08-17",points:[{date:"2026-08-16",value:120.123},{date:"2026-08-17",value:144.473}]}});
    if(url.pathname.endsWith("/instruments"))return route.fulfill({json:{asOf:"2026-08-24",benchmark:"All",quoteMethod:"AKShare / Sina",broker:{connected:false,name:"IBKR",message:"not connected"},executionEnabled:false,disclaimer:"indicative",products:[{id:"CME-CL",benchmark:"WTI",exchange:"NYMEX / CME Group",kind:"future",code:"CL",name:"WTI Crude Oil futures",nameZh:"WTI 原油期货",size:1000,settlement:"Physical",url:"https://www.cmegroup.com/",contracts:1,coveredBarrels:1000,roundingError:0,verification:"official",quote:{last:85.2,bid:85.19,ask:85.21,time:"12:00:00",date:"2026-08-24",name:"纽约原油",provider:"Sina"}}]}});
    return route.fulfill({json:{}});
  });
  await page.goto("http://localhost:4174/data");
  await expect(page.getByRole("heading",{name:"变量因素查询"})).toBeVisible();
  await page.getByPlaceholder(/Brent/).fill("GPRD");
  await expect(page.getByText("地缘政治风险指数（传统日度 GPR）")).toBeVisible();
  await page.getByRole("tab",{name:"金融产品查询"}).click();
  await expect(page.getByText("WTI 原油期货")).toBeVisible();
  await expect(page.getByText("85.200 USD")).toBeVisible();
});
