# Copyright (c) Meta Platforms, Inc. and affiliates
"""
Web bridge for the docstring generation visualizers.

This module provides adapters that connect the existing terminal-based
visualizers to the web interface. When enabled, the visualizers will send
updates to the web interface in addition to their normal terminal output.
"""

import threading
import time
import functools
from typing import Dict, Any, Optional

# Singleton pattern for the web socket manager
class WebSocketManager:
    """Manages the connection to the web socket for sending visualization updates."""
    
    _instance = None
    _socket = None
    _enabled = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(WebSocketManager, cls).__new__(cls)
        return cls._instance
    
    @classmethod
    def set_socket(cls, socket):
        """Set the socket.io instance for sending updates."""
        cls._socket = socket
        cls._enabled = True
    
    @classmethod
    def is_enabled(cls):
        """Check if web visualization is enabled."""
        return cls._enabled and cls._socket is not None
    
    @classmethod
    def emit(cls, event, data):
        """Emit an event to the web interface."""
        if cls.is_enabled():
            try:
                cls._socket.emit(event, data)
            except Exception as e:
                print(f"Error sending web update: {e}")
                
    @classmethod
    def disable(cls):
        """Disable web visualization."""
        cls._enabled = False


class WebStatusAdapter:
    """Adapter for the StatusVisualizer to send updates to the web interface."""

    def __init__(self, original_visualizer):
        """
        Initialize the web status adapter.

        Args:
            original_visualizer: The original StatusVisualizer instance
        """
        self.original = original_visualizer
        self.socket_manager = WebSocketManager()

        # Store original methods to avoid recursion. StatusVisualizer only
        # defines update() and set_current_component() - the orchestrator
        # calls visualizer.update(agent, message) directly, not separate
        # set_active_agent()/set_status_message() methods (which don't
        # exist on this class).
        self._original_update = original_visualizer.update
        self._original_set_current_component = original_visualizer.set_current_component

    def update(self, active_agent, status_message=""):
        """
        Update the active agent/status and notify the web interface.

        Args:
            active_agent: Name of the currently active agent
            status_message: Current status message to display
        """
        # Call the original method directly
        result = self._original_update(active_agent, status_message)

        # Special message format for the web interface to parse. Printed
        # unconditionally (not gated on socket_manager.is_enabled()): this
        # code runs in a subprocess spawned by the web UI, which has no
        # access to the parent Flask process's socketio instance, so the
        # direct emit below never actually fires there. This print, relayed
        # over the subprocess's stdout pipe back to process_handler.py, is
        # the channel that actually crosses the process boundary.
        print(f"STATUS: Agent: {active_agent}, Message: {status_message}")

        # Direct emit only works if this process has its own socket handle
        # (e.g. tests running in-process); harmless no-op otherwise.
        if self.socket_manager.is_enabled():
            self.socket_manager.emit('status_update', {
                'status': {
                    'active_agent': active_agent,
                    'status_message': status_message,
                    'current_component': self.original._current_component,
                    'current_file': self.original._current_file
                }
            })

        return result

    def set_current_component(self, focal_component, file_path):
        """
        Set the current component being processed and send update to web interface.

        Args:
            focal_component: The component being processed
            file_path: The path to the file containing the component
        """
        # Call the original method directly
        result = self._original_set_current_component(focal_component, file_path)

        # Special message format for the web interface to parse (see note
        # in update() above about why this is unconditional).
        print(f"COMPONENT: {focal_component} in file {file_path}")

        if self.socket_manager.is_enabled():
            self.socket_manager.emit('status_update', {
                'status': {
                    'active_agent': self.original.active_agent,
                    'status_message': self.original._status_message,
                    'current_component': focal_component,
                    'current_file': file_path
                }
            })

        return result


