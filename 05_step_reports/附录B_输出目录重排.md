# 附录 B · 输出目录重排（`04_reports/` 编号式板块）

> 本篇记录一次**仓库卫生**动作：把交付物本体 `04_reports/` 的板块目录改成**编号式**，
> 并把散落各处的引用一次性同步干净。它不是流水线的第 13 步，而是**贯穿全流程的收尾整理**，
> 因此以「附录」而非「步骤」形式留档。

## 这一步要什么

1. 用户明确要求：**「梳理全部输出内容，合理分类，各自独立文件夹」**。
2. 一个真实存在的读错风险：`04_reports/` 的板块名与 `01_models/` 的**模型板块目录同名**——
   两边都有 `separation`，`04_reports` 还叫 `denoiser`（而模型板叫 `denoising`）。
   于是同一个词 `separation` 在仓库里代表**四种东西**：
   报告板块 / 模型板 / 第三方仓库名 / 权重子目录。人读容易错，脚本改更容易错。

## 做了什么

### 1. 板块改为编号式（`git mv` 保留历史）

| 旧板块名 | 新板块名 | 归属 |
|---|---|---|
| `_shared/` | `00_shared/` | 跨板块共用 |
| `separation/` | `01_separation/` | 板 1 · 分离 |
| `denoiser/` | `02_denoising/` | 板 2 · 降噪 |
| `cascade/` | `03_cascade/` | 级联 |
| `slides/` | `04_defense/` | 答辩材料 |

编号前缀同时让**排序**符合阅读顺序；`tools/paths.py` 五个常量（`SHARED` / `SEPARATION` /
`DENOISER` / `CASCADE` / `SLIDES`）是唯一入口，已同步。

### 2. 五种引用形态、五支补丁（全部字节级读写）

板块改名很简单，**难的是把全仓引用改干净**。仓库里同一个路径有**五种写法**，逐层浮出水面：

| # | 引用形态 | 例子 | 补丁 | 替换量 |
|:--|:--|:--|:--|:--|
| 1 | 字面量 | `04_reports/denoiser/html/…` | `_patch_reorg_reports.py` | 78 文件 / 424 处 |
| 2 | **REPORTS 相对串**（最隐蔽） | `"_shared/figures/paper/…"` | `_patch_reorg_relpath.py` | 5 文件 / 162 处 |
| 3 | `_scratch` 脚手架内部 | 同上但位于 `tools/_scratch/` | `_patch_reorg_scratch.py` | 44 文件 / 148 处 |
| 4 | 裸相对路径 + `"04_reports" / "<old>"` | `` `separation/docs/…` `` | `_patch_reorg_docs.py` | 47 文件 / 276 处 |
| 5 | `os.path.join(...)` / `变量 / "路径"` | `os.path.join(ROOT,"04_reports","separation")`、`R / "_shared"` | `_patch_reorg_join.py` | 22 文件 / 82 处 |

合计 **1092 处**替换。

**安全护栏**（这轮最大的坑）：`separation` / `denoiser` 这些词，**在别处是活路径**，绝不能顺手改——
`01_models/separation/`（模型板）、`01_models/_third_party/**`（第三方仓库内部相对链接）、
`_weights/denoiser/*.th`（权重）、`facebookresearch/denoiser/enhance.py`。
补丁 4/5 用**负向后顾** `(?<![\w/\\.])` 拒绝「前面是词字符 / `/` / `.`」的匹配，把这类全部挡掉。

