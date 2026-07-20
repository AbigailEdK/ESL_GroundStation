from flask import Blueprint, request


def create_recording_blueprint(recording_service):
    #  % ------------------------------------------------------------
    #  % Inputs: Parameters: recording_service.
    #  % Side-effects: Executes module logic and may read or mutate internal state.
    #  % Returns: A configured Flask Blueprint object.
    #  % ------------------------------------------------------------
    blueprint = Blueprint('recording', __name__, url_prefix='/api')

    @blueprint.route('/start-recording', methods=['POST'])
    def start_recording():
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: May start threads/processes, open resources, and update shared runtime state.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
        return recording_service.start_recording(request.json or {})

    @blueprint.route('/stop-recording', methods=['POST'])
    def stop_recording():
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: May stop active work, release resources, and update shared runtime state.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
        return recording_service.stop_recording(request.json or {})

    @blueprint.route('/recordings')
    def get_recordings():
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: Reads current state and may compute derived values for reporting.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
        return recording_service.list_recordings()

    @blueprint.route('/recording-status')
    def recording_status():
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: Reads current state and may compute derived values for reporting.
        #  % Returns: A state/report payload for API or internal callers.
        #  % ------------------------------------------------------------
        return recording_service.recording_status()

    @blueprint.route('/delete-recording', methods=['POST'])
    def delete_recording():
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: May change device/file state and update in-memory tracking fields.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
        return recording_service.delete_recording(request.json or {})

    @blueprint.route('/download-recording/<filename>')
    def download_recording(filename):
        #  % ------------------------------------------------------------
        #  % Inputs: Parameters: filename.
        #  % Side-effects: May change device/file state and update in-memory tracking fields.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
        return recording_service.download_recording(filename)

    return blueprint