class WebProgressAdapter:
    """Adapter for the ProgressVisualizer to send updates to the web interface."""
    
    def __init__(self, original_visualizer):
        """
        Initialize the web progress adapter.
        
        Args:
            original_visualizer: The original ProgressVisualizer instance
        """
        self.original = original_visualizer
        self.socket_manager = WebSocketManager()
        
        # Store original methods to avoid recursion
        self._original_update = original_visualizer.update
        if hasattr(original_visualizer, 'mark_complete'):
            self._original_mark_complete = original_visualizer.mark_complete
    
    def update(self, component_id=None, status="processing"):
        """
        Update the progress visualization and send update to web interface.
        
        Args:
            component_id: ID of the component being processed
            status: Status of the component
        """
        # Call the original method directly
        result = self._original_update(component_id, status)

        # Special message format for the web interface to parse (see note
        # in WebStatusAdapter.update() about why this is unconditional).
        print(f"PROGRESS: {len(self.original.processed)}/{len(self.original.sorted_order)} components processed")

        if self.socket_manager.is_enabled():
            # Get the component status from the original visualizer
            component_status = {}
            for comp_id in self.original.components:
                if comp_id in self.original.processed:
                    component_status[comp_id] = "complete"
                elif comp_id == self.original.current:
                    component_status[comp_id] = "in_progress"
                else:
                    component_status[comp_id] = "not_started"

            self.socket_manager.emit('status_update', {
                'progress': {
                    'total_components': len(self.original.sorted_order),
                    'processed_components': len(self.original.processed),
                    'current_component': self.original.current,
                    'component_status': component_status
                }
            })

        return result
    
    def mark_complete(self, component_id):
        """
        Mark a component as complete and send update to web interface.
        
        Args:
            component_id: ID of the component to mark as complete
        """
        # Check if the original visualizer has mark_complete
        if not hasattr(self, '_original_mark_complete'):
            # Fall back to update
            return self.update(component_id, "complete")
            
        # Call the original method directly
        result = self._original_mark_complete(component_id)
        
        # Update web interface
        if self.socket_manager.is_enabled():
            # Use the update method to send progress
            self.update(component_id, "complete")
        
        return result


def _patch_status_class(StatusVisualizer):
    """Patch a single StatusVisualizer class object in place."""
    if hasattr(StatusVisualizer, '_web_patched'):
        return
    StatusVisualizer._web_patched = True
    original_status_init = StatusVisualizer.__init__

    def patched_status_init(self, *args, **kwargs):
        original_status_init(self, *args, **kwargs)
        # Create adapter and store original methods
        adapter = WebStatusAdapter(self)
        # Replace methods with adapter methods - update() is what the
        # orchestrator actually calls (visualizer.update(agent, message));
        # there is no set_active_agent()/set_status_message() on this class.
        self.update = adapter.update
        self.set_current_component = adapter.set_current_component

    StatusVisualizer.__init__ = patched_status_init


def _patch_progress_class(ProgressVisualizer):
    """Patch a single ProgressVisualizer class object in place."""
    if hasattr(ProgressVisualizer, '_web_patched'):
        return
    ProgressVisualizer._web_patched = True
    original_progress_init = ProgressVisualizer.__init__

    def patched_progress_init(self, *args, **kwargs):
        original_progress_init(self, *args, **kwargs)
        # Create adapter and store original methods
        adapter = WebProgressAdapter(self)
        # Replace methods with adapter methods
        self.update = adapter.update
        if hasattr(self, 'mark_complete'):
            self.mark_complete = adapter.mark_complete

    ProgressVisualizer.__init__ = patched_progress_init


def patch_visualizers():
    """
    Patch the existing visualizer classes to add web interface support.

    This function should be called before creating any visualizer instances
    to ensure they have web support.

    The editable install exposes src/visualizer under two different import
    paths - `src.visualizer` (relative to the repo root) and a top-level
    `visualizer` package (via setup.py's package_dir mapping) - which
    resolve to two DISTINCT class objects in memory despite sharing source
    code. Callers use both paths inconsistently (e.g. Orchestrator imports
    the top-level `visualizer` package for StatusVisualizer), so patching
    only one leaves whichever class is actually instantiated un-patched.
    Both are patched here to cover either usage.
    """
    from . import StatusVisualizer as SrcStatusVisualizer, ProgressVisualizer as SrcProgressVisualizer

    _patch_status_class(SrcStatusVisualizer)
    _patch_progress_class(SrcProgressVisualizer)

    try:
        from visualizer import StatusVisualizer as TopStatusVisualizer, ProgressVisualizer as TopProgressVisualizer
        _patch_status_class(TopStatusVisualizer)
        _patch_progress_class(TopProgressVisualizer)
    except ImportError:
        pass 