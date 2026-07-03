'''
TODO:
    - Hosted locally and available from any machine on the closed network
    - Live monitoring: time, current target AZ/EL, actual AZ/EL reported by STM32, error between them
    - Later: STM32 firmware will be updated to send states and error messages which should also show on the broswer
    - Pass countdown and satellite name display would be useful during tracking operations
    - Ground track map showing satellite position over Earth based on TLE data would be a very cool addition. Leaftlet.js could be used for this map.
    - Basic commanding: selecting a satellite to track, or entering manual AZ/EL targets

N.B! The serial port to STM32 can only be opened by one process, so the web server must absorb the UART handling rather than running alongside other scripts.
'''

from flask import Flask, render_template, jsonify, request
import os
import random
from datetime import datetime, timedelta
import threading
import subprocess
import json

app = Flask(__name__)

# Configure template folder
app.template_folder = os.path.join(os.path.dirname(__file__), 'templates')
app.static_folder = os.path.join(os.path.dirname(__file__), 'static')

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/settings')
def settings():
    return render_template('settings.html')

@app.route('/logs')
def logs():
    return render_template('logs.html')

@app.route('/tracking')
def tracking():
    return render_template('tracking.html')

@app.route('/cameras')
def cameras():
    return render_template('cameras.html')

@app.route('/gallery')
def gallery():
    return render_template('gallery.html')

@app.route('/api/system-info')
def system_info():
    """Return system information as JSON"""
    import psutil
    return jsonify({
        'cpu_percent': psutil.cpu_percent(interval=1),
        'memory_percent': psutil.virtual_memory().percent,
        'disk_percent': psutil.disk_usage('/').percent,
        'temperature': get_cpu_temperature()
    })

@app.route('/api/satellite-status')
def satellite_status():
    """Return current satellite tracking status"""
    return jsonify({
        'satellite_name': 'ISS (ZARYA)',
        'azimuth': round(random.uniform(0, 360), 2),
        'elevation': round(random.uniform(0, 90), 2),
        'signal_strength': round(random.uniform(-120, -50), 1),
        'snr': round(random.uniform(5, 20), 1),
        'frequency': 145.800,
        'data_rate': random.randint(1000, 50000),
        'communication_status': 'Connected',
        'gps_latitude': 40.7128,
        'gps_longitude': -74.0060,
        'gps_altitude': 10.5,
        'time_sync': True
    })

@app.route('/api/upcoming-passes')
def upcoming_passes():
    """Return upcoming satellite passes"""
    passes = []
    for i in range(5):
        rise_time = datetime.now() + timedelta(hours=i*6)
        passes.append({
            'satellite': 'ISS (ZARYA)',
            'rise_time': rise_time.strftime('%Y-%m-%d %H:%M:%S'),
            'max_elevation': round(random.uniform(10, 85), 1),
            'set_time': (rise_time + timedelta(minutes=random.randint(5, 15))).strftime('%Y-%m-%d %H:%M:%S'),
            'duration': random.randint(5, 15)
        })
    return jsonify(passes)

@app.route('/api/receiver-config')
def receiver_config():
    """Return receiver configuration"""
    return jsonify({
        'frequency': 145.800,
        'modulation': 'FM',
        'bandwidth': 25000,
        'squelch': -100,
        'recording_enabled': True,
        'recording_path': '/data/recordings/'
    })

@app.route('/api/transmitter-config')
def transmitter_config():
    """Return transmitter configuration"""
    return jsonify({
        'frequency': 145.200,
        'modulation': 'FM',
        'power_output': 10,
        'bandwidth': 25000,
        'status': 'Standby'
    })

@app.route('/api/telemetry-data')
def telemetry_data():
    """Return recent telemetry data"""
    telemetry = []
    for i in range(10):
        timestamp = datetime.now() - timedelta(minutes=i)
        telemetry.append({
            'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'signal_strength': round(random.uniform(-120, -50), 1),
            'snr': round(random.uniform(5, 20), 1),
            'bit_error_rate': round(random.uniform(0, 0.01), 4),
            'packet_count': random.randint(100, 5000)
        })
    return jsonify(telemetry)

@app.route('/api/system-health')
def system_health():
    """Return detailed system health"""
    return jsonify({
        'receiver_temp': round(random.uniform(35, 65), 1),
        'transmitter_temp': round(random.uniform(30, 60), 1),
        'antenna_temp': round(random.uniform(20, 50), 1),
        'power_consumption': round(random.uniform(50, 200), 1),
        'network_status': 'Online',
        'receiver_status': 'Active',
        'transmitter_status': 'Standby',
        'tracking_status': 'Active'
    })

