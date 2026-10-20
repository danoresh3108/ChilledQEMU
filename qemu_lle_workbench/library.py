"""Atomic local registry of imported VM projects and their saved configuration."""
import json
import os
from pathlib import Path

from .project import normalize_project


class VmLibrary:
    def __init__(self, path):
        self.path = Path(path)
        self.entries = []
        if self.path.exists():
            value = json.loads(self.path.read_text(encoding='utf-8'))
            if value.get('version') != 1 or not isinstance(value.get('virtualMachines'), list):
                raise ValueError('Unsupported virtual_machines.json format')
            for entry in value['virtualMachines']:
                self.entries.append({'path': str(Path(entry['path']).resolve()),
                    'project': normalize_project(entry['project'])})

    def remember(self, path, project):
        path = str(Path(path).resolve())
        entry = {'path': path, 'project': normalize_project(project)}
        entries = [entry if item['path'] == path else item for item in self.entries]
        if not any(item['path'] == path for item in self.entries): entries.append(entry)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.json.tmp')
        with temporary.open('w', encoding='utf-8') as stream:
            json.dump({'version': 1, 'virtualMachines': entries}, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(self.path)
        self.entries = entries
