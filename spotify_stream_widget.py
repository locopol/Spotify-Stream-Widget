#!/usr/bin/env python3
"""
Spotify Stream Widget for Streamers
This is a Python implementation of the Spotify Stream Widget that shows current track information
and allows control via WebSocket connections for OBS Studio integration.
"""

import json
import os
import sys
import time
import threading
import webbrowser
import asyncio
import websockets
from datetime import datetime
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SpotifyStreamWidget:
    def __init__(self):
        self.config_file = "config.json"
        self.config = self.load_config()
        self.spotify = None
        self.websocket_server = None
        self.current_track = None
        self.is_running = False
        
    def load_config(self):
        """Load configuration from JSON file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            else:
                # Default configuration
                default_config = {
                    "dark_mode": True,
                    "size": "normal",
                    "progress_bar_style": "blocks",
                    "progress_color": "green",
                    "export_mode": False,
                    "api_calls": 0,
                    "local_dir": "",
                    "window_color": "green"
                }
                self.save_config(default_config)
                return default_config
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {}
    
    def save_config(self, config):
        """Save configuration to JSON file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    def authenticate_spotify(self):
        """Authenticate with Spotify using OAuth"""
        try:
            # Spotify API credentials - these should be set as environment variables
            client_id = os.getenv('SPOTIPY_CLIENT_ID')
            client_secret = os.getenv('SPOTIPY_CLIENT_SECRET')
            redirect_uri = os.getenv('SPOTIPY_REDIRECT_URI', 'http://localhost:8080/callback')
            
            if not client_id or not client_secret:
                logger.error("Spotify client credentials not found in environment variables")
                return False
            
            # Setup Spotify authentication
            scope = 'user-read-playback-state user-modify-playback-state'
            auth_manager = SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scope=scope,
                show_dialog=True
            )
            
            # Get access token - using as_dict=False to avoid the deprecation warning
            token_info = auth_manager.get_access_token(as_dict=False)
            if token_info:
                self.spotify = spotipy.Spotify(auth=token_info)
                logger.info("Successfully authenticated with Spotify")
                return True
            else:
                logger.error("Failed to get access token")
                return False
                
        except Exception as e:
            logger.error(f"Spotify authentication error: {e}")
            return False
    
    def get_current_track(self):
        """Get current playing track from Spotify"""
        try:
            if not self.spotify:
                return None
                
            playback = self.spotify.current_playback()
            if playback and playback['is_playing']:
                track = playback['item']
                self.config['api_calls'] += 1
                self.save_config(self.config)
                return {
                    'name': track['name'],
                    'artists': [artist['name'] for artist in track['artists']],
                    'album': track['album']['name'],
                    'duration_ms': track['duration_ms'],
                    'progress_ms': playback['progress_ms'],
                    'is_playing': True,
                    'album_art_url': track['album']['images'][0]['url'] if track['album']['images'] else None
                }
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error getting current track: {e}")
            return None
    
    def format_time(self, ms):
        """Format milliseconds to MM:SS"""
        seconds = int(ms / 1000)
        minutes = int(seconds / 60)
        seconds = seconds % 60
        return f"{minutes}:{seconds:02d}"
    
    def display_track_info(self, track):
        """Display track information in console"""
        if not track:
            print("No track currently playing")
            return
            
        artists = ", ".join(track['artists'])
        print(f"\n{'='*50}")
        print(f"Track: {track['name']}")
        print(f"Artists: {artists}")
        print(f"Album: {track['album']}")
        print(f"Progress: {self.format_time(track['progress_ms'])}/{self.format_time(track['duration_ms'])}")
        print(f"Status: {'Playing' if track['is_playing'] else 'Paused'}")
        print(f"{'='*50}")
    
    def control_playback(self, command, value=None):
        """Control Spotify playback via WebSocket commands"""
        try:
            if not self.spotify:
                logger.warning("Not authenticated with Spotify")
                return
                
            if command == "play":
                self.spotify.start_playback()
                logger.info("Playback started")
            elif command == "pause":
                self.spotify.pause_playback()
                logger.info("Playback paused")
            elif command == "next":
                self.spotify.next_track()
                logger.info("Next track")
            elif command == "previous":
                self.spotify.previous_track()
                logger.info("Previous track")
            elif command == "volume":
                if value is not None:
                    self.spotify.volume(value)
                    logger.info(f"Volume set to {value}%")
            elif command == "seek":
                if value is not None:
                    self.spotify.seek_track(value)
                    logger.info(f"Seeked to {value}ms")
                    
        except Exception as e:
            logger.error(f"Error controlling playback: {e}")
    
    async def handle_websocket_message(self, websocket, message):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)
            command = data.get('command')
            value = data.get('value')
            
            logger.info(f"Received command: {command}")
            
            if command in ['play', 'pause', 'next', 'previous']:
                self.control_playback(command)
            elif command == 'volume' and value is not None:
                self.control_playback('volume', value)
            elif command == 'seek' and value is not None:
                self.control_playback('seek', value)
            elif command == 'status':
                track = self.get_current_track()
                await websocket.send(json.dumps({
                    'type': 'status',
                    'track': track,
                    'timestamp': datetime.now().isoformat()
                }))
                
        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
    
    async def websocket_server(self):
        """Start WebSocket server for OBS integration"""
        try:
            async with websockets.serve(self.handle_websocket_message, "localhost", 8765):
                logger.info("WebSocket server started on ws://localhost:8765")
                await asyncio.Future()  # Run forever
        except Exception as e:
            logger.error(f"WebSocket server error: {e}")
    
    def start(self):
        """Start the Spotify Stream Widget"""
        logger.info("Starting Spotify Stream Widget...")
        
        # Authenticate with Spotify
        if not self.authenticate_spotify():
            logger.error("Failed to authenticate with Spotify")
            return
            
        # Start WebSocket server in a separate thread
        websocket_thread = threading.Thread(target=asyncio.run, args=(self.websocket_server(),))
        websocket_thread.daemon = True
        websocket_thread.start()
        
        self.is_running = True
        logger.info("Widget is running. Use WebSocket commands to control playback.")
        logger.info("Available commands: play, pause, next, previous, volume, seek, status")
        
        try:
            while self.is_running:
                # Get and display current track
                track = self.get_current_track()
                self.display_track_info(track)
                
                # Wait before next update
                time.sleep(5)
                
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            self.is_running = False
    
    def stop(self):
        """Stop the Spotify Stream Widget"""
        self.is_running = False
        logger.info("Widget stopped")

def main():
    """Main function"""
    widget = SpotifyStreamWidget()
    
    try:
        widget.start()
    except Exception as e:
        logger.error(f"Error in main function: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()