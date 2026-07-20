from flask import jsonify


class ControlService:
    #  % ------------------------------------------------------------
    #  % Inputs: Class constructor arguments at instantiation and module dependencies used by its methods.
    #  % Side-effects: Defines state and behavior used by instances across the module.
    #  % Returns: A class definition used to construct and manage instances.
    #  % ------------------------------------------------------------
    def __init__(self, controller):
        #  % ------------------------------------------------------------
        #  % Inputs: Parameters: controller.
        #  % Side-effects: Executes module logic and may read or mutate internal state.
        #  % Returns: An internal helper result consumed by the caller.
        #  % ------------------------------------------------------------
        self.controller = controller

    def _require_controller(self):
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: Executes module logic and may read or mutate internal state.
        #  % Returns: An internal helper result consumed by the caller.
        #  % ------------------------------------------------------------
        if self.controller is None:
            return jsonify({'status': 'error', 'message': 'Controller unavailable'}), 503
        return None

    def state(self):
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: Reads current state and may compute derived values for reporting.
        #  % Returns: A state/report payload for API or internal callers.
        #  % ------------------------------------------------------------
        unavailable = self._require_controller()
        if unavailable is not None:
            return unavailable
        return jsonify(self.controller.get_state())

    def connect_uart(self):
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: May start threads/processes, open resources, and update shared runtime state.
        #  % Returns: A success/failure status with a descriptive message.
        #  % ------------------------------------------------------------
        unavailable = self._require_controller()
        if unavailable is not None:
            return unavailable
        ok, message = self.controller.connect_uart()
        status_code = 200 if ok else 500
        return jsonify({'status': 'ok' if ok else 'error', 'message': message}), status_code

    def disconnect_uart(self):
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: May start threads/processes, open resources, and update shared runtime state.
        #  % Returns: A success/failure status with a descriptive message.
        #  % ------------------------------------------------------------
        unavailable = self._require_controller()
        if unavailable is not None:
            return unavailable
        ok, message = self.controller.disconnect_uart()
        status_code = 200 if ok else 500
        return jsonify({'status': 'ok' if ok else 'error', 'message': message}), status_code

    def send_external_target(self, data):
        #  % ------------------------------------------------------------
        #  % Inputs: Parameters: data.
        #  % Side-effects: May change device/file state and update in-memory tracking fields.
        #  % Returns: A success/failure status with a descriptive message.
        #  % ------------------------------------------------------------
        unavailable = self._require_controller()
        if unavailable is not None:
            return unavailable

        azimuth = data.get('azimuth')
        elevation = data.get('elevation')
        if azimuth is None or elevation is None:
            return (
                jsonify({'status': 'error', 'message': 'azimuth and elevation are required'}),
                400,
            )

        try:
            azimuth = float(azimuth)
            elevation = float(elevation)
        except (TypeError, ValueError):
            return jsonify({'status': 'error', 'message': 'azimuth/elevation must be numeric'}), 400

        ok, message = self.controller.send_external_target(azimuth, elevation)
        status_code = 200 if ok else 500
        return jsonify({'status': 'ok' if ok else 'error', 'message': message}), status_code

    def load_tle(self, data):
        #  % ------------------------------------------------------------
        #  % Inputs: Parameters: data.
        #  % Side-effects: May change device/file state and update in-memory tracking fields.
        #  % Returns: A success/failure status with a descriptive message.
        #  % ------------------------------------------------------------
        unavailable = self._require_controller()
        if unavailable is not None:
            return unavailable

        name = data.get('name')
        line1 = data.get('line1')
        line2 = data.get('line2')
        if not name or not line1 or not line2:
            return jsonify({'status': 'error', 'message': 'name, line1, and line2 are required'}), 400

        ok, message = self.controller.load_tle(name, line1, line2)
        status_code = 200 if ok else 400
        return jsonify({'status': 'ok' if ok else 'error', 'message': message}), status_code

    def start_standalone(self, data):
        #  % ------------------------------------------------------------
        #  % Inputs: Parameters: data.
        #  % Side-effects: May start threads/processes, open resources, and update shared runtime state.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
        unavailable = self._require_controller()
        if unavailable is not None:
            return unavailable

        refresh_rate_hz = data.get('refresh_rate_hz')
        ok, message = self.controller.start_standalone_tracking(refresh_rate_hz)
        status_code = 200 if ok else 400
        return jsonify({'status': 'ok' if ok else 'error', 'message': message}), status_code

    def stop_standalone(self):
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: May stop active work, release resources, and update shared runtime state.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
        unavailable = self._require_controller()
        if unavailable is not None:
            return unavailable

        ok, message = self.controller.stop_standalone_tracking()
        status_code = 200 if ok else 500
        return jsonify({'status': 'ok' if ok else 'error', 'message': message}), status_code
