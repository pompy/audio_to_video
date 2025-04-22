import argparse
import subprocess
import os
import shutil
import re
from tqdm import tqdm

def main():
    parser = argparse.ArgumentParser(description='Create video from multiple images and audio')
    parser.add_argument('-i', '--images', nargs='+', required=True, help='Input image files')
    parser.add_argument('-a', '--audio', required=True, help='Input audio file')
    parser.add_argument('-o', '--output', required=True, help='Output video file')
    parser.add_argument('-r', '--resolution', help='Force output resolution (e.g., 1920x1080)')
    parser.add_argument('-d', '--debug', action='store_true', help='Show FFmpeg debug output')
    args = parser.parse_args()

    # Check requirements
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        print("Error: ffmpeg and ffprobe must be installed")
        return

    # Validate files
    for img in args.images:
        if not os.path.exists(img):
            print(f"Error: Image file not found - {img}")
            return
    if not os.path.exists(args.audio):
        print(f"Error: Audio file not found - {args.audio}")
        return

    # Get audio duration
    try:
        duration = float(subprocess.check_output([
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            args.audio
        ]).decode().strip())
    except subprocess.CalledProcessError:
        print("Error: Could not get audio duration")
        return

    # Calculate per-image duration
    num_images = len(args.images)
    per_image_duration = duration / num_images

    # Build FFmpeg command
    ffmpeg_cmd = ['ffmpeg', '-y', '-i', args.audio]
    
    # Add image inputs
    for img in args.images:
        ffmpeg_cmd += ['-loop', '1', '-t', f'{per_image_duration:.2f}', '-i', img]

    # Build filter graph
    filter_complex = []
    concat_inputs = []
    
    for i in range(num_images):
        if args.resolution:
            filter_complex.append(f'[{i+1}:v]scale={args.resolution},setsar=1[s{i}]')
        else:
            filter_complex.append(f'[{i+1}:v]setsar=1[s{i}]')
        concat_inputs.append(f'[s{i}]')
    
    filter_complex.append(f'{"".join(concat_inputs)}concat=n={num_images}:v=1:a=0[v]')
    ffmpeg_cmd += ['-filter_complex', ';'.join(filter_complex)]

    # Output options
    ffmpeg_cmd += [
        '-map', '[v]',
        '-map', '0:a',
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-c:a', 'aac',
        '-strict', 'experimental',
        args.output
    ]

    # Run FFmpeg
    try:
        process = subprocess.Popen(
            ffmpeg_cmd,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )

        progress_bar = tqdm(total=duration, unit='s', desc='Processing')
        time_pattern = re.compile(r'time=(\d+:\d+:\d+\.\d+)')
        error_lines = []

        while True:
            line = process.stderr.readline()
            if not line:
                break

            # Capture errors
            if 'error' in line.lower():
                error_lines.append(line.strip())

            # Show debug output
            if args.debug:
                print(line.strip())

            # Update progress
            match = time_pattern.search(line)
            if match:
                try:
                    h, m, s = map(float, match.group(1).split(':'))
                    current_time = h * 3600 + m * 60 + s
                    progress_bar.n = min(current_time, duration)
                    progress_bar.refresh()
                except:
                    continue

        progress_bar.close()
        process.communicate()

        if process.returncode != 0:
            print("\nError: FFmpeg processing failed")
            if error_lines:
                print("\nLast errors:")
                for err in error_lines[-3:]:
                    print(f" - {err}")
        else:
            print(f"\nVideo created successfully: {args.output}")

    except KeyboardInterrupt:
        process.kill()
        print("\nProcess interrupted")

if __name__ == '__main__':
    main()
