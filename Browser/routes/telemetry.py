from flask import Blueprint


def create_telemetry_blueprint(telemetry_service):
    blueprint = Blueprint('telemetry', __name__, url_prefix='/api')

    @blueprint.route('/system-info')
    def system_info():
        return telemetry_service.system_info()

    @blueprint.route('/satellite-status')
    def satellite_status():
        return telemetry_service.satellite_status()

    @blueprint.route('/upcoming-passes')
    def upcoming_passes():
        return telemetry_service.upcoming_passes()

    @blueprint.route('/receiver-config')
    def receiver_config():
        return telemetry_service.receiver_config()

    @blueprint.route('/transmitter-config')
    def transmitter_config():
        return telemetry_service.transmitter_config()

    @blueprint.route('/telemetry-data')
    def telemetry_data():
        return telemetry_service.telemetry_data()

    @blueprint.route('/system-health')
    def system_health():
        return telemetry_service.system_health()

    return blueprint
