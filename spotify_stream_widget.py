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
from PIL import Image
import requests
from io import BytesIO

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SpotifyStreamWidget:
    def __init__(self):
        self.config_file = "config.json"
        self.config = self.load_config()
        self.spotify = None
        self.websocket_server_task = None
        self.current_track_id = None
        self.is_running = False
        self.auth_manager = None
        
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
            self.auth_manager = SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scope=scope,
                show_dialog=True
            )
            
            # Get access token - using as_dict=False to avoid the deprecation warning
            token_info = self.auth_manager.get_access_token(as_dict=False)
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
    
    def refresh_spotify_token(self):
        """Refresh Spotify access token"""
        try:
            if self.auth_manager:
                token_info = self.auth_manager.refresh_access_token()
                if token_info:
                    self.spotify = spotipy.Spotify(auth=token_info['access_token'])
                    logger.info("Successfully refreshed Spotify token")
                    return True
                else:
                    logger.error("Failed to refresh Spotify token")
                    return False
            else:
                logger.error("No auth manager available for token refresh")
                return False
        except Exception as e:
            logger.error(f"Error refreshing Spotify token: {e}")
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
                    'album_art_url': track['album']['images'][0]['url'] if track['album']['images'] else None,
                    'track_id': track['id']
                }
            else:
                return None
                
        except Exception as e:
            # Check if token is expired and try to refresh
            if "401" in str(e) or "Unauthorized" in str(e):
                logger.info("Token expired, attempting to refresh...")
                if self.refresh_spotify_token():
                    # Retry getting the track after token refresh
                    return self.get_current_track()
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
    
    def export_track_data(self, track):
        """Export track information to files"""
        try:
            if not self.config.get('export_mode', False):
                return
                
            # Create export directory if it doesn't exist
            export_dir = "exported-details"
            if not os.path.exists(export_dir):
                os.makedirs(export_dir)
            
            # Export track name
            with open(os.path.join(export_dir, "track.txt"), "w") as f:
                f.write(track['name'])
            
            # Export album name
            with open(os.path.join(export_dir, "album.txt"), "w") as f:
                f.write(track['album'])
            
            # Export artists
            artists = ", ".join(track['artists'])
            with open(os.path.join(export_dir, "artists.txt"), "w") as f:
                f.write(artists)
            
            # Export album cover image
            if track['album_art_url']:
                try:
                    response = requests.get(track['album_art_url'])
                    if response.status_code == 200:
                        image = Image.open(BytesIO(response.content))
                        image.save(os.path.join(export_dir, "albumCover.png"))
                except Exception as e:
                    logger.error(f"Error downloading album cover: {e}")
            
            logger.info("Track data exported successfully")
            
        except Exception as e:
            logger.error(f"Error exporting track data: {e}")
    
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
            # Check if token is expired and try to refresh
            if "401" in str(e) or "Unauthorized" in str(e):
                logger.info("Token expired, attempting to refresh...")
                if self.refresh_spotify_token():
                    # Retry the command after token refresh
                    self.control_playback(command, value)
                else:
                    logger.error(f"Error controlling playback after token refresh: {e}")
            else:
                logger.error(f"Error controlling playback: {e}")
    
    async def handle_websocket_message(self, websocket, path):
        """Handle incoming WebSocket messages"""
        try:
            async for message in websocket:
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
    
    async def run_websocket_server(self):
        """Run WebSocket server"""
        try:
            server = await websockets.serve(self.handle_websocket_message, "localhost", 8765)
            logger.info("WebSocket server started on ws://localhost:8765")
            await server.wait_closed()
        except Exception as e:
            logger.error(f"WebSocket server error: {e}")
    
    def start_websocket_server(self):
        """Start WebSocket server in a separate thread"""
        try:
            # Create a new event loop for the thread
            def run_server():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self.run_websocket_server())
                finally:
                    loop.close()
            
            websocket_thread = threading.Thread(target=run_server)
            websocket_thread.daemon = True
            websocket_thread.start()
            logger.info("WebSocket server thread started")
            
        except Exception as e:
            logger.error(f"Error starting WebSocket server thread: {e}")
    
    def start(self):
        """Start the Spotify Stream Widget with song change detection"""
        logger.info("Starting Spotify Stream Widget...")
        
        # Authenticate with Spotify
        if not self.authenticate_spotify():
            logger.error("Failed to authenticate with Spotify")
            return
            
        # Start WebSocket server
        self.start_websocket_server()
        
        self.is_running = True
        logger.info("Widget is running. Use WebSocket commands to control playback.")
        logger.info("Available commands: play, pause, next, previous, volume, seek, status")
        
        try:
            while self.is_running:
                # Get current track
                track = self.get_current_track()
                
                # Check if track has changed
                if track:
                    if self.current_track_id != track['track_id']:
                        logger.info(f"Song changed to: {track['name']} by {', '.join(track['artists'])}")
                        self.current_track_id = track['track_id']
                        # Display new track info
                        self.display_track_info(track)
                        # Export track data
                        self.export_track_data(track)
                    else:
                        # Only update progress if same song
                        self.display_track_info(track)
                else:
                    # No track playing, display empty info
                    self.display_track_info(None)
                
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