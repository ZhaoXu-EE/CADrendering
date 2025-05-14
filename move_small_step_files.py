import os
import glob
import shutil
from tqdm import tqdm

def move_small_step_files(source_dir='step', target_dir='small_step_files'):
    """
    将500行以内的.step文件移动到新文件夹中，
    保持原有的文件夹结构
    
    Args:
        source_dir (str): 源目录，默认为'step'
        target_dir (str): 目标目录，默认为'small_step_files'
    """
    # 确保源目录存在
    if not os.path.exists(source_dir):
        print(f"错误: 源目录 '{source_dir}' 不存在")
        return
    
    # 创建目标根目录
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        print(f"创建目标目录: {target_dir}")
    
    # 统计变量
    total_files = 0
    moved_files = 0
    
    # 首先计算需要处理的文件总数
    print("正在统计文件数量...")
    for i in range(1000):
        folder_name = f"{i:08d}"
        folder_path = os.path.join(source_dir, folder_name)
        if os.path.exists(folder_path):
            step_files = glob.glob(os.path.join(folder_path, "*.step"))
            total_files += len(step_files)
    
    print(f"找到 {total_files} 个.step文件")
    
    # 使用tqdm创建进度条
    with tqdm(total=total_files, desc="处理进度") as pbar:
        # 遍历从00000000到00000999的文件夹
        for i in range(1000):
            folder_name = f"{i:08d}"
            source_folder = os.path.join(source_dir, folder_name)
            target_folder = os.path.join(target_dir, folder_name)
            
            # 检查源文件夹是否存在
            if not os.path.exists(source_folder):
                continue
            
            # 查找.step文件
            step_files = glob.glob(os.path.join(source_folder, "*.step"))
            
            for step_file in step_files:
                try:
                    # 计算文件行数
                    with open(step_file, 'r', encoding='utf-8') as f:
                        line_count = sum(1 for _ in f)
                    
                    # 如果行数不超过500，移动文件
                    if line_count <= 500:
                        # 创建目标文件夹（如果不存在）
                        if not os.path.exists(target_folder):
                            os.makedirs(target_folder)
                        
                        # 构建目标文件路径
                        file_name = os.path.basename(step_file)
                        target_file = os.path.join(target_folder, file_name)
                        
                        # 移动文件
                        shutil.copy2(step_file, target_file)  # 使用copy2保留文件元数据
                        moved_files += 1
                        tqdm.write(f"已移动: {step_file} (行数: {line_count})")
                
                except Exception as e:
                    tqdm.write(f"处理文件 {step_file} 时出错: {str(e)}")
                
                # 更新进度条
                pbar.update(1)
    
    # 打印统计信息
    print(f"\n处理完成!")
    print(f"总共处理文件数: {total_files}")
    print(f"移动的文件数: {moved_files}")

if __name__ == "__main__":
    move_small_step_files()