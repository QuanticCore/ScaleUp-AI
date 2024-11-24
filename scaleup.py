import os
from queue import Queue
from threading import Thread
import argparse
import shutil
import subprocess
import time
import sys
import signal
from collections import deque

# Default model, upscale factor, GPU ID, frame directories, and thread count
CURRENT_MODEL = 'realesr-animevideov3-x4'
UPSCALE_FACTOR = "4"
GPU_ID = '0'
TMP_FRAMES_DIR = 'tmp_frames'
OUT_FRAMES_DIR = 'out_frames'
THREAD_COUNT = 1


# Global flag to signal threads to stop
stop_threads = False


def run_command(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return result.returncode, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        print(f"Command '{e.cmd}' failed with return code {e.returncode}")
        print(f"Error message: {e.stderr}")
        exit(0)


def clear_console():
    """Clear the console screen."""
    if os.name == 'nt':  # For Windows
        os.system('cls')
    else:  # For Linux or macOS
        os.system('clear')


def print_progress_bar(iteration, total, prefix='', suffix='', length=50, fill='█'):
    if total == 0:
        return  # Avoid division by zero
    percent = ("{0:.1f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)

    # Print the progress bar (this will be on the last line)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end='\r')

    # If the iteration is complete, print a newline (end the progress bar)
    if iteration == total:
        print()

def calculate_framerate(frame_rate_str):
    parts = frame_rate_str.split('x')
    if len(parts) == 3:
        fps_str = parts[2]
    else:
        raise ValueError("Unexpected format for frame rate string")

    fps_numerator, fps_denominator = fps_str.split('/')
    fps = int(fps_numerator) / int(fps_denominator)

    return fps


def get_video_framerate(input_video):
    ffprobe_command = [
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=avg_frame_rate,width,height', '-of', 'csv=s=x:p=0',
        input_video
    ]
    result = subprocess.run(ffprobe_command, capture_output=True, text=True, check=True)

    # Extracting the frame rate string from the output
    frame_rate_str = result.stdout.strip().split('\n')[0]

    # Calculate the frame rate
    fps = calculate_framerate(frame_rate_str)

    return str(fps)


def upscale_frame(input_frame, output_frame, model, upscale_factor, gpu_id):
    # Use GPU (CUDA) by specifying the -g flag in the command
    realesrgan_command = [
        './realesrgan-ncnn-vulkan.exe', '-i', input_frame, '-o', output_frame,
        '-n', model, '-s', upscale_factor, '-f', 'png', '-g', gpu_id
    ]
    _, realesrgan_stdout, realesrgan_stderr = run_command(realesrgan_command)


def process_frame(input_frame_path, output_frame_path, frame_index, total_frames, model, upscale_factor, gpu_id, recent_times, thread_count):
    """
    Process a single frame and estimate the remaining time using a sliding window of recent frame times.
    - recent_times: A deque that holds the processing times of the most recent frames
    """
    # Start time to calculate elapsed time
    start_time = time.time()

    # Upscale the frame
    upscale_frame(input_frame_path, output_frame_path, model, upscale_factor, gpu_id)

    # Calculate elapsed time
    elapsed_time = time.time() - start_time

    # Update the recent times sliding window (keep the last 10 frame times)
    recent_times.append(elapsed_time)
    if len(recent_times) > 10:  # Keep only the last 10 frame times
        recent_times.popleft()

    frames_processed = frame_index + 1  # We count from 0, so add 1 to match progress bar
    remaining_frames = total_frames - frames_processed

    # Calculate average processing time from the last 'n' frames
    if len(recent_times) > 0:
        avg_time_per_frame = sum(recent_times) / len(recent_times)
    else:
        avg_time_per_frame = 0

    # Estimate remaining time
    remaining_time = (avg_time_per_frame * remaining_frames) / thread_count

    # Convert remaining time into hours, minutes, and seconds format
    hours, remainder = divmod(remaining_time, 3600)
    minutes, seconds = divmod(remainder, 60)
    formatted_remaining_time = f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"

    clear_console()
    print(f"Processed Frame {frames_processed}/{total_frames}: {input_frame_path}")
    print(f"Elapsed Time: {elapsed_time:.2f}s | Average Time per Frame: {avg_time_per_frame:.2f}s")
    print(f"Remaining Time: {formatted_remaining_time}")

    # Print progress bar with remaining time
    print_progress_bar(frames_processed, total_frames, prefix='Progress', length=50)


def merge_video_audio(output_video, input_audio):
    ffmpeg_command = [
        'ffmpeg', '-framerate', '30', '-i', os.path.join(OUT_FRAMES_DIR, 'frame%08d.jpg'), '-i', input_audio, '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-strict', 'experimental', '-shortest', output_video
    ]
    run_command(ffmpeg_command)


def extract_frames(input_video, tmp_frames_dir):
    os.makedirs(tmp_frames_dir, exist_ok=True)  # Ensure directory exists
    
    ffmpeg_command = [
        'ffmpeg', '-i', input_video, '-qscale:v', '1', '-qmin', '1', '-qmax', '1', '-vsync', '0',
        os.path.join(tmp_frames_dir, 'frame%08d.jpg')
    ]
    
    print(f"Running command: {ffmpeg_command}")  # Debugging output
    run_command(ffmpeg_command)


def confirm_reset(tmp_frames_dir, out_frames_dir):
    """Prompt user to confirm reset of the upscaled and extracted frames."""
    if os.path.exists(tmp_frames_dir) or os.path.exists(out_frames_dir):
        print("\nWarning: Resetting will delete the extracted and upscaled frames.")
        confirmation = input("Are you sure you want to reset (delete) these frames? This action cannot be undone (yes/no): ").strip().lower()
        if confirmation != 'yes':
            print("Reset canceled. Exiting.")
            exit(0)
    else:
        print("No frames found to delete. Proceeding with reset.")


def upscale_worker(worker_id, frame_queue, total_frames, model, upscale_factor, gpu_id, start_index, thread_count, verbose):
    """
    Worker function for upscaling frames. Pulls frames from the queue and processes them.
    Skips frames based on the starting index.
    """
    global stop_threads
    recent_times = deque()  # Initialize an empty deque to store recent frame processing times

    while not stop_threads:
        frame_index, input_frame_path, output_frame_path = frame_queue.get()
        
        if frame_index is None:  # Sentinel to exit the thread
            break

        # Skip frames below the starting index
        if frame_index < start_index:
            frame_queue.task_done()
            continue

        # Process the frame with enhanced time calculation
        process_frame(input_frame_path, output_frame_path, frame_index, total_frames, model, upscale_factor, gpu_id, recent_times, thread_count)

        # Mark task as done
        frame_queue.task_done()


def signal_handler(signal, frame):
    """Handle the interrupt signal and gracefully stop threads."""
    global stop_threads
    print("\nReceived interrupt signal. Stopping threads...")
    stop_threads = True  # Set the flag to stop threads


def main():
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)

    # Set up argument parsing
    parser = argparse.ArgumentParser(description='Process input and generate output video using ffmpeg and realesrgan-ncnn-vulkan.')
    parser.add_argument('-i', '--input', required=True, help='Input video file')
    parser.add_argument('-o', '--output', required=True, help='Output video file')
    parser.add_argument('-g', '--gpu_id', default=GPU_ID, help='GPU ID (default: 0)')
    parser.add_argument('-m', '--model', default=CURRENT_MODEL, help='Model to use for upscaling (default: realesrgan-x4plus)')
    parser.add_argument('-s', '--upscale_factor', default=UPSCALE_FACTOR, help='Upscale factor (default: 4)')
    parser.add_argument('-r', '--reset', action='store_true', help='Reset the upscaler')
    parser.add_argument('--tmp_frames', default=TMP_FRAMES_DIR, help='Directory for temporary frames (default: tmp_frames)')
    parser.add_argument('--out_frames', default=OUT_FRAMES_DIR, help='Directory for output frames (default: out_frames)')
    parser.add_argument('--thread_count', default=THREAD_COUNT, help='Amount of threads used to upscale the video')
    parser.add_argument('-v', '--verbose', action='store_true', help='Show more information')

    args = parser.parse_args()

    try:
        # Validate reset argument
        if args.reset:
            confirm_reset(args.tmp_frames, args.out_frames)

        # Reset the directories if the reset argument is passed
        if args.reset:
            if os.path.exists(args.output):
                os.remove(args.output)
            if os.path.exists(args.tmp_frames):
                shutil.rmtree(args.tmp_frames)
            if os.path.exists(args.out_frames):
                shutil.rmtree(args.out_frames)

        # Get video metadata to calculate frame rate
        print("Getting video metadata...")
        framerate = get_video_framerate(args.input)
        print(f"Framerate: {framerate}")
        print(f"Threads: {args.thread_count}")

        # Check if frames already exist, otherwise extract them
        if not os.path.exists(args.tmp_frames):
            print("Extracting frames from input video...")
            extract_frames(args.input, args.tmp_frames)

        # Read frames
        existing_frames = sorted(os.listdir(args.tmp_frames))
        total_frames = len(existing_frames)

        # Prepare the output directory
        os.makedirs(args.out_frames, exist_ok=True)

        # Determine how many frames have already been processed
        processed_frame_count = len(os.listdir(args.out_frames))
        print(f"Skipping the first {processed_frame_count} frames (already upscaled).")

        # Prepare a thread-safe queue for frame processing
        frame_queue = Queue()
        for i, frame in enumerate(existing_frames):
            input_frame_path = os.path.join(args.tmp_frames, frame)
            output_frame_path = os.path.join(args.out_frames, frame)
            frame_queue.put((i, input_frame_path, output_frame_path))

        # Add sentinel values to signal threads to exit
        for _ in range(int(args.thread_count)):
            frame_queue.put((None, None, None))

        # Launch threads for frame processing
        threads = []
        for i in range(int(args.thread_count)):
            thread = Thread(target=upscale_worker, args=(i, frame_queue, total_frames, args.model, args.upscale_factor, args.gpu_id, processed_frame_count, int(args.thread_count), args.verbose))
            thread.start()
            threads.append(thread)

        # Wait for all tasks to be completed
        frame_queue.join()

        # Wait for all threads to finish
        for thread in threads:
            thread.join()

        # Merge video and audio at the end
        print("Merging video with audio...")
        merge_video_audio(args.output, args.input)

        print("All frames have been processed, and video with audio has been created.")
    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Exiting...")
        sys.exit(0)

if __name__ == '__main__':
    main()