import multiprocessing as mp
from PIL import Image
import numpy as np
import logging
import queue

logger = logging.getLogger(__name__)

class ImageProcessor(mp.Process):
    def __init__(self, image_queue, result_queue):
        super().__init__()
        self.image_queue = image_queue
        self.result_queue = result_queue
        self.running = mp.Value('b', True)
    
    def run(self):
        while self.running.value:
            try:
                # Get image task from queue
                task = self.image_queue.get(timeout=1)
                if task is None:  # Shutdown signal
                    break
                    
                image_path, shm_name, shape, dtype = task
                
                # Load and process image in separate process
                try:
                    # Load image with PIL
                    img = Image.open(image_path)
                    img_array = np.array(img)
                    
                    # Create shared memory
                    shm = mp.shared_memory.SharedMemory(name=shm_name)
                    shared_array = np.ndarray(shape, dtype=dtype, buffer=shm.buf)
                    shared_array[:] = img_array[:]
                    
                    # Signal completion
                    self.result_queue.put(("success", None))
                    
                except Exception as e:
                    self.result_queue.put(("error", str(e)))
                finally:
                    try:
                        shm.close()
                    except:
                        pass
                        
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Image processor error: {e}")
                
    def stop(self):
        self.running.value = False
