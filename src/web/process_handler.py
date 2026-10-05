# Copyright (c) Meta Platforms, Inc. and affiliates
"""
Process handler for running the docstring generation.

This module handles starting, monitoring, and stopping the docstring generation
process, as well as capturing its output and sending it to the web interface.
"""

import os
import sys
import subprocess
import threading
import tempfile
import signal
import re
from pathlib import Path
from typing import Optional, Dict, Any

from . import visualization_handler

# Global variables to track the process
process = None
should_stop = False

class OutputParser:
    """Parser to handle output from the docstring generation process."""
    
    def __init__(self, socketio):
        """
        Initialize the output parser.
        
        Args:
            socketio: The Flask-SocketIO instance for sending updates to clients
        """
        self.socketio = socketio
        
        # Regular expressions for parsing different types of output
        self.status_regex = re.compile(r'STATUS: Agent: (\w+), Message: (.+)')
        self.component_regex = re.compile(r'COMPONENT: (.+) in file (.+)')
        self.event_regex = re.compile(r'EVENT: (.+)')
        self.log_regex = re.compile(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} - (\w+) - (\w+) - (.+)')
        
        # Additional regex to detect agent activity from regular logs
        self.agent_activity_regex = re.compile(r'(reader|writer|searcher|verifier)', re.IGNORECASE)
        self.docstring_update_regex = re.compile(r'Successfully updated docstring for (.+)|Completed docstring generation for (.+)', re.IGNORECASE)
        
        # Patterns to filter out visualization-related output from logs
        visualization_patterns = [
            r'┌─+┐',     # Box top
            r'│.*│',     # Box content
            r'└─+┘',     # Box bottom
            r'Agent:',   # Agent status
            r'Status:',  # Status message
            r'Component:',  # Component info
            r'╔═+╗',     # Double-line box top
            r'║.*║',     # Double-line box content
            r'╚═+╝',     # Double-line box bottom
            r'▶ ',       # Progress indicators
            r'→ ',       # Arrow indicators
            r'⦿',        # Bullet indicators
            r'Processing component \d+/\d+',  # Progress messages
            r'╡.*╞',     # Table separators
            r'═+',       # Table lines
            r'DocAgent (?:Workflow )?Status',  # Workflow status header
            r'Processing: ',    # Processing status line
            r'File: ',          # File status line
            r'Active Agent: ',  # Agent status line
            r'Status: ',        # Status message line
            r'Workflow Input:',  # Input section
            r'Component Name:',  # Input component name
            r'File Path:',       # Input file path
            r'Dependencies:',    # Input dependencies
            r'Code:',            # Input code
            r'^Input:',          # Input header
            r'\[.*?\]',          # Status messages in brackets
            r'EVENT:',           # Structured event data
        ]
        self.visualization_filter = re.compile('|'.join(visualization_patterns))
        
    def process_line(self, line):
        """Process a single line of output."""
        # Decode the line if it's bytes
        if isinstance(line, bytes):
            try:
                line = line.decode('utf-8').rstrip()
            except UnicodeDecodeError:
                return
        else:
            line = line.rstrip()
            
            # Process workflow status lines separately to update agent status
            if 'Processing:' in line or 'File:' in line:
                if 'Processing:' in line:
                    component = line.split('Processing:')[1].strip()
                    if component:
                        visualization_handler.update_component_focus(component, "")
                if 'File:' in line:
                    file_path = line.split('File:')[1].strip()
                    if file_path:
                        # Update the current file without changing the component
                        current_status = visualization_handler.get_current_status()
                        if 'status' in current_status and current_status['status'].get('current_component'):
                            visualization_handler.update_component_focus(
                                current_status['status']['current_component'], 
                                file_path
                            )
                self.socketio.emit('status_update', visualization_handler.get_current_status())
            
            # Add to log messages - filter out visualization
            if not self.visualization_filter.search(line):
                visualization_handler.add_log_message(line)
                self.socketio.emit('log_line', line)
            
            # Check for status updates
            status_match = self.status_regex.search(line)
            if status_match:
                agent, message = status_match.groups()
                visualization_handler.update_agent_status(agent, message)
                self.socketio.emit('status_update', visualization_handler.get_current_status())
                return
            
            # Check for agent activity in regular logs
            if not status_match:  # Only check if we didn't already match a status
                agent_match = self.agent_activity_regex.search(line)
                if agent_match and ('active' in line.lower() or 'using' in line.lower() or 'processing' in line.lower()):
                    # Extract agent name from logs
                    agent = agent_match.group(1).capitalize()
                    visualization_handler.update_agent_status(agent, "Processing")
                    self.socketio.emit('status_update', visualization_handler.get_current_status())
            
            # Check for component updates
            component_match = self.component_regex.search(line)
            if component_match:
                component, file_path = component_match.groups()
                visualization_handler.update_component_focus(component, file_path)
                visualization_handler.update_file_status(file_path, 'in_progress')
                self.socketio.emit('status_update', visualization_handler.get_current_status())
                return
            
            # Check for structured events
            event_match = self.event_regex.search(line)
            if event_match:
                import json
                try:
                    event_data = json.loads(event_match.group(1))
                    if event_data.get("type") == "progress_update":
                        visualization_handler.update_structured_progress(event_data)
                        self.socketio.emit('status_update', visualization_handler.get_current_status())
                except Exception as e:
                    print(f"Error parsing EVENT: {e}")
                return
            
            # Also check for progress updates in normal log lines
            progress_in_log = re.search(r'Processing component (\d+)/(\d+)', line)
            if progress_in_log:
                current, total = progress_in_log.groups()
                visualization_handler.update_progress(int(total), int(current), '', {})
                self.socketio.emit('status_update', visualization_handler.get_current_status())
            
            # Check for docstring updates
            docstring_update_match = self.docstring_update_regex.search(line)
            if docstring_update_match:
                component = docstring_update_match.group(1) or docstring_update_match.group(2)
                # If this is a file path, extract it
                if component and '/' in component:
                    file_path = component
                    visualization_handler.update_file_status(file_path, 'complete')
                    self.socketio.emit('status_update', visualization_handler.get_current_status())
                    # Emit a special event for docstring updates
                    self.socketio.emit('docstring_updated', {'component': component})
            
            # Try to extract component information from other log lines
            if 'Processing' in line and ':' in line and 'file' in line:
                parts = line.split('file')
                if len(parts) > 1:
                    file_path = parts[1].strip()
                    component = parts[0].split('Processing')[-1].strip()
                    if component and file_path:
                        visualization_handler.update_component_focus(component, file_path)
                        visualization_handler.update_file_status(file_path, 'in_progress')
                        self.socketio.emit('status_update', visualization_handler.get_current_status())
            
            # Check for log messages
            log_match = self.log_regex.search(line)
            if log_match:
                _, level, message = log_match.groups()
                # If the message indicates completion of a file, update the file status
                if 'Completed docstring generation for' in message or 'Successfully updated docstring for' in message:
                    # Try to extract the file path from the message
                    file_match = re.search(r'for file (.+)$|for (.+)', message)
                    if file_match:
                        file_path = file_match.group(1) or file_match.group(2)
                        if file_path and '.' in file_path:  # Simple check to ensure it looks like a filename
                            visualization_handler.update_file_status(file_path, 'complete')
                            self.socketio.emit('status_update', visualization_handler.get_current_status())
                            # Emit a special event for docstring updates
                            self.socketio.emit('docstring_updated', {'component': file_path})
                
                self.socketio.emit('log_message', {'level': level, 'message': message})

