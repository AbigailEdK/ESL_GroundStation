from flask import Blueprint, render_template


def create_ui_blueprint():
    #  % ------------------------------------------------------------
    #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
    #  % Side-effects: Executes module logic and may read or mutate internal state.
    #  % Returns: A configured Flask Blueprint object.
    #  % ------------------------------------------------------------
    blueprint = Blueprint('ui', __name__)

    @blueprint.route('/')
    def index():
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: Executes module logic and may read or mutate internal state.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
        return render_template('dashboard.html')

    @blueprint.route('/settings')
    def settings():
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: Executes module logic and may read or mutate internal state.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
        return render_template('settings.html')

    @blueprint.route('/logs')
    def logs():
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: Executes module logic and may read or mutate internal state.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
        return render_template('logs.html')

    @blueprint.route('/tracking')
    def tracking():
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: Executes module logic and may read or mutate internal state.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
        return render_template('tracking.html')

    @blueprint.route('/cameras')
    def cameras():
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: Executes module logic and may read or mutate internal state.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
        return render_template('cameras.html')

    @blueprint.route('/gallery')
    def gallery():
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: Executes module logic and may read or mutate internal state.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
        return render_template('gallery.html')

    return blueprint
