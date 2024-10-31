import os
from datetime import datetime
import vtk
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from OCC.Core.StlAPI import StlAPI_Writer
import numpy as np
import matplotlib.pyplot as plt

class StepVTKRenderer:
    def __init__(self, step_file):
        self.step_file = step_file
        self.shape = None
        self.views = [
            (30, 45), (30, 135), (30, 225), (30, 315),
            (60, 45), (60, 135), (60, 225), (60, 315),
            (85, 45), (85, 135), (85, 225), (85, 315)
        ]
        
    def load_step(self):
        """加载STEP文件"""
        reader = STEPControl_Reader()
        status = reader.ReadFile(self.step_file)
        if status == IFSelect_RetDone:
            reader.TransferRoot()
            self.shape = reader.Shape()
            return True
        return False
        
    def shape_to_stl(self, output_dir):
        """将STEP转换为STL"""
        if self.shape is None:
            return None
            
        # 创建网格
        mesh = BRepMesh_IncrementalMesh(self.shape, 0.1)
        mesh.Perform()
        
        # 保存为STL
        stl_path = os.path.join(output_dir, "temp.stl")
        writer = StlAPI_Writer()
        writer.Write(self.shape, stl_path)
        
        return stl_path
        
    def render_views(self, output_dir='output'):
        """渲染多个视角"""
        os.makedirs(output_dir, exist_ok=True)
        
        # 转换为STL
        stl_path = self.shape_to_stl(output_dir)
        if not stl_path:
            return None
            
        # 设置VTK渲染器
        renderer = vtk.vtkRenderer()
        render_window = vtk.vtkRenderWindow()
        render_window.SetOffScreenRendering(1)
        render_window.AddRenderer(renderer)
        
        # 读取STL
        reader = vtk.vtkSTLReader()
        reader.SetFileName(stl_path)
        
        # 创建映射器和actor
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(reader.GetOutputPort())
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        renderer.AddActor(actor)
        
        # 设置背景颜色
        renderer.SetBackground(1, 1, 1)  # 白色背景
        
        # 创建图表
        fig, axes = plt.subplots(3, 4, figsize=(20, 15))
        fig.suptitle(f'STEP File: {os.path.basename(self.step_file)}', fontsize=16)
        
        # 渲染每个视角
        for idx, (elev, azim) in enumerate(self.views):
            row = idx // 4
            col = idx % 4
            
            # 设置相机
            camera = renderer.GetActiveCamera()
            camera.SetPosition(np.cos(np.radians(azim)) * np.sin(np.radians(elev)),
                             np.sin(np.radians(azim)) * np.sin(np.radians(elev)),
                             np.cos(np.radians(elev)))
            camera.SetViewUp(0, 0, 1)
            camera.SetFocalPoint(0, 0, 0)
            
            renderer.ResetCamera()
            render_window.Render()
            
            # 捕获图像
            w2i = vtk.vtkWindowToImageFilter()
            w2i.SetInput(render_window)
            w2i.Update()
            
            # 将VTK图像转换为numpy数组
            vtk_image = w2i.GetOutput()
            width, height, _ = vtk_image.GetDimensions()
            vtk_array = vtk_image.GetPointData().GetScalars()
            components = vtk_array.GetNumberOfComponents()
            np_array = np.frombuffer(vtk_array, dtype=np.uint8)
            np_array = np_array.reshape(height, width, components)
            
            # 显示在matplotlib中
            axes[row, col].imshow(np_array)
            axes[row, col].axis('off')
            axes[row, col].set_title(f'Elevation: {elev}°, Azimuth: {azim}°')
        
        # 保存结果
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join(output_dir, f'step_visualization_{timestamp}.png')
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        # 清理临时文件
        if os.path.exists(stl_path):
            os.remove(stl_path)
            
        return output_path

def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    step_files = [f for f in os.listdir(current_dir) if f.lower().endswith('.step') or f.lower().endswith('.stp')]
    
    if not step_files:
        print("Error: No STEP files found in the current directory.")
        return
        
    step_file = os.path.join(current_dir, step_files[0])
    print(f"Processing STEP file: {step_file}")
    
    try:
        renderer = StepVTKRenderer(step_file)
        if renderer.load_step():
            output_path = renderer.render_views()
            if output_path:
                print(f"Visualization successfully saved to: {output_path}")
            else:
                print("Error: Failed to render views")
        else:
            print("Error: Failed to load STEP file")
    except Exception as e:
        print(f"Error occurred: {str(e)}")

if __name__ == "__main__":
    main()