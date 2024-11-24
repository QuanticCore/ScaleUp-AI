# Video Upscaler and Enhancer

This Python script provides a toolchain to upscale video frames using the **Real-ESRGAN NCNN Vulkan** framework, process frames in parallel using multi-threading, and merge the upscaled frames back into a video with audio. The script handles frame extraction, upscaling, and video/audio merging.

## Table of Contents
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Arguments](#arguments)
- [Example Commands](#example-commands)
- [Reset Option](#reset-option)
- [Dependencies](#dependencies)
- [License](#license)

---

## Features
- Upscales videos frame-by-frame using the **Real-ESRGAN** model.
- Multi-threaded processing for faster upscaling.
- Handles frame extraction and merging back into a video with audio.
- Progress tracking with estimated remaining time.
- Support for resuming from already processed frames.

---

## Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/your-repo-name/video-upscaler.git
   cd video-upscaler
   ```

2. Install **Real-ESRGAN NCNN Vulkan**:
   - Download the binary for your platform from the [Real-ESRGAN releases](https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan/releases).
   - Place the `realesrgan-ncnn-vulkan.exe` binary in the same directory as this script or in your system PATH.

3. Ensure you have **FFmpeg** installed:
   - On Debian/Ubuntu:
     ```bash
     sudo apt update && sudo apt install ffmpeg
     ```
   - On Windows:
     Download from [FFmpeg.org](https://ffmpeg.org/) and add it to your PATH or by using choco:
     ```powershell
      choco install ffmpeg
     ```

---

## Usage

### Basic Syntax
```bash
python video_upscaler.py -i <input_video> -o <output_video> [OPTIONS]
```

### Arguments
| Argument              | Description                                                                                     | Default                       |
|-----------------------|-------------------------------------------------------------------------------------------------|-------------------------------|
| `-i, --input`         | Path to the input video file.                                                                   | Required                      |
| `-o, --output`        | Path to the output video file.                                                                  | Required                      |
| `-g, --gpu_id`        | ID of the GPU to use for processing.                                                            | `0`                           |
| `-m, --model`         | Model to use for upscaling. Options include `realesrgan-x4plus`, `realesr-animevideov3-x4`.     | `realesr-animevideov3-x4`     |
| `-s, --upscale_factor`| Scale factor for upscaling.                                                                     | `4`                           |
| `-r, --reset`         | Reset by clearing temporary and output frame directories.                                       | False                         |
| `--tmp_frames`        | Directory to store extracted frames.                                                            | `tmp_frames`                  |
| `--out_frames`        | Directory to store upscaled frames.                                                             | `out_frames`                  |
| `--thread_count`      | Number of threads to use for parallel frame processing.                                         | `1`                           |

---

## Example Commands

### 1. Upscale a video
```bash
python video_upscaler.py -i input.mp4 -o output.mp4
```

### 2. Upscale using a specific GPU and model
```bash
python video_upscaler.py -i input.mp4 -o output.mp4 -g 1 -m realesrgan-x4plus
```

### 3. Upscale with multiple threads (e.g., 4 threads)
```bash
python video_upscaler.py -i input.mp4 -o output.mp4 --thread_count 4
```

### 4. Reset and process a video
```bash
python video_upscaler.py -i input.mp4 -o output.mp4 -r
```

---

## Reset Option
Using the `--reset` flag deletes all previously extracted and upscaled frames, effectively resetting the project. Use this option when starting a new project or encountering issues with partially processed videos.

```bash
python video_upscaler.py -i input.mp4 -o output.mp4 -r
```

---

## Dependencies

### Software Requirements
- **Python 3.8+**
- **FFmpeg** (for frame extraction and merging video/audio)
- **Real-ESRGAN NCNN Vulkan** (for upscaling frames)

### Python Libraries
- `argparse` (standard library)
- `shutil` (standard library)
- `subprocess` (standard library)
- `threading` (standard library)
- `queue` (standard library)

### Installation Notes
- Ensure that `ffmpeg` and `realesrgan-ncnn-vulkan` are properly installed and accessible in your system's PATH.

---

## License
This script is provided under the [MIT License](LICENSE). You are free to use, modify, and distribute this software with attribution.

---

## Acknowledgments
- [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN): High-quality image and video upscaling framework.
- [FFmpeg](https://ffmpeg.org/): Powerful multimedia framework for handling video and audio processing.