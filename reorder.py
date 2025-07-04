#!/usr/bin/env python3
"""
STEP 实体重排与重新编号工具
=============================

功能简介
--------
本工具用于预处理 STEP 文件的实体定义，特别适用于 LLM 数据生成任务，具备以下功能：

1. **消除 forward reference**：确保每个实体在首次被引用前已被定义。
2. **相似实体聚类**：在满足依赖拓扑的前提下，尽量将相同类型实体聚集在一起（可选）。
3. **重新编号实体 ID**：将 `#` 开头的实体编号统一重新映射为从 `#1` 开始的连续递增序列。

支持处理单个文件或整个目录中的多个 `.step` / `.stp` 文件，支持保持子目录结构。

使用示例
--------
1. **就地处理单个文件**：

    python reorder.py --in-place model.step

2. **输出至指定文件**：

    python reorder.py model.step out.step

3. **关闭类型聚类，仅进行拓扑排序与编号**：

    python reorder.py model.step out.step --group none

4. **仅消除 forward reference，不重新编号**：

    python reorder.py model.step out.step --no-renum

5. **批量处理目录中所有 STEP 文件，输出至目标目录**：

    python reorder.py input_dir/ --out-dir output_dir/

命令行参数说明
---------------
- `--in-place`：直接覆盖原始文件。
- `--group {type, strict, none}`：控制类型聚类方式：
    - `type`：尽量聚类相同类型；
    - `strict`（默认）：同类实体尽量连续出现；
    - `none`：不聚类，仅保证拓扑无环。
- `--no-renum`：不修改实体编号，仅排序。
- `--out-dir DIR`：输出至指定目录（保留子目录结构）。
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
    id2ent, deps, rev, indeg, typ, order = {}, defaultdict(set), defaultdict(set), {}, {}, {}
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
            deps[eid].add(rid)  # eid 依赖 rid
            rev[rid].add(eid)  # 反向：rid 被 eid 依赖
    # 新：统计“仍有多少依赖尚未满足”
    for n, S in deps.items():
        indeg[n] = len(S)
    for k in id2ent:
        indeg.setdefault(k, 0)
    # 计算每个实体的深度（最长依赖链长度）
    # 深度定义为从叶子节点到当前节点的最长路径长度
    depth, memo = {}, {}
    def get_depth(n):
        if n in memo:
            return memo[n]
        if not deps[n]:                # 叶子
            memo[n] = 0
        else:
            memo[n] = 1 + max(get_depth(c) for c in deps[n])
        return memo[n]
    for k in id2ent:
        depth[k] = get_depth(k)

    return id2ent, rev, indeg, typ, order, depth

# ---------- Kahn（按“依赖深度 → 是否同类 → 原行号”优先） ----------
def topo_grouped(id2ent, rev, indeg, order, depth, typ, group_mode='type'):
    """
    • 依赖全部满足 (indeg == 0) 的节点进入优先队列。
    • 队列键 = (depth, order)：
        - depth  = 由 build_graph 预计算的最长依赖链长度
        - order  = 原文件行号，保证同层保持原相对顺序
    这样即可自动把叶子节点（CARTESIAN_POINT, DIRECTION…）排在最前，
    无需维护手工类型优先级表。
    """
    # --------- 准备容器 ---------
    if group_mode == 'strict':
        # {type: [(depth, order, id), ...]}
        ready_by_type = defaultdict(list)
        def push(n):
            heapq.heappush(ready_by_type[typ[n]], (depth[n], order[n], n))
    else:   # type / none → 继续用单一堆
        ready = []
        cur_ty = None
        def push(n):
            same = 0 if (group_mode != 'none' and cur_ty == typ[n]) else 1
            heapq.heappush(ready, (depth[n], same, order[n], n))

    for n in id2ent:
        if indeg[n] == 0:
            push(n)

    out = []
    if group_mode == 'strict':
        cur_ty = None
        while ready_by_type:
            # 尽量延续当前类型
            if cur_ty and ready_by_type.get(cur_ty):
                q = ready_by_type[cur_ty]
            else:
                # 选一个“最靠前”的新类型
                cur_ty = min(ready_by_type,
                             key=lambda k: ready_by_type[k][0][:2])  # depth→order
                q = ready_by_type[cur_ty]
            _, _, n = heapq.heappop(q)
            # 1) 把当前节点加入输出序列
            out.append(n)
            # 2) 释放其后继节点
            for m in rev[n]:
                indeg[m] -= 1
                if indeg[m] == 0:
                    push(m)
            if not q:
                ready_by_type.pop(cur_ty, None)
    else:   # 原来的 soft / none
        while ready:
            _, _, _, n = heapq.heappop(ready)
            cur_ty = typ[n]
            # 1) 输出当前节点
            out.append(n)
            # 2) 释放其后继节点
            for m in rev[n]:
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
    id2ent, rev, indeg, typ, order, depth = build_graph(ents)
    sorted_ents = topo_grouped(id2ent, rev, indeg, order, depth, typ, group_mode)
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
    ap.add_argument("--group", choices=["type","strict","none"], default="strict",
                help=("type   = soft cluster by entity type; "
                      "strict = contiguous cluster when possible (default); "
                      "none   = pure topo sort"))
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

        try:
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

            process_file(f, dst, args.group, not args.no_renum)

        except Exception as e:
            print(f"\n[SKIP] Failed to process file: {f}")
            print(f"Error reason: {e}")

if __name__ == "__main__":
    main()
