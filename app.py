from flask import Flask, render_template, request, send_file, redirect, url_for, send_from_directory
from rembg import remove
from PIL import Image
import io
import os
import zipfile
import uuid

app = Flask(__name__)

UPLOAD_FOLDER = '/tmp/uploads'
PROCESSED_FOLDER = '/tmp/static/processed'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# Add this route to serve files from the PROCESSED_FOLDER
@app.route('/static/processed/<path:filename>')
def serve_processed(filename):
    return send_from_directory(PROCESSED_FOLDER, filename)

@app.route('/', methods=['GET'])
def index():
    batch_id = request.args.get('batch_id')
    size = request.args.get('size')
    images = []
    if batch_id:
        batch_folder = os.path.join(PROCESSED_FOLDER, batch_id)
        if os.path.exists(batch_folder):
            images = os.listdir(batch_folder)

    return render_template('index.html', images=images, batch_id=batch_id, size=size)

@app.route('/upload', methods=['POST'])
def upload():
    batch_id = str(uuid.uuid4())
    batch_folder = os.path.join(PROCESSED_FOLDER, batch_id)
    os.makedirs(batch_folder, exist_ok=True)

    selected_size = request.form.get('size')  # Get the selected size
#    if selected_size not in ['12', '16', '24', '32', '40']:
#        return 'Invalid size selected', 400

    uploaded_files = request.files.getlist('images')
    for uploaded_file in uploaded_files:
        if uploaded_file.filename != '':
            # Save uploaded file
            filename = str(uuid.uuid4()) + os.path.splitext(uploaded_file.filename)[1]
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            uploaded_file.save(filepath)

            with Image.open(filepath) as img:
                # Remove background
                img_no_bg = remove(img)

                # Get the bounding box of non-transparent pixels
                alpha = img_no_bg.split()[-1]
                bbox = alpha.getbbox()
                if bbox:
                    img_cropped = img_no_bg.crop(bbox)
                else:
                    img_cropped = img_no_bg  # In case bbox is None

                # Define target bottle heights based on size
                target_bottle_heights = {
                    '49': 1040,
                    '40': 1040,
                    '35': 1020,
                    '32': 1020,
                    '30': 1020,
                    '26': 990,
                    '25': 990,
                    '22': 950,
                    '24': 990,
                    '20': 940,
                    '16': 890,
                    '15': 840,
                    '14': 800,
                    '12': 760,
                    '10': 710,
                    '8': 850,
                    '7': 690,
                    '64': 1040
                    }

                target_height = target_bottle_heights[selected_size]

                # Compute scaling factor
                scaling_factor = target_height / img_cropped.height

                # Resize the cropped image
                new_width = int(img_cropped.width * scaling_factor)
                new_height = int(img_cropped.height * scaling_factor)
                img_resized = img_cropped.resize((new_width, new_height), resample=Image.LANCZOS)

                # Create a new canvas
                canvas_size = (1080, 1080)
                new_canvas = Image.new('RGBA', canvas_size, (0, 0, 0, 0))

                # Compute offsets
                x_offset = (canvas_size[0] - img_resized.width) // 2
                bottom_padding = 20  # Fixed bottom padding
                y_offset = canvas_size[1] - bottom_padding - img_resized.height

                # Paste the resized image onto the canvas
                new_canvas.paste(img_resized, (x_offset, y_offset))

                # Save the processed image
                processed_filename = os.path.splitext(filename)[0] + '.webp'
                processed_filepath = os.path.join(batch_folder, processed_filename)
                new_canvas.save(processed_filepath, 'WEBP')

    # Redirect to index with batch_id and size
    return redirect(url_for('index', batch_id=batch_id, size=selected_size))

@app.route('/download_all', methods=['POST'])
def download_all():
    batch_id = request.form.get('batch_id')
    size = request.form.get('size')  # Get the size
    image_names = request.form.getlist('image_names[]')
    original_filenames = request.form.getlist('original_filenames[]')
    
    batch_folder = os.path.join(PROCESSED_FOLDER, batch_id)
    if not os.path.exists(batch_folder):
        return 'Batch not found', 404

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for i, original_filename in enumerate(original_filenames):
            if i < len(image_names):
                # Get original file path
                original_path = os.path.join(batch_folder, original_filename)
                
                if os.path.exists(original_path):
                    # Open the processed image
                    with Image.open(original_path) as img:
                        # Copy the image
                        img_copy = img.copy()
                        
                        # Construct the new filename using the size
                        new_filename = f"{image_names[i].replace(' ', '')}-{size}-1.webp"
                        
                        # Save the image to a BytesIO object
                        img_buffer = io.BytesIO()
                        img_copy.save(img_buffer, format='WEBP')
                        img_buffer.seek(0)
                        
                        # Add the image to the zip file
                        zip_file.writestr(new_filename, img_buffer.getvalue())

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name='processed_images.zip'
    )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
