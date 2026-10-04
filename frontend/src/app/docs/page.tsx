import Link from "next/link";
import SiteLogo from "@/components/SiteLogo";
import SiteFooter from "@/components/SiteFooter";

const DOCS = [
  { title: "Hunyuan3D 本地部署", desc: "见仓库 docs/hunyuan3d-setup.md — M 系列 Mac 模型选型与 API 启动" },
  { href: "https://github.com/Tencent-Hunyuan/Hunyuan3D-2", title: "Hunyuan3D-2 官方仓库", desc: "腾讯混元 3D 开源文档", external: true },
  { title: "六层架构", desc: "L1 基础模型 · L2 文明引擎 · L3 Agent 社会 · L4 叙事 · L5 UI · L6 持久化" },
  { title: "实验平台 API", desc: "POST /api/labs/{key}/open — 独立沙盘工作区" },
  { title: "3D 生成 API", desc: "POST /api/generator/model/text · GET /outfits · /map — 人物服饰套装与地图" },
];

export default function DocsPage() {
  return (
    <main className="min-h-screen px-4 sm:px-6 py-8">
      <div className="max-w-3xl mx-auto">
        <SiteLogo href="/" compact />
        <h1 className="font-serif text-3xl tracking-widest mt-6 mb-2">技术文档</h1>
        <p className="text-sm opacity-55 mb-10">CivilSimulator 平台架构与集成说明</p>
        <ul className="space-y-4">
          {DOCS.map((d) => (
            <li key={d.title} className="rounded-xl border border-stone-800 bg-stone-950/40 p-4">
              {"href" in d && d.href ? (
                d.external ? (
                  <a href={d.href} target="_blank" rel="noreferrer"
                     className="font-serif text-lg hover:text-cyan-200/90 transition">{d.title} ↗</a>
                ) : (
                  <Link href={d.href} className="font-serif text-lg hover:text-cyan-200/90 transition">
                    {d.title}
                  </Link>
                )
              ) : (
                <div className="font-serif text-lg">{d.title}</div>
              )}
              <p className="text-[12px] opacity-55 mt-1">{d.desc}</p>
            </li>
          ))}
        </ul>
        <p className="text-[11px] opacity-40 mt-8">
          完整 Markdown 文档见仓库 <code className="opacity-80">docs/</code> 目录。
        </p>
        <SiteFooter />
      </div>
    </main>
  );
}
