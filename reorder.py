#!/usr/bin/env python3
"""
功能
----

1. **消除 forward reference**：保证任何被引用的实体在首次被引用前已定义。
2. **相似实体聚类**：在满足拓扑约束的前提下，尽量把“相似”实体（默认=类型相同）排在一起。
3. **连续重新编号**：将 DATA 区所有实体的 `#` 编号重新映射为从 **#1** 开始的连续递增序列，
   并同步更新实体间的引用关系。

用法
----

基本命令格式：

    python reorder.py [输入文件/文件夹] [输出文件/文件夹] [选项]

示例：

1. **就地处理 STEP 文件**（推荐方式）  
   消除 forward reference，按类型聚类，重新编号实体：

    python reorder.py --in-place part.step

2. **输出到指定文件**  
   和上面相同功能，但将结果写入新文件 `out.step`：

    python reorder.py part.step out.step

3. **关闭聚类，仅保留拓扑排序和编号**  
   不按实体类型聚类，仅按依赖关系拓扑排序并重新编号：

    python reorder.py part.step out.step --group none

4. **保持原始 ID，不进行重新编号**  
   仍会消除 forward reference，但保留原始的 `#ID` 编号（不推荐用于 LLM 训练）：

    python reorder.py part.step out.step --no-renum

5. **批量处理文件夹中的所有 STEP 文件**  
   将 `models/` 文件夹中所有 `.step` / `.stp` 文件处理后写入 `out_dir/`，保留原有子目录结构：

    python reorder.py models/ --out-dir out_dir/

可选参数说明：
- `--in-place`：就地修改输入文件，不指定时默认写入新的文件。
- `--group {type, none}`：控制是否聚类相同类型的实体（默认：type）。
- `--no-renum`：不重新编号 `#ID`，保留原始编号。
- `--out-dir DIR`：指定输出根目录，用于批量处理多个文件。
"""

import argparse, pathlib, re, sys, heapq, itertools
from typing import Optional
from collections import defaultdict, Counter
from tqdm import tqdm

ID_RE   = re.compile(r'#(\d+)\b')
TYPE_RE = re.compile(r'=\s*([A-Z0-9_]+)\s*[\(\s]')   # STEP 关键字

# ---------- 拆段 ----------
def split_sections(lines):
    header, data, footer, state = [], [], [], 'header'
    for ln in lines:
        if state == 'header':
            header.append(ln)
            if ln.strip().upper() == 'DATA;':
                state = 'data'
        elif state == 'data':
            if ln.strip().upper() == 'ENDSEC;':
                footer.append(ln)
                state = 'footer'
            else:
                data.append(ln)
        else:
            footer.append(ln)
    if state != 'footer':
        raise ValueError("STEP file missing ENDSEC; for DATA section")
    return header, data, footer

def collect_entities(data_lines):
    blocks, cur = [], []
    for ln in data_lines:
        cur.append(ln)
        if ';' in ln:
            blocks.append(''.join(cur))
            cur.clear()
    if cur:
        raise ValueError("Unterminated entity before ENDSEC;")
    return blocks

# ---------- 依赖图 ----------
def entity_type(block: str) -> str:
    m = TYPE_RE.search(block)
    return m.group(1) if m else ''

def build_graph(entities):
    id2ent, deps, indeg, typ, order = {}, defaultdict(set), Counter(), {}, {}
    for idx, block in enumerate(entities):
        m = re.match(r'\s*#(\d+)\s*=', block)
        if not m:
            raise ValueError(f"Malformed entity header: {block[:60]}...")
        eid          = int(m.group(1))
        id2ent[eid]  = block
        order[eid]   = idx
        typ[eid]     = entity_type(block)
        for r in ID_RE.findall(block):
            rid = int(r)
            if rid == eid:
                continue
            deps[eid].add(rid)
    for v, S in deps.items():
        for u in S:
            indeg[u] += 1
    # ensure all nodes exist in indeg
    for k in id2ent:
        indeg.setdefault(k, 0)
    return id2ent, deps, indeg, typ, order

