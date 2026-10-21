# Copyright (c) Meta Platforms, Inc. and affiliates
"""
Main Flask application for the docstring generation visualization.

This module defines the Flask application, routes, and event handlers for
the web-based docstring generation visualization system.
"""

import os
import re
import hmac
import json
import yaml
import threading
import eventlet
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory, Response, abort
from flask_socketio import SocketIO

# Patch standard library for async support with eventlet
eventlet.monkey_patch()

from . import config_handler
from . import visualization_handler
from . import process_handler
from . import git_handler

WORKSPACE_DIR = Path(__file__).parent.parent.parent / 'workspace'
FRONTEND_DIST = Path(__file__).parent.parent.parent / 'frontend' / 'dist'

# Public sharing mode (see DEPLOY.md). When DOCWEAVE_PUBLIC=1 the app is meant to sit behind a public
# URL, so it only clones github.com repositories and disables endpoints that accept arbitrary config.
PUBLIC_MODE = os.environ.get('DOCWEAVE_PUBLIC') == '1'
GITHUB_URL_RE = re.compile(r'^https://github\.com/[\w.-]+/[\w.-]+?(\.git)?/?$')
PUBLIC_BLOCKED_PATHS = {'/api/start', '/api/test_api', '/api/default_config', '/api/completeness'}


def _basic_auth_ok(req) -> bool:
    """True when no password is configured, or the request carries the right Basic credentials."""
    user, password = os.environ.get('DOCWEAVE_USER', ''), os.environ.get('DOCWEAVE_PASSWORD', '')
    if not (user and password):
        return True
    auth = req.authorization
    return bool(auth and auth.username is not None and auth.password is not None
                and hmac.compare_digest(auth.username, user) and hmac.compare_digest(auth.password, password))

