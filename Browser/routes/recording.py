from flask import Blueprint, request


def create_recording_blueprint(recording_service):
    blueprint = Blueprint('recording', __name__, url_prefix='/api')

    @blueprint.route('/start-recording', methods=['POST'])
    def start_recording():
        return recording_service.start_recording(request.json or {})

    @blueprint.route('/stop-recording', methods=['POST'])
    def stop_recording():
        return recording_service.stop_recording(request.json or {})

    @blueprint.route('/recordings')
    def get_recordings():
        return recording_service.list_recordings()

    @blueprint.route('/recording-status')
    def recording_status():
        return recording_service.recording_status()

    @blueprint.route('/delete-recording', methods=['POST'])
    def delete_recording():
        return recording_service.delete_recording(request.json or {})

    @blueprint.route('/download-recording/<filename>')
    def download_recording(filename):
        return recording_service.download_recording(filename)

    return blueprint
