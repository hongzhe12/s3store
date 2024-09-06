import io
import tempfile
from flask import Flask, request, render_template, redirect, url_for, flash, send_file
from s3_client import S3Client  # 假设S3Client类存放在s3_client.py中
import os
from config import access_key, secret_key, bucket_name

app = Flask(__name__)
app.secret_key = 'ChSlckeJYMv4kOT'

# 初始化 S3Client
s3_client = S3Client(
    access_key=access_key,
    secret_key=secret_key,
    bucket_name=bucket_name,
    end_point=None
)


# 首页 - 显示文件列表
@app.route('/')
def index():
    files = s3_client.list_files()
    return render_template('index.html', files=files)


# 上传文件
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)

    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)

    if file:
        # 使用 tempfile.gettempdir() 获取当前系统的临时目录，兼容 Windows 和 Linux
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, file.filename)

        # 保存文件到本地临时目录
        file.save(file_path)

        try:
            # 上传文件到 S3
            s3_client.put_file(file.filename, file_path)
            flash(f"File {file.filename} uploaded successfully to S3!")
        except Exception as e:
            flash(f"Failed to upload file to S3: {str(e)}")
        finally:
            # 删除本地临时文件
            if os.path.exists(file_path):
                os.remove(file_path)

        return redirect('/')


# 删除文件
@app.route('/delete/<filename>')
def delete_file(filename):
    try:
        s3_client.delete_file(filename)
        flash(f"File {filename} deleted successfully from S3")
    except Exception as e:
        flash(f"Failed to delete file: {str(e)}")
    return redirect(url_for('index'))


# 下载文件
@app.route('/download/<filename>')
def download_file(filename):
    try:
        # 从 S3 下载文件到内存
        file_obj = s3_client.get_file(filename)
        file_content = file_obj['Body'].read()

        # 创建一个字节流对象
        file_stream = io.BytesIO(file_content)

        # 发送文件到用户
        return send_file(
            file_stream,
            as_attachment=True,
            download_name=filename  # 使用 download_name 而不是 attachment_filename
        )
    except Exception as e:
        flash(f"Failed to download file: {str(e)}")
        return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)
