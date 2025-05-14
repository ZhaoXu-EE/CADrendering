import os
import glob
from tqdm import tqdm

def analyze_step_files(base_dir='small_step_files'):
    """
    统计step文件夹中的文件数量和分布情况
    
    Args:
        base_dir (str): 包含子文件夹的基础目录，默认为'step'
    """
    if not os.path.exists(base_dir):
        print(f"错误: 目录 '{base_dir}' 不存在")
        return
    
    # 统计变量
    total_folders = 0
    empty_folders = 0
    total_step_files = 0
    folders_with_files = {}  # 记录每个文件夹中的文件数量
    
    # 遍历所有可能的文件夹
    print("正在统计文件信息...")
    for i in tqdm(range(1000), desc="扫描文件夹"):
        folder_name = f"{i:08d}"
        folder_path = os.path.join(base_dir, folder_name)
        
        if os.path.exists(folder_path):
            total_folders += 1
            step_files = glob.glob(os.path.join(folder_path, "*.step"))
            file_count = len(step_files)
            total_step_files += file_count
            
            if file_count == 0:
                empty_folders += 1
            else:
                folders_with_files[folder_name] = file_count
    
    # 打印统计结果
    print("\n=== 统计结果 ===")
    print(f"文件夹总数: {total_folders}")
    print(f"空文件夹数: {empty_folders}")
    print(f"包含文件的文件夹数: {total_folders - empty_folders}")
    print(f"STEP文件总数: {total_step_files}")
    
    if total_folders > 0:
        print(f"平均每个文件夹的文件数: {total_step_files/total_folders:.2f}")
    
    # 打印包含文件的文件夹详情
    if folders_with_files:
        print("\n包含文件的文件夹详情:")
        for folder, count in sorted(folders_with_files.items())[:10]:  # 只显示前10个
            print(f"文件夹 {folder}: {count} 个文件")
        
        if len(folders_with_files) > 10:
            print(f"... 还有 {len(folders_with_files) - 10} 个文件夹含有文件")
    
    # 检查是否存在异常情况（每个文件夹应该最多只有1个step文件）
    abnormal_folders = {k: v for k, v in folders_with_files.items() if v > 1}
    if abnormal_folders:
        print("\n警告：以下文件夹包含多个STEP文件：")
        for folder, count in abnormal_folders.items():
            print(f"文件夹 {folder}: {count} 个文件")

if __name__ == "__main__":
    analyze_step_files()