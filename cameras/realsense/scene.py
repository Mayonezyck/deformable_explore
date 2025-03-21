import open3d as o3d
import numpy as np
from ultralytics import YOLO
import threading
import time

class Scene:
    def __init__(self,camera, update_delay = -1):
        self.global_map = o3d.geometry.PointCloud()
        self.camera = camera
        self.model = YOLO("yolo11x-seg.pt")

        self.update_delay = update_delay
        self.is_done = False
        self.lock = threading.Lock()

        self.app = o3d.visualization.gui.Application.instance
        self.window = self.app.create_window("Open3D Python App", width=800, height=600, x=0, y=30)
        self.window.set_on_close(self.on_main_window_closing)
        if self.update_delay < 0:
            self.window.set_on_tick_event(self.on_main_window_tick_event)

        self.widget = o3d.visualization.gui.SceneWidget()
        self.widget.scene = o3d.visualization.rendering.Open3DScene(self.window.renderer)
        self.widget.scene.set_background([1.0, 1.0, 1.0, 1.0])
        self.window.add_child(self.widget)

        self.add_depth_image()
        self.geom_mat = o3d.visualization.rendering.MaterialRecord()
        self.geom_mat.shader = 'defaultUnlit'
        self.geom_mat.point_size = 2.0

        self.widget.scene.add_geometry('Global Map', self.global_map)

        self.widget.setup_camera(60, self.widget.scene.bounding_box, [0, 0, 0])
    
    def startThread(self):
            if self.update_delay >= 0:
                threading.Thread(target=self.update_thread).start()

    def update_thread(self):
            def do_update():
                return self.update_point_cloud()

            while not self.is_done:
                time.sleep(self.update_delay)
                print("update_thread")
                with self.lock:
                    if self.is_done:  # might have changed while sleeping.
                        break
                    o3d.visualization.gui.Application.instance.post_to_main_thread(self.window, self.update_point_cloud)
    def on_main_window_closing(self):
        with self.lock:
            self.is_done = True
        return True  # False would cancel the close
    def on_main_window_tick_event(self):
        print("tick")
        return self.update_point_cloud()
    '''def add_depth_image_random(self):
        print('Adding random depth image to scene...')
        depth_image = np.random.randint(0, 1000, (480, 640)).astype(np.float32)
        mask = np.random.randint(0, 2, (480, 640)).astype(bool)
        intrinsics = np.array([[525.0, 0.0, 319.5], [0.0, 525.0, 239.5], [0.0, 0.0, 1.0]])
        self.add_depth_image(depth_image, mask, intrinsics)'''
    
    def decaying(self):
        colors = np.asarray(self.global_map.colors)
        colors = np.clip(colors - 5 / 255.0, 0, 1)
        self.global_map.colors = o3d.utility.Vector3dVector(colors)
    
    def delete_points(self,death_threshold):
        colors = np.asarray(self.global_map.colors)
        points = np.asarray(self.global_map.points)
        mask = np.all(colors >= death_threshold / 255.0, axis=1)
        self.global_map.points = o3d.utility.Vector3dVector(points[mask])
        self.global_map.colors = o3d.utility.Vector3dVector(colors[mask])

    def trim_points(self, input_points, input_colors, input_percentage):
        num_points = len(input_points)
        num_points_to_keep = int(num_points * input_percentage)
        indices = np.random.choice(num_points, num_points_to_keep, replace=False)
        trimmed_points = input_points[indices]
        trimmed_colors = input_colors[indices]
        return trimmed_points, trimmed_colors

    def add_depth_image(self):
        intrinsics = self.camera.intrinsics
        depth_image = self.camera.get_depth_image()
        #color_image = self.camera.get_color_image()
        mask = self.getMask()
        # Convert depth image to point cloud
        height, width = depth_image.shape
        fx = intrinsics.fx
        fy = intrinsics.fy
        cx = intrinsics.ppx
        cy = intrinsics.ppy
        points = []
        for v in range(height):
            for u in range(width):
                if mask[v, u]:
                    z = depth_image[v, u] / 1000.0  # Convert from mm to meters
                    if z > 0:
                        x = (u - cx) * z / fx
                        y = (v - cy) * z / fy
                        points.append([x, y, z])
        # Create point cloud from points
        if points:
            points = np.array(points)
            colors = np.full(points.shape, 127 / 255.0)  # Assign color with 127
            # colors = color_image[mask]
            # colors = colors / 255.0  # Normalize colors to [0, 1]
            points, colors = self.trim_points(points, colors, 0.1)

            point_cloud = o3d.geometry.PointCloud()
            point_cloud.points = o3d.utility.Vector3dVector(points)
            point_cloud.colors = o3d.utility.Vector3dVector(colors)
            
            # Merge with global map
            self.global_map += point_cloud

    def display(self):
        vis = o3d.visualization.Visualizer()
        vis.create_window(window_name="Global Map", width=800, height=600)
        vis.add_geometry(self.global_map)
        vis.run()
        counter = 0
        while True:
            counter += 1
            #print('Displaying global map...')
            intrinsics = self.camera.intrinsics
            depth_image = self.camera.get_depth_image()
            color_image = self.camera.get_color_image()
            mask = self.getMask()
            if mask is not None and counter % 90 == 0:
                self.add_depth_image(depth_image, color_image, mask, intrinsics)
            #print(f'Point cloud size: {len(self.global_map.points)}')
            if counter % 1000 == 0:
                print('Decaying colors...')
                self.decaying()
                self.delete_points(0.2)
            if counter % 2 == 0:
                vis.update_geometry(self.global_map)
                vis.poll_events()
                vis.update_renderer()
            

    def test_display_static_pointcloud(self):
        # Create a static point cloud
        intrinsics = self.camera.intrinsics
        depth_image = self.camera.get_depth_image()
        color_image = self.camera.get_color_image()
        mask = self.getMask()
        print(f'Depth image shape: {depth_image.shape}')
        print(f'Color image shape: {color_image.shape}')
        print(f'Mask shape: {mask.shape}')
        
        vis = o3d.visualization.Visualizer()
        vis.create_window(window_name="Static Point Cloud", width=800, height=600)
        vis.add_geometry(self.global_map)
        vis.run()
        vis.destroy_window()

    def getMask(self):
        frames = self.camera.get_frames()
        color_frame = frames.get_color_frame()
        depth_frame = frames.get_depth_frame()
        color_image = np.asanyarray(color_frame.get_data())
        depth_image = np.asanyarray(depth_frame.get_data())
        results = self.model(color_image)
        result_mask = None
        if results is not None:
            for result in results:
                if result.masks is not None:
                    xy = result.masks.xy  # mask in polygon format
                    xyn = result.masks.xyn  # normalized
                    masks = result.masks.data  # mask in matrix format (num_objects x H x W)
                    print(masks.shape)
        if masks is not None:
            for mask in masks:
                if result_mask is None:
                    result_mask = mask.cpu().numpy()
                else:
                    result_mask = np.logical_or(result_mask, mask.cpu().numpy())
        return result_mask
    
    
