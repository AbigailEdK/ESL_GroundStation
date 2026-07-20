from flask import Blueprint, request


def create_control_blueprint(control_service):
    #  % ------------------------------------------------------------
    #  % Inputs: Parameters: control_service.
    #  % Side-effects: Executes module logic and may read or mutate internal state.
    #  % Returns: A configured Flask Blueprint object.
    #  % ------------------------------------------------------------
    blueprint = Blueprint('control', __name__, url_prefix='/api/control')

    @blueprint.route('/state')
    def state():
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: Reads current state and may compute derived values for reporting.
        #  % Returns: A state/report payload for API or internal callers.
        #  % ------------------------------------------------------------
        return control_service.state()

    @blueprint.route('/connect-uart', methods=['POST'])
    def connect_uart():
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: May start threads/processes, open resources, and update shared runtime state.
        #  % Returns: A success/failure status with a descriptive message.
        #  % ------------------------------------------------------------
        return control_service.connect_uart()

    @blueprint.route('/disconnect-uart', methods=['POST'])
    def disconnect_uart():
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: May start threads/processes, open resources, and update shared runtime state.
        #  % Returns: A success/failure status with a descriptive message.
        #  % ------------------------------------------------------------
        return control_service.disconnect_uart()

    @blueprint.route('/external-target', methods=['POST'])
    def external_target():
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: Reads current state and may compute derived values for reporting.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
        return control_service.send_external_target(request.json or {})

    @blueprint.route('/load-tle', methods=['POST'])
    def load_tle():
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: May change device/file state and update in-memory tracking fields.
        #  % Returns: A success/failure status with a descriptive message.
        #  % ------------------------------------------------------------
        return control_service.load_tle(request.json or {})

    @blueprint.route('/start-standalone', methods=['POST'])
    def start_standalone():
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: May start threads/processes, open resources, and update shared runtime state.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
        return control_service.start_standalone(request.json or {})

    @blueprint.route('/stop-standalone', methods=['POST'])
    def stop_standalone():
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: May stop active work, release resources, and update shared runtime state.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
        return control_service.stop_standalone()

    return blueprint
