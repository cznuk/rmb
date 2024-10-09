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

# Configure the app to use the PORT environment variable
port = int(os.environ.get('PORT', 10000))

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# Add this route to serve files from the PROCESSED_FOLDER
@app.route('/static/processed/<path:filename>')
def serve_processed(filename):
    return send_from_directory(PROCESSED_FOLDER, filename)

@app.route('/', methods=['GET'])
def index():
    batch_id = request.args.get('batch_id')
    images = []
    if batch_id:
        batch_folder = os.path.join(PROCESSED_FOLDER, batch_id)
        if os.path.exists(batch_folder):
            images = os.listdir(batch_folder)

    return render_template('index.html', images=images, batch_id=batch_id)

@app.route('/upload', methods=['POST'])
def upload():
    batch_id = str(uuid.uuid4())
    batch_folder = os.path.join(PROCESSED_FOLDER, batch_id)
    os.makedirs(batch_folder, exist_ok=True)

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

                # Resize the cropped image to fill the square canvas
                max_dim = max(img_cropped.size)
                new_img = Image.new('RGBA', (max_dim, max_dim), (0, 0, 0, 0))

                # Resize the image to fit the canvas while maintaining aspect ratio
                img_resized = img_cropped.copy()
                img_resized.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

                # Center the resized image
                offset = (
                    (max_dim - img_resized.width) // 2,
                    (max_dim - img_resized.height) // 2
                )
                new_img.paste(img_resized, offset)

                # Convert to .webp
                processed_filename = os.path.splitext(filename)[0] + '.webp'
                processed_filepath = os.path.join(batch_folder, processed_filename)
                new_img.save(processed_filepath, 'WEBP')

    return redirect(url_for('index', batch_id=batch_id))

@app.route('/download_all', methods=['POST'])
def download_all():
    batch_id = request.form.get('batch_id')
    image_names = request.form.getlist('image_names[]')
    image_sizes = request.form.getlist('image_sizes[]')
    original_filenames = request.form.getlist('original_filenames[]')
    
    batch_folder = os.path.join(PROCESSED_FOLDER, batch_id)
    if not os.path.exists(batch_folder):
        return 'Batch not found', 404

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for i, original_filename in enumerate(original_filenames):
            if i < len(image_names) and i < len(image_sizes):
                # Get original file path
                original_path = os.path.join(batch_folder, original_filename)
                
                if os.path.exists(original_path):
                    # Open the original image
                    with Image.open(original_path) as img:
                        # Copy the original image without resizing
                        img_copy = img.copy()
                        
                        # Use the size in the filename only
                        size = image_sizes[i]
                        new_filename = f"{image_names[i].replace(' ', '')}-{size}-{1}.webp"
                        
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