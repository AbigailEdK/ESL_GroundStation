from flask import Blueprint, request


def create_control_blueprint(control_service):
    blueprint = Blueprint('control', __name__, url_prefix='/api/control')

    @blueprint.route('/state')
    def state():
        return control_service.state()

    @blueprint.route('/connect-uart', methods=['POST'])
    def connect_uart():
        return control_service.connect_uart()

    @blueprint.route('/disconnect-uart', methods=['POST'])
    def disconnect_uart():
        return control_service.disconnect_uart()

    @blueprint.route('/external-target', methods=['POST'])
    def external_target():
        return control_service.send_external_target(request.json or {})

    @blueprint.route('/load-tle', methods=['POST'])
    def load_tle():
        return control_service.load_tle(request.json or {})

    @blueprint.route('/start-standalone', methods=['POST'])
    def start_standalone():
        return control_service.start_standalone(request.json or {})

    @blueprint.route('/stop-standalone', methods=['POST'])
    def stop_standalone():
        return control_service.stop_standalone()

    return blueprint
