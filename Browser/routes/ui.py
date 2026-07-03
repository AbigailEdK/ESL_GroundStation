from flask import Blueprint, render_template


def create_ui_blueprint():
    blueprint = Blueprint('ui', __name__)

    @blueprint.route('/')
    def index():
        return render_template('dashboard.html')

    @blueprint.route('/settings')
    def settings():
        return render_template('settings.html')

    @blueprint.route('/logs')
    def logs():
        return render_template('logs.html')

    @blueprint.route('/tracking')
    def tracking():
        return render_template('tracking.html')

    @blueprint.route('/cameras')
    def cameras():
        return render_template('cameras.html')

    @blueprint.route('/gallery')
    def gallery():
        return render_template('gallery.html')

    return blueprint
