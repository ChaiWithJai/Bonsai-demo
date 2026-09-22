"""Create synthetic video cards for timestamped OCR development checks.

CPU preparation only. Upload and model execution are separate, recorded steps.
The output directory must be new to preserve previous artifacts.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw, ImageFont


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--font', default='/System/Library/Fonts/Helvetica.ttc')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    font = ImageFont.truetype(args.font, 42)
    expected = []
    for index, (stage, count, second) in enumerate([
        ('Intake', 12, 0), ('Review', 7, 2.875), ('Approved', 3, 5.75)
    ]):
        image = Image.new('RGB', (960, 540), 'white')
        draw = ImageDraw.Draw(image)
        for y, text in [(65, 'DEVELOPMENT WORKSTREAM'), (185, 'Stage: ' + stage),
                        (275, 'Records: ' + str(count)), (390, 'Synthetic evaluation data')]:
            draw.text((60, y), text, font=font, fill='black')
        image.save(args.output / f'card-{index}.png')
        expected.append({'stage': stage, 'records': count, 'sample_seconds': second})
    video = args.output / 'development-three-stage.mp4'
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-framerate', '1/2',
                    '-i', str(args.output / 'card-%d.png'), '-c:v', 'libx264',
                    '-r', '10', '-pix_fmt', 'yuv420p', str(video)], check=True)
    (args.output / 'fixture.json').write_text(json.dumps({
        'expected': expected, 'sha256': hashlib.sha256(video.read_bytes()).hexdigest(),
        'font': args.font, 'font_sha256': hashlib.sha256(Path(args.font).read_bytes()).hexdigest(),
        'scope': 'Synthetic development OCR fixture; not a human label or motion benchmark'
    }, indent=2))


if __name__ == '__main__':
    main()
