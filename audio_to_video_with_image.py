import argparse
import subprocess
import os
import shutil
import re
from tqdm import tqdm

def main():
    parser = argparse.ArgumentParser(description='Create video from image and audio with FFmpeg')
    parser.add_argument('-i', '--image', required=True, help='Input image file')
    parser.add_argument('-a', '--audio', required=True, help='Input audio file')
    parser.add_argument('-o', '--output', required=True, help='Output video file')
    parser.add_argument('-d', '--debug', action='store_true', help='Show FFmpeg debug output')
    args = parser.parse_args()

    # Check if FFmpeg and ffprobe are available
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        print("Error: ffmpeg and ffprobe must be installed")
        return

    # Validate input files
    if not os.path.exists(args.image):
        print(f"Error: Image file not found - {args.image}")
        return
    if not os.path.exists(args.audio):
        print(f"Error: Audio file not found - {args.audio}")
        return

    # Get audio duration
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            args.audio
        ]
        duration = float(subprocess.check_output(cmd).decode().strip())
        if duration <= 0:
            raise ValueError("Invalid audio duration")
    except Exception as e:
        print(f"Error getting audio duration: {str(e)}")
        return

    # Build FFmpeg command
    ffmpeg_cmd = [
        'ffmpeg',
        '-loop', '1',
        '-i', args.image,
        '-i', args.audio,
        '-vf', 'fps=30,format=yuv420p',
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-c:a', 'aac',
        '-strict', 'experimental',
        '-t', str(duration),
        '-y',
        args.output
    ]

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

            # Capture error lines
            if 'error' in line.lower():
                error_lines.append(line.strip())

            # Show debug output if requested
            if args.debug:
                print(line.strip())

            # Update progress
            match = time_pattern.search(line)
            if match:
                try:
                    time_str = match.group(1)
                    parts = list(map(float, time_str.split(':')))
                    current_time = parts[0] * 3600 + parts[1] * 60 + parts[2]
                    progress_bar.n = current_time
                    progress_bar.refresh()
                except Exception as e:
                    continue

        progress_bar.close()
        process.communicate()  # Wait for process to finish

        if process.returncode != 0:
            print("\nError: FFmpeg processing failed")
            if error_lines:
                print("\nLast error messages:")
                for err in error_lines[-3:]:  # Show last 3 error lines
                    print(f" - {err}")
        else:
            print("\nVideo created successfully:", args.output)

    except KeyboardInterrupt:
        process.kill()
        print("\nProcess interrupted")

if __name__ == '__main__':
    main()
