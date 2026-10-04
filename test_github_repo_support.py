import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.web.app import create_app
from src.web.process_handler import start_generation_process

@pytest.fixture
def app():
    app, socketio = create_app(debug=True)
    app.config['TESTING'] = True
    return app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def mock_socketio():
    socketio = MagicMock()
    return socketio

def test_api_start_with_valid_github_url(client):
    """Test 1. Valid public GitHub URL."""
    with patch('src.web.config_handler.save_config') as mock_save, \
         patch('flask_socketio.SocketIO.start_background_task') as mock_task:
        
        mock_save.return_value = '/tmp/config.json'
        
        response = client.post('/api/start', json={
            'repo_path': 'https://github.com/plotly/dash',
            'config': {}
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'
        mock_task.assert_called_once()

def test_api_start_with_invalid_local_path(client):
    """Test 5. Invalid local path."""
    response = client.post('/api/start', json={
        'repo_path': '/path/that/does/not/exist/9999',
        'config': {}
    })
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'error'
    assert 'not found' in data['message']

def test_api_start_with_valid_local_path(client):
    """Test 4. Valid local repository path."""
    with patch('src.web.config_handler.save_config') as mock_save, \
         patch('flask_socketio.SocketIO.start_background_task') as mock_task:
        
        mock_save.return_value = '/tmp/config.json'
        
        response = client.post('/api/start', json={
            'repo_path': os.path.dirname(os.path.abspath(__file__)),
            'config': {}
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'
        mock_task.assert_called_once()

def test_start_generation_process_github_url(mock_socketio):
    """Test 7. Successful handoff to the existing documentation pipeline."""
    app_state = {}
    with patch('src.web.git_handler.clone_repo') as mock_clone, \
         patch('os.walk') as mock_walk, \
         patch('subprocess.Popen') as mock_popen, \
         patch('src.web.visualization_handler.get_repo_structure') as mock_struct, \
         patch('pathlib.Path.exists') as mock_exists:
        
        mock_clone.return_value = '/tmp/cloned_repo'
        mock_walk.return_value = [('/tmp/cloned_repo', [], ['test.py'])]
        mock_exists.return_value = True
        mock_proc = MagicMock()
        mock_proc.wait.return_value = 0
        mock_proc.stdout.readline.side_effect = [b'']
        mock_popen.return_value = mock_proc
        
        start_generation_process(mock_socketio, 'https://github.com/plotly/dash', '/tmp/config.json', app_state)
        
        # Check that it cloned the repository
        mock_clone.assert_called_once()
        
        # Check that app_state got updated
        assert app_state.get('repo_path') == '/tmp/cloned_repo'
        
        # Check that it started the subprocess with the cloned path
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert '--repo-path' in args
        repo_idx = args.index('--repo-path')
        assert args[repo_idx + 1] == '/tmp/cloned_repo'

def test_start_generation_process_github_url_no_source(mock_socketio):
    """Test 6. Git clone / validation failure (Empty or unsupported repository)."""
    app_state = {}
    with patch('src.web.git_handler.clone_repo') as mock_clone, \
         patch('os.walk') as mock_walk:
        
        mock_clone.return_value = '/tmp/cloned_repo'
        # Return files that are not python or java
        mock_walk.return_value = [('/tmp/cloned_repo', [], ['README.md'])]
        
        start_generation_process(mock_socketio, 'https://github.com/plotly/dash', '/tmp/config.json', app_state)
        
        # Error should be emitted because no source files found
        mock_socketio.emit.assert_any_call('error', {'message': 'No Python (.py) or Java (.java) source files found in the cloned repository.'})

def test_start_generation_process_github_url_clone_fails(mock_socketio):
    """Test 6. Git clone failure."""
    app_state = {}
    with patch('src.web.git_handler.clone_repo') as mock_clone:
        
        mock_clone.side_effect = Exception("Git clone failed")
        
        start_generation_process(mock_socketio, 'https://github.com/plotly/dash', '/tmp/config.json', app_state)
        
        # Error should be emitted
        mock_socketio.emit.assert_any_call('error', {'message': 'Failed to clone repository: Git clone failed'})

if __name__ == '__main__':
    pytest.main(['-v', __file__])