def start_generation_process(socketio, repo_path: str, config_path: str, app_state: Optional[Dict] = None):
    """
    Start the docstring generation process.
    
    Args:
        socketio: The Flask-SocketIO instance for sending updates to clients
        repo_path: Path to the repository to generate docstrings for
        config_path: Path to the configuration file
        app_state: Application state dictionary to update repo_path after cloning
    """
    global process, should_stop
    
    should_stop = False
    
    # Set an initial status to show we're starting
    visualization_handler.update_agent_status("System", "Starting docstring generation...")
    socketio.emit('status_update', visualization_handler.get_current_status())
    
    # Connect the socket to the web bridge
    try:
        from src.visualizer.web_bridge import WebSocketManager
        WebSocketManager.set_socket(socketio)
    except ImportError:
        socketio.emit('log_message', {
            'level': 'warning',
            'message': 'Web bridge not available. Some features may not work correctly.'
        })
    
    # Handle GitHub URL cloning
    is_github_url = repo_path.startswith(('http://', 'https://'))
    if is_github_url:
        visualization_handler.update_agent_status("System", f"Cloning repository {repo_path}...")
        socketio.emit('status_update', visualization_handler.get_current_status())
        socketio.emit('log_message', {
            'level': 'info',
            'message': f'Cloning repository {repo_path}... this may take a moment.'
        })
        
        try:
            import eventlet
            import uuid
            from . import git_handler
            WORKSPACE_DIR = Path(__file__).parent.parent.parent / 'workspace'
            
            # Validate URL
            url = repo_path.strip()
            if not git_handler._VALID_URL_RE.match(url):
                raise ValueError("Only http(s) git URLs are supported")
                
            WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
            dest = WORKSPACE_DIR / uuid.uuid4().hex
            
            # Run git clone and assign to global process so it can be stopped
            global process
            import time
            import shutil
            import tempfile
            
            cmd = ['git', 'clone', '--progress', '--depth', '1', url, str(dest)]
            
            # We set environment variables to disable credential prompts which can hang the process
            env = os.environ.copy()
            env['GIT_TERMINAL_PROMPT'] = '0'
            env['GCM_INTERACTIVE'] = 'false'
            
            # Use a temporary file instead of PIPE to avoid Eventlet/Windows deadlock
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, dir=WORKSPACE_DIR) as temp_log:
                log_path = temp_log.name
                
            try:
                with open(log_path, 'w') as log_file:
                    process = subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT, env=env)
                
                start_time = time.time()
                timeout_seconds = 300 # 5 minutes timeout for cloning
                clone_failed = False
                error_output = []
                
                with open(log_path, 'r') as log_read:
                    # Poll until finished, sleeping to yield to eventlet loop
                    while process.poll() is None:
                        # Check for cancellation
                        if should_stop:
                            process.terminate()
                            clone_failed = True
                            error_output.append("Cloning cancelled by user.")
                            break
                            
                        # Check for timeout
                        if time.time() - start_time > timeout_seconds:
                            process.terminate()
                            clone_failed = True
                            error_output.append("Cloning timed out after 5 minutes.")
                            break
                        
                        # Read new lines from log file
                        lines = log_read.readlines()
                        for line in lines:
                            # git progress uses \r, handle that
                            cleaned = line.replace('\r', '\n').strip()
                            for part in cleaned.split('\n'):
                                if part.strip():
                                    error_output.append(part.strip())
                                    if "Receiving objects" in part or "Resolving deltas" in part:
                                        socketio.emit('log_message', {'level': 'info', 'message': part.strip()})
                        
                        eventlet.sleep(0.1)
                        
                    # Final read after process exits
                    lines = log_read.readlines()
                    for line in lines:
                        cleaned = line.replace('\r', '\n').strip()
                        for part in cleaned.split('\n'):
                            if part.strip():
                                error_output.append(part.strip())
                                if "Receiving objects" in part or "Resolving deltas" in part:
                                    socketio.emit('log_message', {'level': 'info', 'message': part.strip()})
                                    
                return_code = process.returncode if process else -1
            finally:
                process = None # Clear global process
                try:
                    os.remove(log_path)
                except:
                    pass
            
            if clone_failed or return_code != 0:
                # Cleanup partially cloned dir
                if dest.exists():
                    try:
                        shutil.rmtree(dest, ignore_errors=True)
                    except:
                        pass
                        
                stderr_str = "\n".join(error_output)
                raise Exception(f"Git clone failed: {stderr_str}")
                
            repo_path = str(dest)
            
            if app_state is not None:
                app_state['repo_path'] = repo_path
                
            socketio.emit('log_message', {
                'level': 'info',
                'message': f'Successfully cloned repository to {repo_path}'
            })
            
            # Validate it has source files
            has_source = False
            for root, dirs, files in os.walk(repo_path):
                if any(f.endswith(('.py', '.java')) for f in files):
                    has_source = True
                    break
            
            if not has_source:
                error_msg = 'No Python (.py) or Java (.java) source files found in the cloned repository.'
                socketio.emit('error', {'message': error_msg})
                socketio.emit('log_message', {'level': 'error', 'message': error_msg})
                return
                
        except Exception as e:
            error_msg = f'Failed to clone repository: {str(e)}'
            socketio.emit('error', {'message': error_msg})
            socketio.emit('log_message', {'level': 'error', 'message': error_msg})
            return
    
    # Get the repository structure and update the visualization state
    try:
        structure = visualization_handler.get_repo_structure(repo_path)
        socketio.emit('status_update', visualization_handler.get_current_status())
        socketio.emit('log_message', {
            'level': 'info',
            'message': f'Repository structure loaded with {len(structure["children"])} top-level items'
        })
    except Exception as e:
        socketio.emit('log_message', {
            'level': 'error',
            'message': f'Error loading repository structure: {str(e)}'
        })
    
    # Find the generate_docstrings.py script
    script_path = Path(__file__).parent.parent.parent / 'generate_docstrings.py'
    
    if not script_path.exists():
        socketio.emit('error', {
            'message': f'Could not find docstring generation script at {script_path}'
        })
        return
    
    # Start the process
    try:
        import tempfile
        import eventlet
        WORKSPACE_DIR = Path(__file__).parent.parent.parent / 'workspace'
        WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
        
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, dir=WORKSPACE_DIR) as temp_log:
            log_path = temp_log.name
            
        try:
            with open(log_path, 'w') as log_file:
                process = subprocess.Popen(
                    [sys.executable, str(script_path), 
                     '--repo-path', repo_path, 
                     '--config-path', config_path,
                     '--enable-web'],  # Enable web integration
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    env=os.environ.copy()
                )
            
            parser = OutputParser(socketio)
            
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as log_read:
                while process.poll() is None:
                    if should_stop:
                        process.terminate()
                        break
                        
                    lines = log_read.readlines()
                    for line in lines:
                        parser.process_line(line)
                        
                    eventlet.sleep(0.1)
                    
                # Final read
                lines = log_read.readlines()
                for line in lines:
                    parser.process_line(line)
                    
            return_code = process.returncode if process else -1
            
            if return_code == 0 and not should_stop:
                socketio.emit('complete', {
                    'message': 'Docstring generation completed successfully'
                })
            elif should_stop:
                socketio.emit('error', {'message': 'Docstring generation was stopped.'})
            else:
                socketio.emit('error', {
                    'message': f'Docstring generation failed with return code {return_code}'
                })
        finally:
            try:
                os.remove(log_path)
            except:
                pass
                
    except Exception as e:
        socketio.emit('error', {
            'message': f'Error starting docstring generation process: {str(e)}'
        })
    
    finally:
        process = None

def stop_generation_process():
    """
    Stop the docstring generation process.
    
    Returns:
        True if the process was stopped, False otherwise
    """
    global process, should_stop
    
    if process is None:
        return False
    
    should_stop = True
    
    try:
        # Disconnect from the web bridge
        try:
            from src.visualizer.web_bridge import WebSocketManager
            WebSocketManager.disable()
        except ImportError:
            pass
        
        # Try to terminate the process gracefully first
        process.terminate()
        
        # Wait for up to 5 seconds for the process to terminate
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # If the process didn't terminate, kill it
            process.kill()
        
        return True
    
    except Exception as e:
        print(f"Error stopping process: {e}")
        return False 