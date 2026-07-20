from flask import Blueprint, request


def create_tle_library_blueprint(tle_library_service):
    #  % ------------------------------------------------------------
    #  % Inputs: TLE library service instance with persistence and public search behavior.
    #  % Side-effects: Defines API routes for saving, loading, deleting, and searching TLE entries.
    #  % Returns: A configured Flask Blueprint object.
    #  % ------------------------------------------------------------
    blueprint = Blueprint('tle_library', __name__, url_prefix='/api/tle-library')

    @blueprint.route('/saved')
    def saved():
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses service state and persisted TLE library file.
        #  % Side-effects: Reads saved TLE entries for UI consumption.
        #  % Returns: JSON list of saved satellites with age metadata.
        #  % ------------------------------------------------------------
        return tle_library_service.list_saved()

    @blueprint.route('/save', methods=['POST'])
    def save():
        #  % ------------------------------------------------------------
        #  % Inputs: JSON payload with satellite name, TLE lines, and optional source/mark_loaded fields.
        #  % Side-effects: Persists or updates a saved TLE entry in storage.
        #  % Returns: Success or error JSON describing the save result.
        #  % ------------------------------------------------------------
        return tle_library_service.save_tle(request.json or {})

    @blueprint.route('/delete', methods=['POST'])
    def delete():
        #  % ------------------------------------------------------------
        #  % Inputs: JSON payload with saved entry id.
        #  % Side-effects: Removes a saved TLE entry from persistent storage.
        #  % Returns: Success or error JSON describing the delete result.
        #  % ------------------------------------------------------------
        return tle_library_service.delete_saved(request.json or {})

    @blueprint.route('/load-saved', methods=['POST'])
    def load_saved():
        #  % ------------------------------------------------------------
        #  % Inputs: JSON payload with saved entry id.
        #  % Side-effects: Loads the selected TLE into the controller and updates its last-loaded timestamp.
        #  % Returns: Success or error JSON describing the load result.
        #  % ------------------------------------------------------------
        return tle_library_service.load_saved(request.json or {})

    @blueprint.route('/search-public')
    def search_public():
        #  % ------------------------------------------------------------
        #  % Inputs: Query string parameter q containing public satellite search text.
        #  % Side-effects: Proxies a public TLE search request and parses the results.
        #  % Returns: JSON search results or an error payload.
        #  % ------------------------------------------------------------
        return tle_library_service.search_public(request.args.get('q', ''))

    return blueprint