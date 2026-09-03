import { useMemo, useRef, useState } from "react";
import { Cpu, Square, Sparkles } from "lucide-react";
import type { WebWorkerMLCEngine } from "@mlc-ai/web-llm";
import { buildExplanationPrompt, detectLocalAiCapability, type ExplanationPacket } from "../ai/localExplanation";

type LocalAiExplanationProps = {
  lang: "zh" | "en";
  packet: ExplanationPacket;
};

export function LocalAiExplanation({ lang, packet }: LocalAiExplanationProps) {
  const capability = useMemo(() => detectLocalAiCapability(), []);
  const engineRef = useRef<WebWorkerMLCEngine | null>(null);
  const workerRef = useRef<Worker | null>(null);
  const [progress, setProgress] = useState("");
  const [answer, setAnswer] = useState("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  async function explain() {
    if (!capability.modelId || running) return;
    setRunning(true);
    setError("");
    setAnswer("");
    try {
      if (!engineRef.current) {
        setProgress(lang === "zh" ? "首次使用：正在下载并缓存本地模型…" : "First use: downloading and caching the local model…");
        const { CreateWebWorkerMLCEngine } = await import("@mlc-ai/web-llm");
        const worker = new Worker(new URL("../ai/ai.worker.ts", import.meta.url), { type: "module" });
        workerRef.current = worker;
        engineRef.current = await CreateWebWorkerMLCEngine(worker, capability.modelId, {
          initProgressCallback: (report) => setProgress(`${report.text} ${Number(report.progress * 100).toFixed(1)}%`),
        });
      }
      setProgress(lang === "zh" ? "正在依据当前真实结果生成解释…" : "Explaining the current verified result…");
      const stream = await engineRef.current.chat.completions.create({
        messages: [
          { role: "system", content: lang === "zh" ? "你是严谨的量化研究解释助手。" : "You are a rigorous quantitative research explainer." },
          { role: "user", content: buildExplanationPrompt(packet, lang) },
        ],
        temperature: 0.2,
        stream: true,
      });
      let output = "";
      for await (const chunk of stream) {
        output += chunk.choices[0]?.delta.content || "";
        setAnswer(output);
      }
      setProgress("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setRunning(false);
    }
  }

  function stop() {
    workerRef.current?.terminate();
    workerRef.current = null;
    engineRef.current = null;
    setRunning(false);
    setProgress("");
  }

  return <section className="local-ai-panel">
    <div className="local-ai-heading"><Cpu/><div><b>{lang === "zh" ? "浏览器本地 AI 解释" : "Browser-local AI explanation"}</b><p>{lang === "zh" ? "结果不会上传给第三方模型服务；首次使用才下载模型。" : "Results stay in your browser; the model downloads only after you opt in."}</p></div></div>
    {capability.level === "unsupported" ? <p className="local-ai-unavailable">{lang === "zh" ? "当前设备缺少 WebGPU 或可用内存不足，已禁用本地模型以避免页面卡死。" : "This device lacks WebGPU or enough memory, so local AI is disabled to prevent a stalled page."}</p> : <div className="local-ai-actions">
      <button onClick={()=>void explain()} disabled={running}><Sparkles/>{lang === "zh" ? `使用 ${capability.modelId} 解释` : `Explain with ${capability.modelId}`}</button>
      {running && <button className="secondary" onClick={stop}><Square/>{lang === "zh" ? "停止" : "Stop"}</button>}
    </div>}
    {progress && <p className="local-ai-progress">{progress}</p>}
    {error && <p className="local-ai-error">{error}</p>}
    {answer && <div className="local-ai-answer">{answer}</div>}
  </section>;
}
