# Roll no: cert-aai-2026-06-0043 
import json
from pathlib import Path


def _load(source):
    source = Path(source)
    if not source.exists():
        return {}
    return json.loads(source.read_text())

def _save(source, data):
    source = Path(source)
    source.write_text(json.dumps(data, indent=2) + "\n")


def remember(key, value, source):
    """ Method to store data agaionst key. Note that if same key exists we over ride the data"""
    data = _load(source)
    data[key] = value
    _save(source, data)
    return data

def getMemoryData(source):
    return _load(source)

def recall(key, source):
    """Get the data from memory based on the key"""
    return _load(source).get(key)


    