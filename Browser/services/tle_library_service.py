import json
import os
from datetime import datetime, timezone
from urllib import error, parse, request

from flask import jsonify


class TleLibraryService:
    #  % ------------------------------------------------------------
    #  % Inputs: Library file path plus optional controller for loading saved TLEs.
    #  % Side-effects: Persists saved satellites, computes age metadata, and proxies public TLE search results.
    #  % Returns: Service object used by Flask routes for saved/public TLE workflows.
    #  % ------------------------------------------------------------
    def __init__(self, library_path, controller=None):
        self.library_path = os.path.abspath(os.path.expanduser(library_path))
        self.controller = controller
        library_dir = os.path.dirname(self.library_path)
        if library_dir:
            os.makedirs(library_dir, exist_ok=True)
        if not os.path.exists(self.library_path):
            with open(self.library_path, 'w', encoding='utf-8') as file:
                json.dump([], file, indent=2)

    def _read_entries(self):
        try:
            with open(self.library_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _write_entries(self, entries):
        with open(self.library_path, 'w', encoding='utf-8') as file:
            json.dump(entries, file, indent=2)

    @staticmethod
    def _utc_now_iso():
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _parse_iso(value):
        if not value or not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None

    def _age_label(self, value):
        stamp = self._parse_iso(value)
        if stamp is None:
            return 'age unknown'

        delta = datetime.now(timezone.utc) - stamp
        seconds = max(delta.total_seconds(), 0.0)
        if seconds < 60:
            return 'just loaded'
        if seconds < 3600:
            minutes = int(seconds // 60)
            return f'{minutes} min old'
        if seconds < 86400:
            hours = int(seconds // 3600)
            return f'{hours} h old'
        days = int(seconds // 86400)
        return f'{days} d old'

    def _serialize_entry(self, entry):
        last_loaded_utc = entry.get('last_loaded_utc')
        saved_at_utc = entry.get('saved_at_utc')
        age_reference_utc = last_loaded_utc or saved_at_utc
        payload = dict(entry)
        payload['age_reference_utc'] = age_reference_utc
        payload['age_label'] = self._age_label(age_reference_utc)
        payload['source'] = entry.get('source') or 'manual'
        return payload

    @staticmethod
    def _match_entry(entry, payload):
        return (
            entry.get('name') == payload.get('name')
            and entry.get('line1') == payload.get('line1')
            and entry.get('line2') == payload.get('line2')
        )

    def list_saved(self):
        entries = [self._serialize_entry(entry) for entry in self._read_entries()]
        entries.sort(
            key=lambda entry: entry.get('age_reference_utc') or entry.get('saved_at_utc') or '',
            reverse=True,
        )
        return jsonify(entries)

    def save_tle(self, data):
        name = (data.get('name') or '').strip()
        line1 = (data.get('line1') or '').strip()
        line2 = (data.get('line2') or '').strip()
        source = (data.get('source') or 'manual').strip()
        mark_loaded = bool(data.get('mark_loaded', False))

        if not name or not line1 or not line2:
            return jsonify({'status': 'error', 'message': 'name, line1, and line2 are required'}), 400

        entries = self._read_entries()
        existing = next((entry for entry in entries if self._match_entry(entry, data)), None)
        now_iso = self._utc_now_iso()

        if existing is None:
            existing = {
                'id': str(int(datetime.now(timezone.utc).timestamp() * 1000)),
                'name': name,
                'line1': line1,
                'line2': line2,
                'source': source,
                'saved_at_utc': now_iso,
                'last_loaded_utc': now_iso if mark_loaded else None,
            }
            entries.append(existing)
        else:
            existing['source'] = source
            if mark_loaded:
                existing['last_loaded_utc'] = now_iso

        self._write_entries(entries)
        return jsonify(
            {
                'status': 'ok',
                'message': 'Satellite saved',
                'entry': self._serialize_entry(existing),
            }
        )

    def delete_saved(self, data):
        entry_id = str(data.get('id') or '').strip()
        if not entry_id:
            return jsonify({'status': 'error', 'message': 'id is required'}), 400

        entries = self._read_entries()
        remaining = [entry for entry in entries if str(entry.get('id')) != entry_id]
        if len(remaining) == len(entries):
            return jsonify({'status': 'error', 'message': 'Saved satellite not found'}), 404

        self._write_entries(remaining)
        return jsonify({'status': 'ok', 'message': 'Saved satellite deleted'})

    def load_saved(self, data):
        if self.controller is None:
            return jsonify({'status': 'error', 'message': 'Controller unavailable'}), 503

        entry_id = str(data.get('id') or '').strip()
        if not entry_id:
            return jsonify({'status': 'error', 'message': 'id is required'}), 400

        entries = self._read_entries()
        entry = next((item for item in entries if str(item.get('id')) == entry_id), None)
        if entry is None:
            return jsonify({'status': 'error', 'message': 'Saved satellite not found'}), 404

        ok, message = self.controller.load_tle(entry.get('name'), entry.get('line1'), entry.get('line2'))
        if not ok:
            return jsonify({'status': 'error', 'message': message}), 400

        entry['last_loaded_utc'] = self._utc_now_iso()
        self._write_entries(entries)
        return jsonify(
            {
                'status': 'ok',
                'message': message,
                'entry': self._serialize_entry(entry),
            }
        )

    def mark_loaded(self, data):
        name = (data.get('name') or '').strip()
        line1 = (data.get('line1') or '').strip()
        line2 = (data.get('line2') or '').strip()
        if not name or not line1 or not line2:
            return jsonify({'status': 'error', 'message': 'name, line1, and line2 are required'}), 400

        entries = self._read_entries()
        entry = next((item for item in entries if self._match_entry(item, data)), None)
        if entry is None:
            return jsonify({'status': 'ok', 'message': 'Matching saved satellite not found', 'updated': False})

        entry['last_loaded_utc'] = self._utc_now_iso()
        self._write_entries(entries)
        return jsonify(
            {
                'status': 'ok',
                'message': 'Saved satellite age updated',
                'updated': True,
                'entry': self._serialize_entry(entry),
            }
        )

    @staticmethod
    def _parse_tle_response(text):
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        results = []
        index = 0
        while index + 2 < len(lines):
            name = lines[index]
            line1 = lines[index + 1]
            line2 = lines[index + 2]
            if line1.startswith('1 ') and line2.startswith('2 '):
                results.append(
                    {
                        'name': name,
                        'line1': line1,
                        'line2': line2,
                        'source': 'celestrak',
                    }
                )
                index += 3
            else:
                index += 1
        return results[:20]

    def search_public(self, query):
        search_text = (query or '').strip()
        if len(search_text) < 2:
            return jsonify({'status': 'error', 'message': 'Query must be at least 2 characters'}), 400

        url = (
            'https://celestrak.org/NORAD/elements/gp.php?NAME='
            f'{parse.quote(search_text)}&FORMAT=TLE'
        )
        try:
            with request.urlopen(url, timeout=8) as response:
                body = response.read().decode('utf-8', errors='ignore')
        except error.URLError as exc:
            return jsonify({'status': 'error', 'message': f'Public search unavailable: {exc}'}), 502
        except Exception as exc:
            return jsonify({'status': 'error', 'message': str(exc)}), 500

        return jsonify(
            {
                'status': 'ok',
                'results': self._parse_tle_response(body),
            }
        )