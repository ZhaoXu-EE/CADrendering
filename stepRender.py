from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Display.SimpleGui import init_display
from OCC.Core.gp import gp_Dir, gp_Pnt, gp_Ax3
from OCC.Core.V3d import V3d_XposYnegZpos
from OCC.Extend.DataExchange import read_step_file
import os
from PIL import Image
import numpy as np

class STEPRenderer:
    def __init__(self):
        # 初始化显示器
        self.display, self.start_display, self.add_menu, self.add_function = init_display()
        
    def load_step(self, step_file_path):
        """加载STEP文件"""
        if not os.path.exists(step_file_path):
            raise FileNotFoundError(f"找不到STEP文件: {step_file_path}")
            
        self.shape = read_step_file(step_file_path)
        self.display.DisplayShape(self.shape, update=True)
        
    def set_view(self, dx, dy, dz):
        """设置视图方向"""
        self.display.View.SetProj(dx, dy, dz)
        self.display.FitAll()
        
    def capture_view(self, width=800, height=600):
        """捕获当前视图"""
        self.display.View.Dump('./temp_view.png')
        
        # 处理图像
        img = Image.open('./temp_view.png')
        img = img.resize((width, height))
        return img
        
    def render_multi_views(self, step_file_path, output_dir, views=None):
        """渲染多个视图"""
        if views is None:
            # 默认视图：等轴测、前视图、俯视图、右视图
            views = [
                {'name': 'isometric', 'dir': (1, 1, 1)},
                {'name': 'front', 'dir': (0, 0, 1)},
                {'name': 'top', 'dir': (0, 1, 0)},
                {'name': 'right', 'dir': (1, 0, 0)}
            ]
            
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 加载STEP文件
        self.load_step(step_file_path)
        
        # 渲染每个视图
        for view in views:
            self.set_view(*view['dir'])
            img = self.capture_view()
            output_path = os.path.join(output_dir, f"{view['name']}.png")
            img.save(output_path)
            print(f"已保存视图: {output_path}")
            
    def cleanup(self):
        """清理临时文件"""
        if os.path.exists('./temp_view.png'):
            os.remove('./temp_view.png')

def main():
    # 使用示例
    renderer = STEPRenderer()
    
    # 定义自定义视图（可选）
    custom_views = [
        {'name': 'isometric', 'dir': (1, 1, 1)},
        {'name': 'front', 'dir': (0, 0, 1)},
        {'name': 'top', 'dir': (0, 1, 0)},
        {'name': 'right', 'dir': (1, 0, 0)},
        {'name': 'custom1', 'dir': (1, 1, 0)},
        {'name': 'custom2', 'dir': (-1, 1, 1)}
    ]
    
    try:
        renderer.render_multi_views(
            step_file_path='/home/hpo6025/data/abccad_test/step/00000000/00000000_290a9120f9f249a7a05cfe9c_step_000.step',
            output_dir='/home/hpo6025/data/abccad_test/views',
            views=custom_views
        )
    finally:
        renderer.cleanup()

if __name__ == "__main__":
    main()