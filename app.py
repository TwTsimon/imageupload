from flask import Flask, request, jsonify, send_from_directory, render_template, make_response
from werkzeug.utils import secure_filename
import os
import json
from PIL import Image
import io
import socket
import zipfile
import io

app = Flask(__name__)

# 定义一个获取内网IP地址的函数
def get_inner_ip():
    hostname = socket.gethostname()
    ip_info = socket.getaddrinfo(hostname, None)
    for ip in ip_info:
        ip_address = ip[4][0]
        if ip_address.startswith("192.168.1"):
            return ip_address
    return "No IP address found starting with 192.168.1"

# 存储图片信息的JSON文件
IMAGES_JSON = 'images_info.json'
# 初始化图片信息列表
if not os.path.exists(IMAGES_JSON):
    with open(IMAGES_JSON, 'w') as f:
        json.dump([], f)

# 设置图片上传目录和缩略图目录
UPLOAD_FOLDER = 'uploads'
PREVIEW_FOLDER = 'preview'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(PREVIEW_FOLDER):
    os.makedirs(PREVIEW_FOLDER)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

def create_thumbnail(input_stream, filename):
    "创建缩略图"
    img = Image.open(input_stream)
    img.thumbnail((128, 128))  # 移除了 Image.ANTIALIAS
    thumbnail_path = os.path.join(PREVIEW_FOLDER, filename)
    img.save(thumbnail_path, format='JPEG')
    return thumbnail_path

def update_images_info(file_info):
    try:
        with open(IMAGES_JSON, 'r+') as f:
            images_info = json.load(f)
            images_info.append(file_info)
            f.seek(0)
            json.dump(images_info, f, indent=4)
            f.truncate()
            return {'message': 'File uploaded successfully'}
    except (IOError, json.JSONDecodeError) as e:
        return {'message': 'Failed to update images info', 'error': str(e)}
    
@app.route('/')
def index():
    inner_ip = get_inner_ip()
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_image():
    if 'file' not in request.files:
        return jsonify({'message': 'No file part in the request'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'message': 'No selected file'}), 400
    if file and allowed_file(file.filename):
        if 'image' not in file.content_type.lower().split('/'):
            return jsonify({'message': 'File type is not supported'}), 400
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        
        # 创建缩略图
        thumbnail_path = create_thumbnail(file, filename)
        
        # 更新图片信息列表
        with open(IMAGES_JSON, 'r+') as f:
            images_info = json.load(f)
            images_info.append({'filename': filename, 'thumbnail': os.path.basename(thumbnail_path)})
            f.seek(0)
            json.dump(images_info, f, indent=4)
        
        return jsonify({'message': 'File uploaded successfully'})
    else:
        return jsonify({'message': 'File upload failed'}), 500

@app.route('/preview/<filename>')
def preview_image(filename):
    thumbnail_path = os.path.join(PREVIEW_FOLDER, filename)
    if not os.path.exists(thumbnail_path):
        return jsonify({'message': 'Thumbnail not found'}), 404
    return send_from_directory(PREVIEW_FOLDER, filename, as_attachment=False)

# 获取已上传图片列表的路由
@app.route('/list')
def list_images():
    with open(IMAGES_JSON, 'r') as f:
        images_info = json.load(f)
    files = [info['filename'] for info in images_info]
    return jsonify({'files': files})

# 下载多张图片的路由
@app.route('/download_multi', methods=['POST'])
def download_multiple_images():
    # 确保请求的内容类型是JSON
    if not request.is_json:
        return jsonify({'message': 'Missing JSON in request'}), 400
    selected_images = request.get_json().get('images', [])
    if not selected_images:
        return jsonify({'message': 'No images selected for download'}), 400
    
    # 检查所选图片是否存在
    missing_files = [img for img in selected_images if not os.path.exists(os.path.join(UPLOAD_FOLDER, img))]
    if missing_files:
        return jsonify({'message': 'Files do not exist: ' + ', '.join(missing_files)}), 404
    
    # 创建一个内存中的zip文件
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for image in selected_images:
            zip_file.write(os.path.join(UPLOAD_FOLDER, image), image)
    
    # 准备HTTP响应
    zip_buffer.seek(0)
    response = make_response(zip_buffer.read())
    response.headers['Content-Type'] = 'application/zip'
    response.headers['Content-Disposition'] = 'attachment; filename="selected_images.zip"'
    return response

@app.route('/download_single', methods=['POST'])
def download_single_image():
    # 确保请求的内容类型是JSON
    if not request.is_json:
        return jsonify({'message': 'Missing JSON in request'}), 400
    filename = request.get_json().get('filename')
    if not filename:
        return jsonify({'message': 'No filename provided'}), 400
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(file_path):
        return jsonify({'message': 'File not found'}), 404
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

if __name__ == '__main__':
    # 检查内网IP
    inner_ip = get_inner_ip()
    if inner_ip:
        # 启动服务，监听5000端口
        app.run(host=inner_ip, port=5000)
    else:
        print("Error: Could not find a suitable IP address to start the server.")
