import os
import glob
from tqdm import tqdm

def is_folder_empty(folder_path):
    """
    检查文件夹是否为空
    
    Args:
        folder_path (str): 文件夹路径
    
    Returns:
        bool: 如果文件夹为空返回True，否则返回False
    """
    return len(os.listdir(folder_path)) == 0

def delete_large_step_files(base_dir='0002_step_1000'):
    """
    遍历指定目录下的所有子文件夹中的.step文件，
    如果文件行数超过1000行则删除该文件，
    同时删除空文件夹
    
    Args:
        base_dir (str): 包含子文件夹的基础目录，默认为'step'
    """
    # 确保基础目录存在
    if not os.path.exists(base_dir):
        print(f"错误: 目录 '{base_dir}' 不存在")
        return
    
    # 处理的文件和文件夹计数
    total_files = 0
    deleted_files = 0
    deleted_folders = 0
    
    # 首先计算需要处理的文件总数
    all_folders = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
    print("正在统计文件数量...")
    for folder_name in all_folders:
        folder_path = os.path.join(base_dir, folder_name)
        if os.path.exists(folder_path):
            step_files = glob.glob(os.path.join(folder_path, "*.step"))
            total_files += len(step_files)
    
    print(f"找到 {total_files} 个.step文件")
    
    # 使用tqdm创建进度条
    with tqdm(total=total_files, desc="处理进度") as pbar:
        # 遍历从00000000到00000999的文件夹
        for folder_name in all_folders:
            folder_path = os.path.join(base_dir, folder_name)
            
            # 检查文件夹是否存在
            if not os.path.exists(folder_path):
                continue
            
            # 如果文件夹已经是空的，直接删除
            if is_folder_empty(folder_path):
                os.rmdir(folder_path)
                deleted_folders += 1
                tqdm.write(f"已删除空文件夹: {folder_path}")
                continue
            
            # 查找.step文件
            step_files = glob.glob(os.path.join(folder_path, "*.step"))
            has_large_file = False
            
            for step_file in step_files:
                try:
                    # 计算文件行数
                    with open(step_file, 'r', encoding='utf-8') as f:
                        line_count = sum(1 for _ in f)
                    
                    # 如果行数超过1000，删除文件
                    if line_count > 1000:
                        os.remove(step_file)
                        deleted_files += 1
                        has_large_file = True
                        tqdm.write(f"已删除: {step_file} (行数: {line_count})")
                
                except Exception as e:
                    tqdm.write(f"处理文件 {step_file} 时出错: {str(e)}")
                
                # 更新进度条
                pbar.update(1)
            
            # 如果文件夹中有大文件被删除或文件夹变空，检查并删除空文件夹
            if has_large_file or is_folder_empty(folder_path):
                if is_folder_empty(folder_path):
                    os.rmdir(folder_path)
                    deleted_folders += 1
                    tqdm.write(f"已删除空文件夹: {folder_path}")
    
    # 打印统计信息
    print(f"\n处理完成!")
    print(f"总共处理文件数: {total_files}")
    print(f"删除的文件数: {deleted_files}")
    print(f"删除的空文件夹数: {deleted_folders}")

if __name__ == "__main__":
    delete_large_step_files()