from flask import Blueprint


def create_telemetry_blueprint(telemetry_service):
    #  % ------------------------------------------------------------
    #  % Inputs: Parameters: telemetry_service.
    #  % Side-effects: Executes module logic and may read or mutate internal state.
    #  % Returns: A configured Flask Blueprint object.
    #  % ------------------------------------------------------------
    blueprint = Blueprint('telemetry', __name__, url_prefix='/api')

    @blueprint.route('/system-info')
    def system_info():
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: Reads current state and may compute derived values for reporting.
        #  % Returns: A state/report payload for API or internal callers.
        #  % ------------------------------------------------------------
        return telemetry_service.system_info()

    @blueprint.route('/satellite-status')
    def satellite_status():
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: Reads current state and may compute derived values for reporting.
        #  % Returns: A state/report payload for API or internal callers.
        #  % ------------------------------------------------------------
        return telemetry_service.satellite_status()

    @blueprint.route('/upcoming-passes')
    def upcoming_passes():
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: Executes module logic and may read or mutate internal state.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
        return telemetry_service.upcoming_passes()

    @blueprint.route('/next-pass-path')
    def next_pass_path():
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: Executes module logic and may read or mutate internal state.
        #  % Returns: Predicted target path samples for the next pass.
        #  % ------------------------------------------------------------
        return telemetry_service.next_pass_path()

    @blueprint.route('/receiver-config')
    def receiver_config():
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: Reads current state and may compute derived values for reporting.
        #  % Returns: A state/report payload for API or internal callers.
        #  % ------------------------------------------------------------
        return telemetry_service.receiver_config()

    @blueprint.route('/transmitter-config')
    def transmitter_config():
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: Reads current state and may compute derived values for reporting.
        #  % Returns: A state/report payload for API or internal callers.
        #  % ------------------------------------------------------------
        return telemetry_service.transmitter_config()

    @blueprint.route('/telemetry-data')
    def telemetry_data():
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: Executes module logic and may read or mutate internal state.
        #  % Returns: A state/report payload for API or internal callers.
        #  % ------------------------------------------------------------
        return telemetry_service.telemetry_data()

    @blueprint.route('/system-health')
    def system_health():
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: Executes module logic and may read or mutate internal state.
        #  % Returns: A state/report payload for API or internal callers.
        #  % ------------------------------------------------------------
        return telemetry_service.system_health()

    return blueprint
