import os
import subprocess
from datetime import datetime

from flask import jsonify, send_file


class RecordingService:
    def __init__(self, recordings_dir):
        self.recordings_dir = recordings_dir
        os.makedirs(self.recordings_dir, exist_ok=True)
        self.recording_processes = {}

    def _safe_path(self, filename):
        filepath = os.path.join(self.recordings_dir, filename)
        if not os.path.abspath(filepath).startswith(os.path.abspath(self.recordings_dir)):
            return None
        return filepath

    def start_recording(self, data):
        """Start recording from a camera."""
        camera_url = data.get('url')
        camera_name = data.get('name', 'camera')
        camera_id = data.get('id')
        camera_type = data.get('type', 'mjpeg')

        if (
            camera_id in self.recording_processes
            and self.recording_processes[camera_id].poll() is None
        ):
            return jsonify({'status': 'error', 'message': 'Already recording'}), 400

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(self.recordings_dir, f'{camera_name}_{timestamp}.mp4')

        try:
            if camera_type == 'mjpeg':
                cmd = [
                    'ffmpeg',
                    '-rtsp_transport',
                    'tcp',
                    '-i',
                    camera_url,
                    '-c:v',
                    'libx264',
                    '-preset',
                    'veryfast',
                    '-crf',
                    '28',
                    '-c:a',
                    'aac',
                    '-b:a',
                    '128k',
                    output_file,
                ]
            elif camera_type == 'rtsp':
                cmd = [
                    'ffmpeg',
                    '-rtsp_transport',
                    'tcp',
                    '-i',
                    camera_url,
                    '-c:v',
                    'copy',
                    '-c:a',
                    'copy',
                    output_file,
                ]
            else:
                cmd = [
                    'ffmpeg',
                    '-i',
                    camera_url,
                    '-c:v',
                    'libx264',
                    '-preset',
                    'veryfast',
                    '-crf',
                    '28',
                    output_file,
                ]

            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.recording_processes[camera_id] = process

            return jsonify(
                {
                    'status': 'recording',
                    'camera_id': camera_id,
                    'output_file': output_file,
                    'started_at': datetime.now().isoformat(),
                }
            )
        except Exception as exc:
            return jsonify({'status': 'error', 'message': str(exc)}), 500

    def stop_recording(self, data):
        """Stop recording from a camera."""
        camera_id = data.get('id')

        if camera_id not in self.recording_processes:
            return jsonify({'status': 'error', 'message': 'Not recording'}), 400

        process = self.recording_processes[camera_id]
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()

        del self.recording_processes[camera_id]

        return jsonify(
            {
                'status': 'stopped',
                'camera_id': camera_id,
                'stopped_at': datetime.now().isoformat(),
            }
        )

    def list_recordings(self):
        """List all recordings."""
        recordings = []
        try:
            for filename in os.listdir(self.recordings_dir):
                if filename.endswith('.mp4'):
                    filepath = os.path.join(self.recordings_dir, filename)
                    size = os.path.getsize(filepath)
                    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                    recordings.append(
                        {
                            'filename': filename,
                            'size': size,
                            'size_mb': round(size / (1024 * 1024), 2),
                            'created': mtime.isoformat(),
                            'path': filepath,
                        }
                    )
        except Exception as exc:
            return jsonify({'status': 'error', 'message': str(exc)}), 500

        recordings.sort(key=lambda item: item['created'], reverse=True)
        return jsonify(recordings)

    def recording_status(self):
        """Get status of all recordings."""
        status = {}
        for camera_id, process in self.recording_processes.items():
            is_running = process.poll() is None
            status[str(camera_id)] = {
                'recording': is_running,
                'started_at': datetime.now().isoformat() if is_running else None,
            }
        return jsonify(status)

    def delete_recording(self, data):
        """Delete a recording file."""
        filename = data.get('filename')
        filepath = self._safe_path(filename)

        if filepath is None:
            return jsonify({'status': 'error', 'message': 'Invalid file path'}), 400

        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                return jsonify({'status': 'deleted', 'filename': filename})
            return jsonify({'status': 'error', 'message': 'File not found'}), 404
        except Exception as exc:
            return jsonify({'status': 'error', 'message': str(exc)}), 500

    def download_recording(self, filename):
        """Download a recording file."""
        filepath = self._safe_path(filename)

        if filepath is None:
            return jsonify({'status': 'error', 'message': 'Invalid file path'}), 400

        if os.path.exists(filepath):
            return send_file(filepath, as_attachment=True, download_name=filename)
        return jsonify({'status': 'error', 'message': 'File not found'}), 404
