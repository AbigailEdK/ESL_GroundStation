from flask import Blueprint, request


def create_snapshots_blueprint(snapshot_service):
    blueprint = Blueprint('snapshots', __name__, url_prefix='/api')

    @blueprint.route('/save-snapshot', methods=['POST'])
    def save_snapshot():
        return snapshot_service.save_snapshot(request.json or {})

    @blueprint.route('/snapshots')
    def get_snapshots():
        return snapshot_service.list_snapshots()

    @blueprint.route('/snapshot-file/<filename>')
    def snapshot_file(filename):
        return snapshot_service.snapshot_file(filename)

    @blueprint.route('/delete-snapshot', methods=['POST'])
    def delete_snapshot():
        return snapshot_service.delete_snapshot(request.json or {})

    @blueprint.route('/download-snapshot/<filename>')
    def download_snapshot(filename):
        return snapshot_service.download_snapshot(filename)

    return blueprint
