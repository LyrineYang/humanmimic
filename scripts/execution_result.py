"""Execution, task outcome and research acceptance are separate contracts."""
import hashlib
from pathlib import Path


def media_integrity(audit):
    """A historical passed audit must not hide missing/changed cached media."""
    videos = audit.get('videos', [])
    if not videos:
        return False
    for item in videos:
        if item.get('status') != 'passed' or not item.get('full_decode'):
            return False
        digest = hashlib.sha256()
        try:
            with Path(item['path']).open('rb') as stream:
                for block in iter(lambda: stream.read(4*1024**2), b''):
                    digest.update(block)
        except (OSError, KeyError):
            return False
        if digest.hexdigest() != item.get('sha256'):
            return False
    return True


def r2_result(result, audit):
    complete = (audit.get('extraction', {}).get('status') == 'passed'
                and audit.get('media_status') == 'passed'
                and not audit.get('audit_error') and not audit.get('missing_evidence')
                and media_integrity(audit))
    task = [audit.get(k, 'awaiting_verification') for k in ('physical_status', 'body_status')]
    task_status = 'failed' if 'failed' in task else 'passed' if all(v == 'passed' for v in task) else 'awaiting_verification'
    return {'schema_version': 2, 'id': result.get('id'),
            'execution_status': 'completed' if complete else 'failed' if result.get('status') == 'failed' else 'incomplete',
            'task_status': task_status, 'acceptance_status': result['status'],
            'review_status': audit.get('visual_status', 'awaiting_verification'),
            'reason': result.get('reason'), 'scope': 'Execution success does not imply imitation or research acceptance'}


def result_exit_code(result, require_acceptance=False):
    if result['execution_status'] != 'completed':
        return 1
    if require_acceptance:
        return {'passed': 0, 'failed': 1, 'awaiting_verification': 3, 'needs_input': 3}[result['acceptance_status']]
    return 0
