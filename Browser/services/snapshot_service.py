import os
from datetime import datetime

from flask import jsonify, send_file


class SnapshotService:
    #  % ------------------------------------------------------------
    #  % Inputs: Class constructor arguments at instantiation and module dependencies used by its methods.
    #  % Side-effects: Defines state and behavior used by instances across the module.
    #  % Returns: A class definition used to construct and manage instances.
    #  % ------------------------------------------------------------
    def __init__(self, snapshots_dir):
        #  % ------------------------------------------------------------
        #  % Inputs: Parameters: snapshots_dir.
        #  % Side-effects: Executes module logic and may read or mutate internal state.
        #  % Returns: An internal helper result consumed by the caller.
        #  % ------------------------------------------------------------
        self.snapshots_dir = snapshots_dir
        os.makedirs(self.snapshots_dir, exist_ok=True)

    def _safe_path(self, filename):
        #  % ------------------------------------------------------------
        #  % Inputs: Parameters: filename.
        #  % Side-effects: Executes module logic and may read or mutate internal state.
        #  % Returns: An internal helper result consumed by the caller.
        #  % ------------------------------------------------------------
        filepath = os.path.join(self.snapshots_dir, filename)
        if not os.path.abspath(filepath).startswith(os.path.abspath(self.snapshots_dir)):
            return None
        return filepath

    def save_snapshot(self, data):
        """Save a snapshot from a camera."""
        #  % ------------------------------------------------------------
        #  % Inputs: Parameters: data.
        #  % Side-effects: May change device/file state and update in-memory tracking fields.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
        import requests

        camera_url = data.get('url')
        camera_name = data.get('name', 'camera')

        try:
            response = requests.get(camera_url, timeout=5, stream=False)
            if response.status_code == 200:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f'{camera_name}_{timestamp}.jpg'
                filepath = os.path.join(self.snapshots_dir, filename)

                with open(filepath, 'wb') as file:
                    file.write(response.content)

                return jsonify(
                    {
                        'status': 'saved',
                        'filename': filename,
                        'camera_name': camera_name,
                        'timestamp': datetime.now().isoformat(),
                        'filepath': filepath,
                    }
                )
            return jsonify({'status': 'error', 'message': 'Failed to fetch frame'}), 400
        except Exception as exc:
            return jsonify({'status': 'error', 'message': str(exc)}), 500

    def list_snapshots(self):
        """List all snapshots."""
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: Reads current state and may compute derived values for reporting.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
        snapshots = []
        try:
            for filename in sorted(os.listdir(self.snapshots_dir), reverse=True):
                if filename.endswith(('.jpg', '.jpeg', '.png')):
                    filepath = os.path.join(self.snapshots_dir, filename)
                    size = os.path.getsize(filepath)
                    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))

                    parts = filename.rsplit('_', 2)
                    if len(parts) >= 3:
                        date_str = parts[-2]
                        time_str = (
                            parts[-1]
                            .replace('.jpg', '')
                            .replace('.jpeg', '')
                            .replace('.png', '')
                        )
                        try:
                            snapshot_time = datetime.strptime(
                                f'{date_str}_{time_str}', '%Y%m%d_%H%M%S'
                            )
                        except Exception:
                            snapshot_time = mtime
                    else:
                        snapshot_time = mtime

                    snapshots.append(
                        {
                            'filename': filename,
                            'camera_name': parts[0] if len(parts) > 0 else 'Unknown',
                            'size': size,
                            'size_kb': round(size / 1024, 2),
                            'created': snapshot_time.isoformat(),
                            'created_display': snapshot_time.strftime(
                                '%Y-%m-%d %H:%M:%S'
                            ),
                            'path': f'/api/snapshot-file/{filename}',
                        }
                    )
        except Exception as exc:
            return jsonify({'status': 'error', 'message': str(exc)}), 500

        return jsonify(snapshots)

    def snapshot_file(self, filename):
        """Serve a snapshot file."""
        #  % ------------------------------------------------------------
        #  % Inputs: Parameters: filename.
        #  % Side-effects: Executes module logic and may read or mutate internal state.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
        filepath = self._safe_path(filename)

        if filepath is None:
            return jsonify({'status': 'error', 'message': 'Invalid file path'}), 400

        if os.path.exists(filepath):
            return send_file(filepath, mimetype='image/jpeg')
        return jsonify({'status': 'error', 'message': 'File not found'}), 404

    def delete_snapshot(self, data):
        """Delete a snapshot file."""
        #  % ------------------------------------------------------------
        #  % Inputs: Parameters: data.
        #  % Side-effects: May change device/file state and update in-memory tracking fields.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
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

    def download_snapshot(self, filename):
        """Download a snapshot file."""
        #  % ------------------------------------------------------------
        #  % Inputs: Parameters: filename.
        #  % Side-effects: May change device/file state and update in-memory tracking fields.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
        filepath = self._safe_path(filename)

        if filepath is None:
            return jsonify({'status': 'error', 'message': 'Invalid file path'}), 400

        if os.path.exists(filepath):
            return send_file(filepath, as_attachment=True, download_name=filename)
        return jsonify({'status': 'error', 'message': 'File not found'}), 404
