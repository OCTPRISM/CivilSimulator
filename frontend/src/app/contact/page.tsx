import SiteLogo from "@/components/SiteLogo";
import SiteFooter from "@/components/SiteFooter";

export default function ContactPage() {
  return (
    <main className="min-h-screen px-4 sm:px-6 py-8">
      <div className="max-w-lg mx-auto">
        <SiteLogo href="/" compact />
        <h1 className="font-serif text-3xl tracking-widest mt-6 mb-2">联系我们</h1>
        <p className="text-sm opacity-55 mb-8">产品反馈、合作与技术支持</p>
        <div className="space-y-4 text-[13px] opacity-70 leading-relaxed">
          <p>
            <span className="opacity-50">邮箱 · </span>
            <a href="mailto:hello@civsim.local" className="hover:opacity-100">hello@civsim.local</a>
          </p>
          <p>
            <span className="opacity-50">反馈 · </span>
            实验平台、文明模拟器或 3D 生成器相关问题，请附上复现步骤与截图。
          </p>
          <p>
            <span className="opacity-50">商务 · </span>
            定制文明种子、私有化部署与 Hunyuan3D 算力集成。
          </p>
        </div>
        <SiteFooter />
      </div>
    </main>
  );
}