`README.md` 的目录树是**唯一需要按位置切分**的地方：`01_models\` 树在前、`04_reports\` 树在后，
两棵树排版**一模一样**（都是 `│   ├── separation\`），正则无法区分 → 按标记行 `├── 04_reports\`
切分，只对后半段生效（实证：第 38 行 `separation\` 保持原样）。

### 3. 自动产物「改生成器、不手改」

5 个生成器仍写旧路径 → 改生成器源码后**重生成**（手改产物会让 `--verify` 立刻失败）：
`_build_summaries.py`（4 份摘要）、`_build_paper_scope.py`（口径章节）、`_build_slides.py`（24 页 slides）、
`_build_dashboards.py` + `_build_dashboards_t72.py`（3 块看板）。全部改用 **venv 解释器**（`fyp_audio`）。

另有 3 处「松散列表」形态（`separation / denoiser / cascade / _shared`，**无尾斜杠**，正则看不见）
手改：`tools/paths.py` 目录说明、`05_step_reports/00_总览.md` 目录地图、`RESTRUCTURE_2026-09-23.md`。

### 4. 重写 `04_reports/README.md`

原索引只描述重排前的板块名、且篇「空，待阶段产出」的旧内容（早已有产出）。重写为**真实内容索引**
（逐板块列出 `docs / figures / data / html` 实际文件），并加一张**旧名 → 新名映射表**。

## 产出

- `04_reports/` 顶层 = `00_shared / 01_separation / 02_denoising / 03_cascade / 04_defense / README.md`
- `04_reports/README.md`（重写：映射表 + 逐板块真实内容）
- 5 个自动产物在新目录下**重生成**
- 4 支重排补丁脚本 + 1 支 doc 补丁 + 1 支 join 补丁（见 `tools/_scratch/_patch_reorg_*.py`）
- 计划书 §9.14

## 关键数字

| 检查 | 结果 |
|:--|:--|
| 板块重命名 | 5 个（`git mv`，历史保留） |
| 引用替换 | **1092 处**（424 + 162 + 148 + 276 + 82） |
| `reproduce.py --check` | **PASS 77 / FAIL 0** |
| `_check_reproduce.py`（独立核对，不 import 生成器） | **PASS 12 / FAIL 0** |
| `--readme --verify` | 逐字节一致（**19199 字符**） |
| `_build_summaries.py / _build_paper_scope.py --verify` | 逐字节一致 |
| 残留扫描（全形态） | **可修引用 0 处** |

## 结论与坑

1. **一个路径不止一种写法。** 只改「字面量」会漏掉 `REPORTS / "name"`、`os.path.join(…,"name")`、
   变量除法、REPORTS 相对串——**每漏一种，就留一个 `FileNotFoundError` 给未来的自己**。
   判定标准永远是「跑一遍复现链」，不是「看起来改完了」。
2. **同名不同物是最大的坑。** `separation` 在 `01_models/` 下是**必须保留**的模型板；
   在 `04_reports/` 下是**必须改**的报告板块。任何「全局替换」都会烧掉一边。
3. **自动产物只能靠改生成器。** 手改产物 = 制造 `--verify` 的必然失败。
4. **历史快照要留着。** `_hash_*.json` / `_repro_backup/` / `_pre_snapshot/` /
   `_archive_model_cards_2026-09-23/` / `FYP_PLAN_FULL_2026-09-23.html` 里的旧路径是**当时状态的证据**，
   改掉等于篡改记录 → 全部保留，并在 §9.14 里**照报**。
5. **`E:\` 清理只清「我造的」临时产物**（`_fresh2` / `_fresh_lf` / `_fresh_repro` / `E:\c\` / `E:\2026_sem_1`）；
   用户的其它目录（`GameJam` / `Intern` / `jerry` / `FYP_HKBU_evicted` / `tmp`）**一律不动**。
   ⚠️ 回收站的 6.9 G 空间**未清**（本机删除进回收站、空间不即时归还），待你决定。
6. **照报**：`_build_slides.py --verify` 因页脚内嵌 `datetime.now()`（分钟级）跨分钟必失败——
   这是 slides 的**既有**非确定性，本次未引入；要让 slides 逐字节可复现需改时间戳来源（会改变已交付内容）→ 留待拍板。

## 到哪看细节

- 逐条记录与表 → [`../04_reports/00_shared/docs/FYP_PLAN_2026-09-22.md`](../04_reports/00_shared/docs/FYP_PLAN_2026-09-22.md) §9.14
- 板块索引与映射 → [`../04_reports/README.md`](../04_reports/README.md)
- 路径唯一入口 → [`../tools/paths.py`](../tools/paths.py)
- 重排补丁 → `../tools/_scratch/_patch_reorg_*.py`
- 复现自检 → `python tools/reproduce.py --check`
