import json
import os
from datetime import datetime, timedelta, timezone
from urllib import error, parse, request

from flask import jsonify
from skyfield.api import EarthSatellite


class TleLibraryService:
    #  % ------------------------------------------------------------
    #  % Inputs: Library file path plus optional controller for loading saved TLEs.
    #  % Side-effects: Persists saved satellites, computes age metadata, and proxies public TLE search results.
    #  % Returns: Service object used by Flask routes for saved/public TLE workflows.
    #  % ------------------------------------------------------------
    def __init__(self, library_path, controller=None, integration_settings_path=None):
        self.library_path = os.path.abspath(os.path.expanduser(library_path))
        self.controller = controller
        self.integration_settings_path = (
            os.path.abspath(os.path.expanduser(integration_settings_path))
            if integration_settings_path
            else None
        )
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

    def _read_integration_settings(self):
        if not self.integration_settings_path:
            return {}
        try:
            with open(self.integration_settings_path, 'r', encoding='utf-8') as file:
                payload = json.load(file)
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def _write_integration_settings(self, payload):
        if not self.integration_settings_path:
            return
        settings_dir = os.path.dirname(self.integration_settings_path)
        if settings_dir:
            os.makedirs(settings_dir, exist_ok=True)
        with open(self.integration_settings_path, 'w', encoding='utf-8') as file:
            json.dump(payload, file, indent=4)

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
            return 'just saved'
        if seconds < 3600:
            minutes = int(seconds // 60)
            return f'{minutes} min old'
        if seconds < 86400:
            hours = int(seconds // 3600)
            return f'{hours} h old'
        days = int(seconds // 86400)
        return f'{days} d old'

    def _serialize_entry(self, entry):
        saved_at_utc = entry.get('saved_at_utc')
        payload = dict(entry)
        payload['age_reference_utc'] = saved_at_utc
        payload['age_label'] = self._age_label(saved_at_utc)
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
            key=lambda entry: entry.get('saved_at_utc') or '',
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

    def _fetch_public_entries(self, search_text):
        url = (
            'https://celestrak.org/NORAD/elements/gp.php?NAME='
            f'{parse.quote(search_text)}&FORMAT=TLE'
        )
        with request.urlopen(url, timeout=8) as response:
            body = response.read().decode('utf-8', errors='ignore')
        return self._parse_tle_response(body)

    @staticmethod
    def _select_best_public_entry(search_text, results):
        if not results:
            return None

        normalized = (search_text or '').strip().lower()
        for entry in results:
            if entry.get('name', '').strip().lower() == normalized:
                return entry
        return results[0]

    def update_public_satellites(self):
        entries = self._read_entries()
        public_entries = [
            entry for entry in entries
            if (entry.get('source') or '').strip().lower() in {'public-search', 'celestrak'}
        ]

        if not public_entries:
            return jsonify({'status': 'ok', 'message': 'No public satellites found', 'updated': 0})

        updated_count = 0
        not_found = []

        for entry in public_entries:
            try:
                results = self._fetch_public_entries(entry.get('name', ''))
            except error.URLError as exc:
                return jsonify({'status': 'error', 'message': f'Public update unavailable: {exc}'}), 502
            except Exception as exc:
                return jsonify({'status': 'error', 'message': str(exc)}), 500

            best = self._select_best_public_entry(entry.get('name', ''), results)
            if best is None:
                not_found.append(entry.get('name', 'unknown'))
                continue

            entry['name'] = best.get('name', entry.get('name'))
            entry['line1'] = best.get('line1', entry.get('line1'))
            entry['line2'] = best.get('line2', entry.get('line2'))
            entry['source'] = best.get('source', entry.get('source') or 'public-search')
            entry['saved_at_utc'] = self._utc_now_iso()
            updated_count += 1

        self._write_entries(entries)
        message = f'Updated {updated_count} public satellite(s)'
        if not_found:
            message += f'; no match for {", ".join(not_found[:5])}'
        return jsonify({'status': 'ok', 'message': message, 'updated': updated_count, 'not_found': not_found})

    def get_last_tracked(self):
        payload = self._read_integration_settings()
        last = payload.get('last_tracked_satellite', {})
        if not isinstance(last, dict):
            last = {}
        return jsonify(
            {
                'status': 'ok',
                'last_tracked_satellite': {
                    'name': (last.get('name') or '').strip(),
                    'line1': (last.get('line1') or '').strip(),
                    'line2': (last.get('line2') or '').strip(),
                    'updated_utc': last.get('updated_utc'),
                },
            }
        )

    def set_last_tracked(self, data):
        name = (data.get('name') or '').strip()
        line1 = (data.get('line1') or '').strip()
        line2 = (data.get('line2') or '').strip()
        if not name or not line1 or not line2:
            return jsonify({'status': 'error', 'message': 'name, line1, and line2 are required'}), 400

        payload = self._read_integration_settings()
        payload['last_tracked_satellite'] = {
            'name': name,
            'line1': line1,
            'line2': line2,
            'updated_utc': self._utc_now_iso(),
        }

        # Keep standalone section aligned for startup defaults.
        standalone = payload.setdefault('standalone', {})
        if isinstance(standalone, dict):
            standalone['name'] = name
            standalone['line1'] = line1
            standalone['line2'] = line2

        self._write_integration_settings(payload)
        return jsonify({'status': 'ok', 'message': 'Last tracked satellite saved'})

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
        try:
            results = self._fetch_public_entries(search_text)
        except error.URLError as exc:
            return jsonify({'status': 'error', 'message': f'Public search unavailable: {exc}'}), 502
        except Exception as exc:
            return jsonify({'status': 'error', 'message': str(exc)}), 500

        return jsonify(
            {
                'status': 'ok',
                'results': results,
            }
        )

    def preview_next_pass(self, data):
        name = (data.get('name') or '').strip()
        line1 = (data.get('line1') or '').strip()
        line2 = (data.get('line2') or '').strip()
        if not name or not line1 or not line2:
            return jsonify({'status': 'error', 'message': 'name, line1, and line2 are required'}), 400

        controller = self.controller
        if controller is None or getattr(controller, 'tracker', None) is None:
            return jsonify({'status': 'error', 'message': 'Controller unavailable'}), 503

        tracker = controller.tracker
        try:
            satellite = EarthSatellite(line1, line2, name, tracker.ts)
        except Exception:
            return jsonify({'status': 'error', 'message': 'Failed to parse TLE for preview'}), 400

        now_utc = datetime.now(timezone.utc)
        controller_settings = getattr(self.controller, 'settings', {}) or {}
        max_search_hours = float(controller_settings.get('pass_search_hours', 24.0))
        min_elevation = float(controller_settings.get('pass_min_elevation_deg', 10.0))
        t0 = tracker.ts.from_datetime(now_utc)
        t1 = tracker.ts.from_datetime(now_utc + timedelta(hours=max_search_hours))

        try:
            t_events, events = satellite.find_events(tracker.observer, t0, t1, altitude_degrees=min_elevation)
        except Exception as exc:
            return jsonify({'status': 'error', 'message': str(exc)}), 500

        current_pass = None
        for t_event, event in zip(t_events, events):
            event_time = t_event.utc_datetime()
            if event == 0:
                current_pass = {
                    'satellite': name,
                    'rise_time': event_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'max_elevation': None,
                    'set_time': None,
                    'duration': None,
                }
            elif event == 1 and current_pass is not None:
                azimuth, elevation, _, _ = tracker.get_position(event_time)
                current_pass['max_elevation'] = round(elevation, 1)
                current_pass['peak_azimuth'] = round(azimuth, 1)
            elif event == 2 and current_pass is not None:
                current_pass['set_time'] = event_time.strftime('%Y-%m-%d %H:%M:%S')
                rise_dt = datetime.strptime(current_pass['rise_time'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
                current_pass['duration'] = round((event_time - rise_dt).total_seconds() / 60.0, 1)
                return jsonify({'status': 'ok', 'pass': current_pass})

        return jsonify({'status': 'ok', 'pass': None})