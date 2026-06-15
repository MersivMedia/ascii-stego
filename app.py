"""
ASCII Stego Web App

Upload image/video → Convert to ASCII → Embed hidden LLM instruction → Download
"""

import os
import sys
import io
import tempfile
from pathlib import Path

# Add parent dir for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, render_template, send_file, jsonify
from PIL import Image
import cv2
import numpy as np

from llm_stego import embed, extract, has_stego

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max

# ASCII characters from dark to light
ASCII_CHARS = '@%#*+=-:. '
ASCII_CHARS_DETAILED = '$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,"^`\'. '


def image_to_ascii(img: Image.Image, width: int = 100, detailed: bool = False) -> str:
    """Convert PIL Image to ASCII art."""
    # Calculate height to maintain aspect ratio (chars are ~2x tall as wide)
    aspect_ratio = img.height / img.width
    height = int(width * aspect_ratio * 0.5)
    
    # Resize and convert to grayscale
    img = img.resize((width, height))
    img = img.convert('L')
    
    # Map pixels to ASCII
    chars = ASCII_CHARS_DETAILED if detailed else ASCII_CHARS
    pixels = np.array(img)
    
    # Normalize to char index
    char_indices = (pixels / 255 * (len(chars) - 1)).astype(int)
    
    # Build ASCII string
    lines = []
    for row in char_indices:
        line = ''.join(chars[i] for i in row)
        lines.append(line)
    
    return '\n'.join(lines)


def video_to_ascii_frames(video_path: str, width: int = 80, max_frames: int = 100) -> list[str]:
    """Convert video to list of ASCII frames."""
    cap = cv2.VideoCapture(video_path)
    frames = []
    
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 24
    
    # Sample frames evenly if too many
    step = max(1, frame_count // max_frames)
    
    idx = 0
    while cap.isOpened() and len(frames) < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        
        if idx % step == 0:
            # Convert BGR to RGB, then to PIL
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb)
            ascii_frame = image_to_ascii(pil_img, width=width)
            frames.append(ascii_frame)
        
        idx += 1
    
    cap.release()
    return frames


def frames_to_document(frames: list[str], fps: float = 10) -> str:
    """Combine ASCII frames into a single document with frame separators."""
    separator = '\n' + '=' * 40 + ' FRAME {n} ' + '=' * 40 + '\n'
    
    parts = []
    for i, frame in enumerate(frames):
        parts.append(separator.format(n=i+1))
        parts.append(frame)
    
    header = f"ASCII VIDEO - {len(frames)} frames @ {fps:.1f} fps\n"
    header += "Play with: watch -n 0.1 'sed -n \"/FRAME X/,/FRAME Y/p\" file.txt'\n"
    
    return header + '\n'.join(parts)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/encode', methods=['POST'])
def encode():
    """Process upload and return stego ASCII."""
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    hidden_msg = request.form.get('message', '')
    width = int(request.form.get('width', 80))
    detailed = request.form.get('detailed', 'false').lower() == 'true'
    
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400
    
    if not hidden_msg:
        return jsonify({'error': 'No hidden message provided'}), 400
    
    # Determine file type
    ext = Path(file.filename).suffix.lower()
    is_video = ext in ['.mp4', '.avi', '.mov', '.webm', '.mkv', '.gif']
    
    try:
        if is_video:
            # Save to temp file for cv2
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                file.save(tmp.name)
                frames = video_to_ascii_frames(tmp.name, width=width)
                os.unlink(tmp.name)
            
            if not frames:
                return jsonify({'error': 'Could not extract frames from video'}), 400
            
            # Embed stego in first frame only (or spread across frames)
            frames[0] = embed(frames[0], hidden_msg)
            
            ascii_output = frames_to_document(frames)
            filename = 'stego_video.txt'
            
        else:
            # Image
            img = Image.open(file.stream)
            ascii_art = image_to_ascii(img, width=width, detailed=detailed)
            ascii_output = embed(ascii_art, hidden_msg)
            filename = 'stego_image.txt'
        
        # Return as downloadable file
        buffer = io.BytesIO(ascii_output.encode('utf-8'))
        buffer.seek(0)
        
        return send_file(
            buffer,
            mimetype='text/plain',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/preview', methods=['POST'])
def preview():
    """Preview ASCII without download."""
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    hidden_msg = request.form.get('message', '')
    width = int(request.form.get('width', 80))
    detailed = request.form.get('detailed', 'false').lower() == 'true'
    
    ext = Path(file.filename).suffix.lower()
    is_video = ext in ['.mp4', '.avi', '.mov', '.webm', '.mkv', '.gif']
    
    try:
        if is_video:
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                file.save(tmp.name)
                frames = video_to_ascii_frames(tmp.name, width=width, max_frames=5)
                os.unlink(tmp.name)
            
            ascii_output = frames[0] if frames else "Could not extract frames"
            frame_count = len(frames)
        else:
            img = Image.open(file.stream)
            ascii_output = image_to_ascii(img, width=width, detailed=detailed)
            frame_count = 1
        
        # Show with stego if message provided
        if hidden_msg:
            ascii_output = embed(ascii_output, hidden_msg)
        
        return jsonify({
            'ascii': ascii_output,
            'frames': frame_count,
            'has_stego': has_stego(ascii_output),
            'char_count': len(ascii_output)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/decode', methods=['POST'])
def decode():
    """Extract hidden message from ASCII text."""
    
    text = request.form.get('text', '')
    
    if 'file' in request.files and request.files['file'].filename:
        text = request.files['file'].read().decode('utf-8')
    
    if not text:
        return jsonify({'error': 'No text provided'}), 400
    
    hidden = extract(text)
    
    return jsonify({
        'has_stego': hidden is not None,
        'message': hidden,
        'char_count': len(text)
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=True)
