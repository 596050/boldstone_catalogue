# main_thread_order_queue.py

import queue
import datetime

class MainThreadOrderQueue:
    """
    A queue system that allows worker threads to schedule order submissions
    to be executed by the main thread which has event loop access.
    """
    def __init__(self, ib):
        self.ib = ib
        self.queue = queue.Queue()
        self.is_running = True
        
        # Schedule the first queue processing
        next_time = datetime.datetime.now() + datetime.timedelta(seconds=0.1)
        self.ib.schedule(next_time, self._process_queue)
        print(f"Order queue processor scheduled to start at {next_time.strftime('%H:%M:%S.%f')}")
    
    def add_task(self, task, *args, **kwargs):
        """Add a task to be executed in the main thread"""
        self.queue.put((task, args, kwargs))
    
    def _process_queue(self):
        """Process pending tasks in the queue (runs in main thread)"""
        try:
            # Process up to 10 items per cycle to avoid blocking
            for _ in range(10):
                if self.queue.empty():
                    break
                
                task, args, kwargs = self.queue.get_nowait()
                try:
                    task(*args, **kwargs)
                except Exception as e:
                    print(f"Error executing task in main thread: {e}")
                finally:
                    self.queue.task_done()
        
        except Exception as e:
            print(f"Error in queue processing: {e}")
        
        finally:
            # Schedule the next processing if still running
            if self.is_running:
                next_time = datetime.datetime.now() + datetime.timedelta(seconds=0.1)
                self.ib.schedule(next_time, self._process_queue)
    
    def shutdown(self):
        """Stop the queue processing"""
        self.is_running = False