def create_app(debug=True):
    """
    Create and configure the Flask application.
    
    Args:
        debug: Whether to run the application in debug mode
        
    Returns:
        The configured Flask application instance
    """
    app = Flask(__name__, 
                static_folder='static',
                template_folder='templates')
    app.config['SECRET_KEY'] = 'docstring-generator-secret!'
    app.config['DEBUG'] = debug
    
    # Initialize SocketIO for real-time updates with async mode
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
    
    # Store application state
    app.config['APP_STATE'] = {
        'is_running': False,
        'config': {},
        'repo_path': '',
        'process': None
    }
    
    @app.before_request
    def guard_requests():
        """Optional shared password, and a locked-down API surface in public mode."""
        if not _basic_auth_ok(request):
            return Response('Authentication required', 401, {'WWW-Authenticate': 'Basic realm="DocWeave"'})
        if PUBLIC_MODE and request.path in PUBLIC_BLOCKED_PATHS:
            return jsonify({'status': 'error', 'message': 'This endpoint is disabled on the public deployment.'}), 403

    # Routes
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def index(path):
        """Serve the built React app (frontend/dist) with SPA fallback; fall back to the old template."""
        if path.startswith(('api/', 'socket.io/')):
            abort(404)
        if FRONTEND_DIST.is_dir():
            if path and (FRONTEND_DIST / path).is_file():
                return send_from_directory(FRONTEND_DIST, path)
            return send_from_directory(FRONTEND_DIST, 'index.html')
        return render_template('index.html')

    @app.route('/api/default_config')
    def get_default_config():
        """Get the default configuration from agent_config.yaml."""
        return jsonify(config_handler.get_default_config())
    
    @app.route('/api/test_api', methods=['POST'])
    def test_api():
        """Test the LLM API connection with a simple query."""
        data = request.json or {}
        
        llm_type = data.get('llm_type', 'claude')
        
        if (not data.get('api_key')) and llm_type.lower() != 'huggingface':
            return jsonify({
                'status': 'error',
                'message': 'API key is required'
            })
        
        api_key = data.get('api_key', 'EMPTY' if llm_type.lower() == 'huggingface' else '')
        model = data.get('model', 'claude-3-5-haiku-latest')
        
        try:
            # Import the appropriate LLM client based on type
            if llm_type.lower() == 'claude':
                try:
                    import anthropic
                    client = anthropic.Anthropic(api_key=api_key)
                    
                    # Send a simple test message
                    response = client.messages.create(
                        model=model,
                        max_tokens=100,
                        messages=[
                            {"role": "user", "content": "Who are you? Please keep your answer very brief."}
                        ]
                    )
                    
                    # Extract the response text
                    if response and hasattr(response, 'content') and len(response.content) > 0:
                        model_response = response.content[0].text
                    else:
                        model_response = "No response content"
                    
                    return jsonify({
                        'status': 'success',
                        'message': 'Successfully connected to Claude API',
                        'model_response': model_response
                    })
                    
                except Exception as e:
                    return jsonify({
                        'status': 'error',
                        'message': f'Error connecting to Claude API: {str(e)}'
                    })
                    
            elif llm_type.lower() == 'openai':
                try:
                    import openai
                    client = openai.OpenAI(api_key=api_key)
                    
                    # Send a simple test message
                    response = client.chat.completions.create(
                        model=model,
                        max_tokens=100,
                        messages=[
                            {"role": "user", "content": "Who are you? Please keep your answer very brief."}
                        ]
                    )
                    
                    # Extract the response text
                    if response and hasattr(response, 'choices') and len(response.choices) > 0:
                        model_response = response.choices[0].message.content
                    else:
                        model_response = "No response content"
                    
                    return jsonify({
                        'status': 'success',
                        'message': 'Successfully connected to OpenAI API',
                        'model_response': model_response
                    })
                    
                except Exception as e:
                    return jsonify({
                        'status': 'error',
                        'message': f'Error connecting to OpenAI API: {str(e)}'
                    })
                    
            elif llm_type.lower() == 'huggingface':
                try:
                    import openai
                    client = openai.OpenAI(
                        api_key=api_key if api_key else "EMPTY",
                        base_url=data.get('api_base') or "http://localhost:8000/v1"
                    )
                    
                    # Send a simple test message
                    response = client.chat.completions.create(
                        model=model,
                        max_tokens=100,
                        messages=[
                            {"role": "user", "content": "Who are you? Please keep your answer very brief."}
                        ]
                    )
                    
                    # Extract the response text
                    if response and hasattr(response, 'choices') and len(response.choices) > 0:
                        model_response = response.choices[0].message.content
                    else:
                        model_response = "No response content"
                    
                    return jsonify({
                        'status': 'success',
                        'message': 'Successfully connected to HuggingFace API',
                        'model_response': model_response
                    })
                    
                except Exception as e:
                    return jsonify({
                        'status': 'error',
                        'message': f'Error connecting to HuggingFace API: {str(e)}'
                    })
            
            else:
                return jsonify({
                    'status': 'error',
                    'message': f'Unsupported LLM type: {llm_type}'
                })
                
        except ImportError as e:
            return jsonify({
                'status': 'error',
                'message': f'Missing required dependency: {str(e)}'
            })
    
    @app.route('/api/clone', methods=['POST'])
    def clone_repository():
        """Clone a repository from a URL into the workspace for processing."""
        if app.config['APP_STATE']['is_running']:
            return jsonify({'status': 'error', 'message': 'Generation already in progress'})

        data = request.json or {}
        url = (data.get('url') or '').strip()
        if not url:
            return jsonify({'status': 'error', 'message': 'Repository URL is required'})

        if PUBLIC_MODE and not GITHUB_URL_RE.match(url):
            return jsonify({'status': 'error', 'message': 'Only public https://github.com/<owner>/<repo> links are accepted here.'})

        try:
            repo_path = git_handler.clone_repo(url, WORKSPACE_DIR)
        except ValueError as e:
            return jsonify({'status': 'error', 'message': str(e)})
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Failed to clone repository: {str(e)}'})

        app.config['APP_STATE']['repo_path'] = str(repo_path)

        return jsonify({'status': 'success', 'repo_path': str(repo_path)})

    @app.route('/api/start_ollama', methods=['POST'])
    def start_ollama_generation():
        """Start docstring generation on the cloned repo using a local Ollama model."""
        if app.config['APP_STATE']['is_running']:
            return jsonify({'status': 'error', 'message': 'Generation already in progress'})

        data = request.json or {}
        model = data.get('model')
        repo_path = app.config['APP_STATE'].get('repo_path')

        if not repo_path or not os.path.exists(repo_path):
            return jsonify({'status': 'error', 'message': 'No cloned repository to process. Call /api/clone first.'})

        try:
            config = config_handler.build_ollama_config(model)
            config_path = config_handler.save_config(config)
        except ValueError as e:
            return jsonify({'status': 'error', 'message': str(e)})

        # A public deployment shares one API quota, so refuse repositories that would use too much of it.
        max_components = int(os.environ.get('DOCWEAVE_MAX_COMPONENTS', '40' if PUBLIC_MODE else '0') or 0)
        if max_components:
            graph = visualization_handler.get_dependency_graph(repo_path)
            todo = sum(1 for n in graph.get('nodes', []) if not n.get('has_docstring'))
            if todo > max_components:
                return jsonify({
                    'status': 'error',
                    'message': (f'This repository has {todo} undocumented components; this public demo accepts at most '
                                f'{max_components} per run. Try a smaller repository, or run DocWeave locally for larger ones.'),
                })

        app.config['APP_STATE']['config'] = config
        app.config['APP_STATE']['is_running'] = True

        def run_and_release():
            """Run generation, then always release the running lock so the next clone/start isn't blocked."""
            try:
                process_handler.start_generation_process(socketio, repo_path, config_path)
            finally:
                app.config['APP_STATE']['is_running'] = False

        thread = socketio.start_background_task(run_and_release)
        app.config['APP_STATE']['process'] = thread

        return jsonify({'status': 'success', 'message': 'Generation started'})

    @app.route('/api/models')
    def get_ollama_models():
        """List the supported local Ollama models that are installed."""
        return jsonify({'models': config_handler.installed_ollama_models()})

    @app.route('/api/dependency-graph')
    def get_dependency_graph_route():
        """Get the dependency graph (nodes/edges) for the current repository."""
        repo_path = app.config['APP_STATE'].get('repo_path')
        if not repo_path:
            return jsonify({'status': 'error', 'message': 'No repository selected'})

        result = visualization_handler.get_dependency_graph(repo_path)
        return jsonify(result)

    @app.route('/api/results')
    def get_results():
        """Get the diff of docstrings generated for the current repository."""
        repo_path = app.config['APP_STATE'].get('repo_path')
        if not repo_path:
            return jsonify({'status': 'error', 'message': 'No repository selected'})

        try:
            diffs = git_handler.get_diff(repo_path)
            return jsonify({'status': 'success', 'files': diffs})
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Failed to compute diff: {str(e)}'})

    @app.route('/api/download-patch')
    def download_patch():
        """Download the generated docstring changes as a single .patch file."""
        repo_path = app.config['APP_STATE'].get('repo_path')
        if not repo_path:
            return jsonify({'status': 'error', 'message': 'No repository selected'})

        try:
            patch_text = git_handler.get_full_diff(repo_path)
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Failed to build patch: {str(e)}'})

        return Response(
            patch_text,
            mimetype='text/x-patch',
            headers={'Content-Disposition': 'attachment; filename=docweave-changes.patch'}
        )

    @app.route('/api/start', methods=['POST'])
    def start_generation():
        """Start the docstring generation process."""
        if app.config['APP_STATE']['is_running']:
            return jsonify({'status': 'error', 'message': 'Generation already in progress'})
        
        data = request.json
        
        # Validate repo path
        repo_path = (data.get('repo_path') or '').strip()
        is_github_url = repo_path.startswith(('http://', 'https://'))
        
        if not is_github_url and not os.path.exists(repo_path):
            return jsonify({'status': 'error', 'message': f'Repository path not found: {repo_path}'})
        
        # Save configuration
        try:
            config_path = config_handler.save_config(data['config'])
        except ValueError as e:
            return jsonify({'status': 'error', 'message': str(e)})
        
        # Store in application state
        app.config['APP_STATE']['config'] = data['config']
        app.config['APP_STATE']['repo_path'] = repo_path
        app.config['APP_STATE']['is_running'] = True
        
        def run_and_release():
            try:
                process_handler.start_generation_process(
                    socketio, repo_path, config_path, app.config['APP_STATE']
                )
            finally:
                app.config['APP_STATE']['is_running'] = False

        # Start the generation process
        thread = socketio.start_background_task(run_and_release)
        
        app.config['APP_STATE']['process'] = thread
        
        return jsonify({'status': 'success', 'message': 'Generation started'})
    
    @app.route('/api/stop', methods=['POST'])
    def stop_generation():
        """Stop the docstring generation process."""
        if not app.config['APP_STATE']['is_running']:
            return jsonify({'status': 'error', 'message': 'No generation in progress'})
        
        process_handler.stop_generation_process()
        app.config['APP_STATE']['is_running'] = False
        
        return jsonify({'status': 'success', 'message': 'Generation stopped'})
    
    @app.route('/api/status')
    def get_status():
        """Get the current status of the generation process."""
        return jsonify({
            'is_running': app.config['APP_STATE']['is_running'],
            'repo_path': app.config['APP_STATE']['repo_path']
        })
    
    @app.route('/api/completeness')
    def get_completeness():
        """Get the current completeness evaluation of the repository."""
        if not app.config['APP_STATE']['repo_path']:
            return jsonify({'status': 'error', 'message': 'No repository selected'})
        
        results = visualization_handler.get_completeness_data(app.config['APP_STATE']['repo_path'])
        return jsonify(results)
    
    # Socket.IO event handlers
    @socketio.on('connect')
    def handle_connect():
        """Handle client connection to Socket.IO."""
        if not _basic_auth_ok(request):
            return False  # refuse the connection when a shared password is set and not supplied
        if app.config['APP_STATE']['is_running']:
            # Send current state to newly connected client
            socketio.emit('status_update', visualization_handler.get_current_status())
    
    # Additional routes and event handlers can be added here
    
    return app, socketio 