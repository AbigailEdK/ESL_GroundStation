from flask import Blueprint, request


def create_snapshots_blueprint(snapshot_service):
    #  % ------------------------------------------------------------
    #  % Inputs: Parameters: snapshot_service.
    #  % Side-effects: Executes module logic and may read or mutate internal state.
    #  % Returns: A configured Flask Blueprint object.
    #  % ------------------------------------------------------------
    blueprint = Blueprint('snapshots', __name__, url_prefix='/api')

    @blueprint.route('/save-snapshot', methods=['POST'])
    def save_snapshot():
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: May change device/file state and update in-memory tracking fields.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
        return snapshot_service.save_snapshot(request.json or {})

    @blueprint.route('/snapshots')
    def get_snapshots():
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: Reads current state and may compute derived values for reporting.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
        return snapshot_service.list_snapshots()

    @blueprint.route('/snapshot-file/<filename>')
    def snapshot_file(filename):
        #  % ------------------------------------------------------------
        #  % Inputs: Parameters: filename.
        #  % Side-effects: Executes module logic and may read or mutate internal state.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
        return snapshot_service.snapshot_file(filename)

    @blueprint.route('/delete-snapshot', methods=['POST'])
    def delete_snapshot():
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: May change device/file state and update in-memory tracking fields.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
        return snapshot_service.delete_snapshot(request.json or {})

    @blueprint.route('/download-snapshot/<filename>')
    def download_snapshot(filename):
        #  % ------------------------------------------------------------
        #  % Inputs: Parameters: filename.
        #  % Side-effects: May change device/file state and update in-memory tracking fields.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
        return snapshot_service.download_snapshot(filename)

    return blueprint
