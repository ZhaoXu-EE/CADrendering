import os
from datetime import datetime
import vtk
import numpy as np
import matplotlib.pyplot as plt

class STLRenderer:
    def __init__(self, stl_file):
        self.stl_file = stl_file
        self.views = [
            (30, 45), (30, 135), (30, 225), (30, 315),   # 上方视角
            (60, 45), (60, 135), (60, 225), (60, 315),   # 中间视角
            (85, 45), (85, 135), (85, 225), (85, 315)    # 下方视角
        ]
        
        # 初始化VTK对象
        self.renderer = None
        self.render_window = None
        self.actor = None
        
    def setup_visualization(self):
        """设置VTK可视化管线"""
        try:
            # 读取STL
            reader = vtk.vtkSTLReader()
            reader.SetFileName(self.stl_file)
            reader.Update()
            
            # 计算模型中心和大小
            center = reader.GetOutput().GetCenter()
            bounds = reader.GetOutput().GetBounds()
            size = max([bounds[1]-bounds[0], bounds[3]-bounds[2], bounds[5]-bounds[4]])
            
            # 创建映射器
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(reader.GetOutputPort())
            
            # 创建actor并设置属性
            self.actor = vtk.vtkActor()
            self.actor.SetMapper(mapper)
            self.actor.GetProperty().SetColor(0.8, 0.8, 0.8)  # 设置灰色
            self.actor.GetProperty().SetAmbient(0.1)
            self.actor.GetProperty().SetDiffuse(0.7)
            self.actor.GetProperty().SetSpecular(0.3)
            self.actor.GetProperty().SetSpecularPower(60.0)
            
            # 设置渲染器
            self.renderer = vtk.vtkRenderer()
            self.renderer.AddActor(self.actor)
            self.renderer.SetBackground(1, 1, 1)  # 白色背景
            
            # 设置光源
            light = vtk.vtkLight()
            light.SetPosition(1, 1, 1)
            light.SetFocalPoint(0, 0, 0)
            light.SetIntensity(0.8)
            self.renderer.AddLight(light)
            
            # 设置渲染窗口
            self.render_window = vtk.vtkRenderWindow()
            self.render_window.AddRenderer(self.renderer)
            self.render_window.SetOffScreenRendering(1)
            self.render_window.SetSize(800, 800)  # 设置更高的分辨率
            
            return True, (center, size)
        except Exception as e:
            print(f"Error setting up visualization: {str(e)}")
            return False, None
            
    def render_views(self, output_dir='output'):
        """渲染多个视角"""
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            # 设置可视化
            success, model_info = self.setup_visualization()
            if not success:
                return None
                
            center, size = model_info
            
            # 创建matplotlib图表
            fig, axes = plt.subplots(3, 4, figsize=(20, 15))
            fig.suptitle(f'STL File: {os.path.basename(self.stl_file)}', fontsize=16)
            
            # 渲染每个视角
            for idx, (elev, azim) in enumerate(self.views):
                row = idx // 4
                col = idx % 4
                
                # 设置相机
                camera = self.renderer.GetActiveCamera()
                
                # 计算相机位置
                distance = size * 2  # 调整这个值可以改变视图的缩放级别
                x = distance * np.cos(np.radians(azim)) * np.sin(np.radians(elev))
                y = distance * np.sin(np.radians(azim)) * np.sin(np.radians(elev))
                z = distance * np.cos(np.radians(elev))
                
                camera.SetPosition(x + center[0], y + center[1], z + center[2])
                camera.SetFocalPoint(center[0], center[1], center[2])
                camera.SetViewUp(0, 0, 1)
                camera.SetViewAngle(30)  # 设置视场角
                
                self.renderer.ResetCamera()
                self.render_window.Render()
                
                # 捕获图像
                w2i = vtk.vtkWindowToImageFilter()
                w2i.SetInput(self.render_window)
                w2i.Update()
                
                # 转换为numpy数组并显示
                vtk_image = w2i.GetOutput()
                width, height, _ = vtk_image.GetDimensions()
                vtk_array = vtk_image.GetPointData().GetScalars()
                components = vtk_array.GetNumberOfComponents()
                np_array = np.frombuffer(vtk_array, dtype=np.uint8)
                np_array = np_array.reshape(height, width, components)
                
                # 在matplotlib中显示
                axes[row, col].imshow(np_array)
                axes[row, col].axis('off')
                axes[row, col].set_title(f'Elevation: {elev}°\nAzimuth: {azim}°', fontsize=10)
            
            # 调整子图之间的间距
            plt.tight_layout(rect=[0, 0.03, 1, 0.95])
            
            # 保存结果
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = os.path.join(output_dir, f'stl_visualization_{timestamp}.png')
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            return output_path
            
        except Exception as e:
            print(f"Error rendering views: {str(e)}")
            return None

def main():
    # 查找当前目录下的STL文件
    current_dir = os.path.dirname(os.path.abspath(__file__))
    stl_files = [f for f in os.listdir(current_dir) if f.lower().endswith('.stl')]
    
    if not stl_files:
        print("Error: No STL files found in the current directory.")
        return
        
    stl_file = os.path.join(current_dir, stl_files[0])
    print(f"Processing STL file: {stl_file}")
    
    try:
        # 创建渲染器并生成视图
        renderer = STLRenderer(stl_file)
        output_path = renderer.render_views()
        
        if output_path:
            print(f"Visualization successfully saved to: {output_path}")
        else:
            print("Error: Failed to render views")
            
    except Exception as e:
        print(f"Error occurred: {str(e)}")

if __name__ == "__main__":
    main()