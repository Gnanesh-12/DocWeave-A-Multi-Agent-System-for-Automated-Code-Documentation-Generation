import os
import time
import shutil
import unittest
from unittest.mock import patch, MagicMock, Mock
from pathlib import Path
from src.web import process_handler
import tempfile
import sys

class DummySocketIO:
    def __init__(self):
        self.emitted = []
    
    def emit(self, event, data=None):
        self.emitted.append((event, data))

class TestGithubCloning(unittest.TestCase):
    def setUp(self):
        self.socketio = DummySocketIO()
        self.app_state = {}
        # Make sure should_stop is False
        process_handler.should_stop = False

    @patch('subprocess.Popen')
    def test_successful_clone_and_handoff(self, mock_popen):
        # Mock subprocess.Popen
        mock_process = MagicMock()
        mock_process.poll.side_effect = [None, None, 0] # Poll returns None twice, then 0 (exited)
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        # We need to mock the temporary file that Popen writes to
        # Since process_handler uses tempfile.NamedTemporaryFile, we'll patch it to use a real temp file but write to it
        original_named_temp_file = tempfile.NamedTemporaryFile
        
        temp_logs = []
        def mocked_named_temp(*args, **kwargs):
            f = original_named_temp_file(*args, **kwargs)
            temp_logs.append(f.name)
            return f
            
        with patch('tempfile.NamedTemporaryFile', side_effect=mocked_named_temp):
            # Also patch the actual generation so it doesn't run the script
            with patch('src.web.visualization_handler.get_repo_structure', return_value={'children': []}):
                # Mock the script execution part
                mock_gen_process = MagicMock()
                mock_gen_process.poll.return_value = 0
                mock_gen_process.returncode = 0
                mock_popen.side_effect = [mock_process, mock_gen_process]
                
                # Mock os.walk so it finds a .py file
                with patch('os.walk', return_value=[('/mock/repo', [], ['file.py'])]):
                    # Write some fake output to the log file before poll() finishes
                    def side_effect_sleep(*args):
                        if temp_logs:
                            with open(temp_logs[0], 'a') as f:
                                f.write("Receiving objects: 100% (10/10), done.\n")
                    
                    with patch('eventlet.sleep', side_effect=side_effect_sleep):
                        process_handler.start_generation_process(
                            self.socketio,
                            'https://github.com/mock/repo.git',
                            '/mock/config.yaml',
                            self.app_state
                        )
        
        # Verify
        self.assertIn('repo_path', self.app_state)
        self.assertEqual(Path(self.app_state['repo_path']).parent.name, 'workspace')
        
        # Check that 'Cloning repository' message was sent
        emitted_logs = [e[1]['message'] for e in self.socketio.emitted if e[0] == 'log_message']
        self.assertTrue(any('Cloning repository https://github.com/mock/repo.git' in msg for msg in emitted_logs))
        self.assertTrue(any('Receiving objects: 100% (10/10), done.' in msg for msg in emitted_logs))

    @patch('subprocess.Popen')
    def test_clone_failure(self, mock_popen):
        mock_process = MagicMock()
        mock_process.poll.side_effect = [None, 1]
        mock_process.returncode = 1
        mock_popen.return_value = mock_process
        
        temp_logs = []
        original_named_temp_file = tempfile.NamedTemporaryFile
        def mocked_named_temp(*args, **kwargs):
            f = original_named_temp_file(*args, **kwargs)
            temp_logs.append(f.name)
            return f
            
        with patch('tempfile.NamedTemporaryFile', side_effect=mocked_named_temp):
            def side_effect_sleep(*args):
                if temp_logs:
                    with open(temp_logs[0], 'a') as f:
                        f.write("fatal: repository not found\n")
            
            with patch('eventlet.sleep', side_effect=side_effect_sleep):
                process_handler.start_generation_process(
                    self.socketio,
                    'https://github.com/mock/invalid.git',
                    '/mock/config.yaml',
                    self.app_state
                )
                
        errors = [e[1]['message'] for e in self.socketio.emitted if e[0] == 'error']
        self.assertTrue(len(errors) > 0, f"No errors emitted, emitted events: {self.socketio.emitted}")
        self.assertTrue(any('fatal: repository not found' in err for err in errors), f"Errors were: {errors}. Emitted: {self.socketio.emitted}")

    @patch('subprocess.Popen')
    def test_clone_timeout(self, mock_popen):
        mock_process = MagicMock()
        mock_process.poll.return_value = None # Always None (hanging)
        mock_popen.return_value = mock_process
        
        # Mock time.time to simulate timeout
        time_vals = [0, 100, 400] # Jump past 300 seconds timeout
        def mocked_time():
            return time_vals.pop(0) if time_vals else 400
            
        with patch('time.time', side_effect=mocked_time):
            process_handler.start_generation_process(
                self.socketio,
                'https://github.com/mock/hang.git',
                '/mock/config.yaml',
                self.app_state
            )
            
        mock_process.terminate.assert_called_once()
        errors = [e[1]['message'] for e in self.socketio.emitted if e[0] == 'error']
        self.assertTrue(any('Cloning timed out' in err for err in errors))

    @patch('subprocess.Popen')
    def test_clone_cancellation(self, mock_popen):
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process
        
        # Simulate cancellation after 1 sleep
        def mocked_sleep(secs):
            process_handler.should_stop = True
            
        with patch('eventlet.sleep', side_effect=mocked_sleep):
            process_handler.start_generation_process(
                self.socketio,
                'https://github.com/mock/cancel.git',
                '/mock/config.yaml',
                self.app_state
            )
            
        mock_process.terminate.assert_called_once()
        errors = [e[1]['message'] for e in self.socketio.emitted if e[0] == 'error']
        self.assertTrue(any('Cloning cancelled by user' in err for err in errors))

if __name__ == '__main__':
    unittest.main()