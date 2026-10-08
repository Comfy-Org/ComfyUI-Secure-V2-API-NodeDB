"""Exact pinned pack grid method; no host services."""
from PIL import Image

class OriginalGrid:
    def create_image_grid(self, pil_images, grid_rows, grid_cols):
            total_tiles = grid_rows * grid_cols
            
            # Calculate total grid dimensions
            tile_width = max(img.width for img in pil_images)
            tile_height = max(img.height for img in pil_images)
            
            grid_width = tile_width * grid_cols
            grid_height = tile_height * grid_rows
            
            grid_image = Image.new('RGB', (grid_width, grid_height), color='black')
            
            # Paste images into the grid
            for i in range(grid_rows):
                for j in range(grid_cols):
                    try:
                        # Calculate the position for each image
                        x = j * tile_width
                        y = i * tile_height
                        curr_image = pil_images[i * grid_cols + j]
                        
                        # Paste the image into the grid
                        # Center the image if it's smaller than the max tile size
                        paste_x = x + (tile_width - curr_image.width) // 2
                        paste_y = y + (tile_height - curr_image.height) // 2
                        grid_image.paste(curr_image, (paste_x, paste_y))
                    except:
                        continue
            
            return grid_image
