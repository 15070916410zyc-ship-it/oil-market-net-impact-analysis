import type { PriceRow } from "../data";
import { buildForecastOption, buildHorizontalBarOption, buildTimeSeriesOption } from "../lib/chartOptions";
import { EChartView } from "./EChartView";

type Lang = "zh" | "en";
const tx = (lang: Lang, zh: string, en: string) => lang === "zh" ? zh : en;

type Driver = { nameZh: string; nameEn: string; impact: number };
type Granger = { nameZh: string; nameEn: string; pValue: number; significant: boolean };

export function DriverChart({ lang, data }: { lang: Lang; data: Driver[] }) {
  return <EChartView height={430} ariaLabel={tx(lang,"可缩放的因素净影响图","Zoomable factor net-impact chart")} option={buildHorizontalBarOption({
    rows:data.map((driver)=>({name:lang === "en" ? driver.nameEn : driver.nameZh,value:driver.impact,color:driver.impact >= 0 ? "#587a9a" : "#c47d59"})),
    xName:tx(lang,"美元/桶","USD/bbl"),
  })}/>;
}

export function ForecastChart({ data, lang }: { data: PriceRow[]; lang: Lang }) {
  return <EChartView className="forecast-echart" height={520} ariaLabel={tx(lang,"可缩放的真实油价与概率预测区间图","Zoomable observed oil-price and probabilistic forecast chart")} option={buildForecastOption(data.map((row)=>({
    date:row.date,actual:row.actual,median:row.forecast,low50:row.lo50,high50:row.hi50,low80:row.lo80,high80:row.hi80,low95:row.lo95,high95:row.hi95,
  })),lang)}/>;
}

export function RiskChart({ lang, data, threshold }: { lang: Lang; data: Array<{ date:string; score:number }>; threshold:number }) {
  return <EChartView height={340} ariaLabel={tx(lang,"可缩放的历史风险分位图","Zoomable historical risk-percentile chart")} option={buildTimeSeriesOption({rows:data,series:[{key:"score",name:tx(lang,"历史风险分位","Historical risk percentile"),color:"#7771a7",area:true}],yMin:0,yMax:100,threshold:{value:threshold,name:tx(lang,"复核阈值","Review threshold")}})}/>;
}

export function ScaleComponentsChart({ lang, components }: { lang:Lang; components:Array<{ imf:string; points:Array<{date:string;value:number}> }> }) {
  const dates=components[0]?.points.map((point)=>point.date)||[];
  const rows=dates.map((date,index)=>Object.fromEntries([["date",date],...components.map((component)=>[component.imf,component.points[index]?.value])])) as Array<{date:string;[key:string]:string|number|undefined}>;
  return <EChartView height={340} ariaLabel={tx(lang,"可缩放的VMD分量图","Zoomable VMD component chart")} option={buildTimeSeriesOption({rows,series:components.map((component,index)=>({key:component.imf,name:component.imf,color:["#c47d59","#587a9a","#756fa5","#4f8b7d","#b49958","#8b6e78","#527f91","#9a7454"][index]}))})}/>;
}

export function GrangerChart({ lang, data, alpha }: { lang:Lang; data:Granger[]; alpha:number }) {
  return <EChartView height={430} ariaLabel={tx(lang,"可缩放的格兰杰显著性图","Zoomable Granger significance chart")} option={buildHorizontalBarOption({rows:data.map((row)=>({name:lang === "zh" ? row.nameZh : row.nameEn,value:-Math.log10(Math.max(row.pValue,1e-12)),color:row.significant?"#587a9a":"#c7c1bc"})),xName:"−log10(p)",threshold:{value:-Math.log10(alpha),name:`α=${alpha}`}})}/>;
}

export function RollingImpactChart({ lang, data }: { lang:Lang; data:Array<{date:string;observed:number;fitted:number}> }) {
  return <EChartView height={390} ariaLabel={tx(lang,"可缩放的滚动净影响结果","Zoomable rolling net-impact result")} option={buildTimeSeriesOption({rows:data,series:[{key:"observed",name:tx(lang,"实际变动","Observed change"),color:"#30343d"},{key:"fitted",name:tx(lang,"模型拟合","Model fit"),color:"#6f69a2"}]})}/>;
}

export function FevdChart({ lang, data }: { lang:Lang; data:Array<{nameZh:string;nameEn:string;share:number}> }) {
  return <EChartView height={430} ariaLabel={tx(lang,"可缩放的FEVD贡献图","Zoomable FEVD contribution chart")} option={buildHorizontalBarOption({rows:data.map((row)=>({name:lang === "zh" ? row.nameZh : row.nameEn,value:row.share,color:"#c47d59"})),xName:"%"})}/>;
}

export function RollingFevdChart({ lang, data }: { lang:Lang; data:Array<{date:string;externalShare:number;ownShare:number}> }) {
  return <EChartView height={390} ariaLabel={tx(lang,"可缩放的滚动FEVD图","Zoomable rolling FEVD chart")} option={buildTimeSeriesOption({rows:data,series:[{key:"externalShare",name:tx(lang,"外部因素冲击","External-factor shocks"),color:"#c47d59",area:true,stack:"share"},{key:"ownShare",name:tx(lang,"油价自身冲击","Oil-price own shocks"),color:"#6f69a2",area:true,stack:"share"}],yMin:0,yMax:100,yName:"%"})}/>;
}

export function HhtChart({ lang, data }: { lang:Lang; data:Array<{date:string;frequency:number}> }) {
  return <EChartView height={390} ariaLabel={tx(lang,"可缩放的HHT瞬时频率图","Zoomable HHT instantaneous-frequency chart")} option={buildTimeSeriesOption({rows:data,series:[{key:"frequency",name:tx(lang,"HHT瞬时频率","HHT instantaneous frequency"),color:"#9b6d51"}],yMin:0})}/>;
}

export function BreakChart({ lang, data }: { lang:Lang; data:Array<{date:string;improvementPercent:number}> }) {
  return <EChartView height={390} ariaLabel={tx(lang,"可缩放的结构断点诊断图","Zoomable structural-break diagnostic chart")} option={buildTimeSeriesOption({rows:data,series:[{key:"improvementPercent",name:tx(lang,"分段拟合改善","Segmented-fit improvement"),color:"#587a9a"}],yName:"%"})}/>;
}