def get_cpu_temperature():
    """Get Raspberry Pi CPU temperature"""
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp = int(f.read()) / 1000
            return round(temp, 1)
    except:
        return None

# Recording management
RECORDINGS_DIR = os.path.expanduser('~/GSWebUI/recordings')
os.makedirs(RECORDINGS_DIR, exist_ok=True)

recording_processes = {}

@app.route('/api/start-recording', methods=['POST'])
def start_recording():
    """Start recording from a camera"""
    data = request.json
    camera_url = data.get('url')
    camera_name = data.get('name', 'camera')
    camera_id = data.get('id')
    camera_type = data.get('type', 'mjpeg')
    
    if camera_id in recording_processes and recording_processes[camera_id].poll() is None:
        return jsonify({'status': 'error', 'message': 'Already recording'}), 400
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = os.path.join(RECORDINGS_DIR, f'{camera_name}_{timestamp}.mp4')
    
    try:
        if camera_type == 'mjpeg':
            # Record MJPEG stream
            cmd = [
                'ffmpeg',
                '-rtsp_transport', 'tcp',
                '-i', camera_url,
                '-c:v', 'libx264',
                '-preset', 'veryfast',
                '-crf', '28',
                '-c:a', 'aac',
                '-b:a', '128k',
                output_file
            ]
        elif camera_type == 'rtsp':
            # Record RTSP stream
            cmd = [
                'ffmpeg',
                '-rtsp_transport', 'tcp',
                '-i', camera_url,
                '-c:v', 'copy',
                '-c:a', 'copy',
                output_file
            ]
        else:
            cmd = [
                'ffmpeg',
                '-i', camera_url,
                '-c:v', 'libx264',
                '-preset', 'veryfast',
                '-crf', '28',
                output_file
            ]
        
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        recording_processes[camera_id] = process
        
        return jsonify({
            'status': 'recording',
            'camera_id': camera_id,
            'output_file': output_file,
            'started_at': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/stop-recording', methods=['POST'])
def stop_recording():
    """Stop recording from a camera"""
    data = request.json
    camera_id = data.get('id')
    
    if camera_id not in recording_processes:
        return jsonify({'status': 'error', 'message': 'Not recording'}), 400
    
    process = recording_processes[camera_id]
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
    
    del recording_processes[camera_id]
    
    return jsonify({
        'status': 'stopped',
        'camera_id': camera_id,
        'stopped_at': datetime.now().isoformat()
    })

@app.route('/api/recordings')
def get_recordings():
    """List all recordings"""
    recordings = []
    try:
        for filename in os.listdir(RECORDINGS_DIR):
            if filename.endswith('.mp4'):
                filepath = os.path.join(RECORDINGS_DIR, filename)
                size = os.path.getsize(filepath)
                mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                recordings.append({
                    'filename': filename,
                    'size': size,
                    'size_mb': round(size / (1024 * 1024), 2),
                    'created': mtime.isoformat(),
                    'path': filepath
                })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
    # Sort by creation time, newest first
    recordings.sort(key=lambda x: x['created'], reverse=True)
    return jsonify(recordings)

@app.route('/api/recording-status')
def recording_status():
    """Get status of all recordings"""
    status = {}
    for camera_id, process in recording_processes.items():
        is_running = process.poll() is None
        status[str(camera_id)] = {
            'recording': is_running,
            'started_at': datetime.now().isoformat() if is_running else None
        }
    return jsonify(status)

@app.route('/api/delete-recording', methods=['POST'])
def delete_recording():
    """Delete a recording file"""
    data = request.json
    filename = data.get('filename')
    
    filepath = os.path.join(RECORDINGS_DIR, filename)
    
    # Security check - prevent path traversal
    if not os.path.abspath(filepath).startswith(os.path.abspath(RECORDINGS_DIR)):
        return jsonify({'status': 'error', 'message': 'Invalid file path'}), 400
    
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            return jsonify({'status': 'deleted', 'filename': filename})
        else:
            return jsonify({'status': 'error', 'message': 'File not found'}), 404
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/download-recording/<filename>')
def download_recording(filename):
    """Download a recording file"""
    filepath = os.path.join(RECORDINGS_DIR, filename)
    
    # Security check
    if not os.path.abspath(filepath).startswith(os.path.abspath(RECORDINGS_DIR)):
        return jsonify({'status': 'error', 'message': 'Invalid file path'}), 400
    
    if os.path.exists(filepath):
        from flask import send_file
        return send_file(filepath, as_attachment=True, download_name=filename)
    else:
        return jsonify({'status': 'error', 'message': 'File not found'}), 404

# Snapshot management
SNAPSHOTS_DIR = os.path.expanduser('~/GSWebUI/snapshots')
os.makedirs(SNAPSHOTS_DIR, exist_ok=True)

@app.route('/api/save-snapshot', methods=['POST'])
def save_snapshot():
    """Save a snapshot from a camera"""
    import requests
    from PIL import Image
    from io import BytesIO
    
    data = request.json
    camera_url = data.get('url')
    camera_name = data.get('name', 'camera')
    camera_id = data.get('id')
    
    try:
        # For MJPEG streams, we can fetch a frame directly
        response = requests.get(camera_url, timeout=5, stream=False)
        if response.status_code == 200:
            # Save with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'{camera_name}_{timestamp}.jpg'
            filepath = os.path.join(SNAPSHOTS_DIR, filename)
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            return jsonify({
                'status': 'saved',
                'filename': filename,
                'camera_name': camera_name,
                'timestamp': datetime.now().isoformat(),
                'filepath': filepath
            })
        else:
            return jsonify({'status': 'error', 'message': 'Failed to fetch frame'}), 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/snapshots')
def get_snapshots():
    """List all snapshots"""
    snapshots = []
    try:
        for filename in sorted(os.listdir(SNAPSHOTS_DIR), reverse=True):
            if filename.endswith(('.jpg', '.jpeg', '.png')):
                filepath = os.path.join(SNAPSHOTS_DIR, filename)
                size = os.path.getsize(filepath)
                mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                
                # Extract timestamp from filename (format: name_YYYYMMDD_HHMMSS.jpg)
                parts = filename.rsplit('_', 2)
                if len(parts) >= 3:
                    date_str = parts[-2]
                    time_str = parts[-1].replace('.jpg', '').replace('.jpeg', '').replace('.png', '')
                    try:
                        snapshot_time = datetime.strptime(f'{date_str}_{time_str}', '%Y%m%d_%H%M%S')
                    except:
                        snapshot_time = mtime
                else:
                    snapshot_time = mtime
                
                snapshots.append({
                    'filename': filename,
                    'camera_name': parts[0] if len(parts) > 0 else 'Unknown',
                    'size': size,
                    'size_kb': round(size / 1024, 2),
                    'created': snapshot_time.isoformat(),
                    'created_display': snapshot_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'path': f'/api/snapshot-file/{filename}'
                })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
    return jsonify(snapshots)

@app.route('/api/snapshot-file/<filename>')
def snapshot_file(filename):
    """Serve a snapshot file"""
    filepath = os.path.join(SNAPSHOTS_DIR, filename)
    
    # Security check - prevent path traversal
    if not os.path.abspath(filepath).startswith(os.path.abspath(SNAPSHOTS_DIR)):
        return jsonify({'status': 'error', 'message': 'Invalid file path'}), 400
    
    if os.path.exists(filepath):
        from flask import send_file
        return send_file(filepath, mimetype='image/jpeg')
    else:
        return jsonify({'status': 'error', 'message': 'File not found'}), 404

@app.route('/api/delete-snapshot', methods=['POST'])
def delete_snapshot():
    """Delete a snapshot file"""
    data = request.json
    filename = data.get('filename')
    
    filepath = os.path.join(SNAPSHOTS_DIR, filename)
    
    # Security check - prevent path traversal
    if not os.path.abspath(filepath).startswith(os.path.abspath(SNAPSHOTS_DIR)):
        return jsonify({'status': 'error', 'message': 'Invalid file path'}), 400
    
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            return jsonify({'status': 'deleted', 'filename': filename})
        else:
            return jsonify({'status': 'error', 'message': 'File not found'}), 404
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/download-snapshot/<filename>')
def download_snapshot(filename):
    """Download a snapshot file"""
    filepath = os.path.join(SNAPSHOTS_DIR, filename)
    
    # Security check
    if not os.path.abspath(filepath).startswith(os.path.abspath(SNAPSHOTS_DIR)):
        return jsonify({'status': 'error', 'message': 'Invalid file path'}), 400
    
    if os.path.exists(filepath):
        from flask import send_file
        return send_file(filepath, as_attachment=True, download_name=filename)
    else:
        return jsonify({'status': 'error', 'message': 'File not found'}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)