# ---------- Kahn（带“相似优先”） ----------
def topo_grouped(id2ent, deps, indeg, typ, order, group_mode):
    ready  = []
    out    = []
    cur_ty = None

    def push(node):
        same = 0 if (cur_ty and typ[node] == cur_ty and group_mode != 'none') else 1
        heapq.heappush(ready, (same, typ[node], order[node], node))

    for n in id2ent:
        if indeg[n] == 0:
            push(n)

    while ready:
        same, tname, _, n = heapq.heappop(ready)
        out.append(n)
        cur_ty = tname if group_mode != 'none' else None
        for m in deps[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                push(m)

    # 若存在环，按原始顺序追加
    remaining = [k for k, v in indeg.items() if v > 0]
    remaining.sort(key=order.get)
    return [id2ent[i] for i in out + remaining]

# ---------- 重新编号 ----------
def renumber_entities(blocks):
    """给已按依赖排序好的 blocks 重新编号并返回新文本列表"""
    # 构建 old -> new 映射
    old_to_new = {}
    for new_idx, blk in enumerate(blocks, 1):
        m = re.match(r'\s*#(\d+)\s*=', blk)
        old_to_new[int(m.group(1))] = new_idx

    def replace_ids(match):
        old_id = int(match.group(1))
        return f'#{old_to_new[old_id]}'

    new_blocks = []
    for blk in blocks:
        # 更新整段中的所有 #ID
        new_blk = ID_RE.sub(replace_ids, blk)
        new_blocks.append(new_blk)
    return new_blocks

# ---------- 主流程 ----------
def process_file(src: pathlib.Path,
                 dst: Optional[pathlib.Path],
                 group_mode: str,
                 renum: bool):
    lines           = src.read_text(errors='ignore').splitlines(keepends=True)
    head, data, foot= split_sections(lines)
    ents            = collect_entities(data)
    id2ent,deps,indeg,typ,order = build_graph(ents)
    sorted_ents     = topo_grouped(id2ent,deps,indeg,typ,order, group_mode)
    if renum:
        sorted_ents = renumber_entities(sorted_ents)
    out_lines       = head + sorted_ents + foot
    (dst or src).write_text(''.join(out_lines))

# ---------- CLI ----------
def main():
    ap = argparse.ArgumentParser(description="Re‑order & re‑number STEP entities.")
    ap.add_argument("input", help="input STEP file or directory")
    ap.add_argument("output", nargs="?",
                    help="output file/dir; omitted means <name>_sorted.stp")
    ap.add_argument("--in-place", action="store_true",
                    help="overwrite original file(s)")
    ap.add_argument("--group", choices=["type","none"], default="type",
                    help="type = cluster by entity type (default); none = pure topo sort")
    ap.add_argument("--no-renum", action="store_true",
                    help="keep original #IDs (forward refs are still removed)")
    ap.add_argument("--out-dir",
                    help="write all processed files to this directory, "
                         "preserving the relative sub-folder structure "
                         "(implies not --in-place)")

    args = ap.parse_args()
    root  = pathlib.Path(args.input)
    files = [root] if root.is_file() else list(root.rglob("*.st?p"))
    if not files:
        sys.exit("No STEP files found")

    root = root.resolve()            # 方便 later 的 relative_to
    for f in tqdm(files, desc="Processing files", unit="file"):
        dst = None

        # --out-dir 优先级最高
        if args.out_dir:
            out_root = pathlib.Path(args.out_dir).resolve()
            rel_path = f.resolve().relative_to(root)
            dst      = out_root / rel_path           # 保留子目录
            dst.parent.mkdir(parents=True, exist_ok=True)

        # 若给了 positional output 参数，但没用 --out-dir
        elif not args.in_place:
            if args.output:
                o = pathlib.Path(args.output)
                if o.is_dir() or len(files) > 1:
                    rel_path = f.resolve().relative_to(root)
                    dst      = o / rel_path
                    dst.parent.mkdir(parents=True, exist_ok=True)
                else:
                    dst = o
            else:
                dst = f.with_stem(f.stem + "_sorted")
                # dst = dst.with_stem(dst.stem + "_sorted")

        process_file(f, dst, args.group, not args.no_renum)

if __name__ == "__main__":
    main()
