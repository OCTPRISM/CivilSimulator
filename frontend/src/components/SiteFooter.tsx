import Link from "next/link";

export default function SiteFooter() {
  return (
    <footer className="mt-16 pt-8 border-t border-stone-800/80">
      <div className="grid sm:grid-cols-3 gap-8 text-[12px]">
        <div>
          <div className="font-serif text-sm tracking-wider mb-2 opacity-80">平台</div>
          <ul className="space-y-1.5 opacity-55">
            <li><Link href="/labs" className="hover:opacity-100 transition">实验平台</Link></li>
            <li><Link href="/simulator" className="hover:opacity-100 transition">文明模拟器</Link></li>
            <li><Link href="/worlds" className="hover:opacity-100 transition">我的世界</Link></li>
            <li><Link href="/generator" className="hover:opacity-100 transition">3D 模型生成器</Link></li>
          </ul>
        </div>
        <div>
          <div className="font-serif text-sm tracking-wider mb-2 opacity-80">文档</div>
          <ul className="space-y-1.5 opacity-55">
            <li><Link href="/docs" className="hover:opacity-100 transition">技术文档</Link></li>
            <li>
              <a href="https://github.com/Tencent-Hunyuan/Hunyuan3D-2" target="_blank" rel="noreferrer"
                 className="hover:opacity-100 transition">
                Hunyuan3D 集成说明
              </a>
            </li>
          </ul>
        </div>
        <div>
          <div className="font-serif text-sm tracking-wider mb-2 opacity-80">联系我们</div>
          <ul className="space-y-1.5 opacity-55">
            <li><Link href="/contact" className="hover:opacity-100 transition">反馈与商务</Link></li>
            <li><a href="mailto:hello@civsim.local" className="hover:opacity-100 transition">hello@civsim.local</a></li>
          </ul>
        </div>
      </div>
      <p className="text-[10px] opacity-30 text-center mt-10 tracking-widest">
        © {new Date().getFullYear()} Civilization Simulator
      </p>
    </footer>
  );
}
