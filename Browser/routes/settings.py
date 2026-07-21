from flask import Blueprint, request


def create_settings_blueprint(settings_service):
    #  % ------------------------------------------------------------
    #  % Inputs: SettingsService instance bound to integration settings storage.
    #  % Side-effects: Defines API routes for reading and persisting settings form data.
    #  % Returns: A configured Flask Blueprint object.
    #  % ------------------------------------------------------------
    blueprint = Blueprint('settings_api', __name__, url_prefix='/api/settings')

    @blueprint.route('')
    def get_settings():
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters.
        #  % Side-effects: Reads integration settings JSON from disk.
        #  % Returns: JSON payload representing current settings.
        #  % ------------------------------------------------------------
        return settings_service.get_settings()

    @blueprint.route('/general', methods=['POST'])
    def update_general():
        #  % ------------------------------------------------------------
        #  % Inputs: JSON payload for general settings fields.
        #  % Side-effects: Persists general settings in integration settings JSON.
        #  % Returns: Success payload containing updated settings snapshot.
        #  % ------------------------------------------------------------
        return settings_service.update_general(request.json or {})

    @blueprint.route('/receiver', methods=['POST'])
    def update_receiver():
        #  % ------------------------------------------------------------
        #  % Inputs: JSON payload for receiver settings fields.
        #  % Side-effects: Persists receiver settings in integration settings JSON.
        #  % Returns: Success payload containing updated settings snapshot.
        #  % ------------------------------------------------------------
        return settings_service.update_receiver(request.json or {})

    @blueprint.route('/transmitter', methods=['POST'])
    def update_transmitter():
        #  % ------------------------------------------------------------
        #  % Inputs: JSON payload for transmitter settings fields.
        #  % Side-effects: Persists transmitter settings in integration settings JSON.
        #  % Returns: Success payload containing updated settings snapshot.
        #  % ------------------------------------------------------------
        return settings_service.update_transmitter(request.json or {})

    return blueprint
