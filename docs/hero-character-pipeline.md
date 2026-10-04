# Hero 单角色打磨管线

> **当前标杆角色**：`wuxia_wanderer`（散修剑客）  
> **策略**：一次只打磨一个 Hero；batch GLB 对该角色**禁用**，直到质量门禁通过。

## 为什么改策略

批量 `generate_role_bodies.py` 产出的是 box/capsule 拼接体，无法满足 v1.4 Hero 近景可信度。  
`HumanoidFigure` 原先优先加载这些 GLB，反而盖掉了带 PBR 皮肤的 `ProceduralHumanoid`。

## 当前架构

| 路径 | 说明 |
|------|------|
| `frontend/src/components/hero/HeroWuxiaWanderer.tsx` | Hero 专线 R3F 渲染（劲装/披风/五官/背剑） |
| `frontend/src/lib/heroCharacter.ts` | 路由：`wuxia_wanderer` → Hero，其它角色仍走 GLB |
| `frontend/public/models/characters/hero/wuxia_wanderer/manifest.json` | 迭代版本、质量门禁、下一步 |
| `backend/scripts/hero_compiler/compile_wuxia_wanderer.py` | 每次打磨后 bump iteration |
| `/dev/hero` | 单角色验收台（旋转、换肤、展示模式） |

## 日常迭代流程（可持续半年）

1. 编辑 `HeroWuxiaWanderer.tsx`（或将来导入的 Blender GLB）
2. 打开 `/dev/hero` 目视验收
3. 运行 `python3 backend/scripts/hero_compiler/compile_wuxia_wanderer.py`
4. 在 `manifest.json` 的 `quality_gates` 中勾选已达标项
5. **全部门禁通过后**，才允许：
   - 烘焙 `hero/wuxia_wanderer/body.glb` + LOD
   - 将第二个角色加入 `HERO_PIPELINE_ROLES`

## 下一阶段（真正脱离几何体拼接）

1. MakeHuman/MPFB → Blender  sculpt → 导出 glTF（CC0 链）
2. `compile_wuxia_wanderer.py` 接入 mesh 校验（三角面数、骨骼、license）
3. 表情 morph + idle/walk in-place 动画
4. 第二个 Story NPC 复制同一管线

## 查看入口

```bash
cd frontend && npm run dev
# http://localhost:3000/dev/hero
# 创建页选「散修剑客」/ Play 内玩家若为该 preset 均走 Hero 专线
```
