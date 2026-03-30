# Spotify Stream Widget

A Python-based tool for streamers to display current Spotify track information and control playback via WebSocket for OBS Studio integration.

## Features

- Displays current Spotify track information (title, artist, album, progress)
- WebSocket server for OBS Studio integration
- Full playback control (play, pause, next, previous, volume, seek)
- Configuration file for customizing appearance and behavior
- Spotify authentication via web browser
- Console-based output (no GUI)

## Requirements

- Python 3.7+
- Spotify Developer Account
- Required Python packages (see requirements.txt)

## Setup

1. Create a Spotify Developer Account at https://developer.spotify.com/
2. Create a new app and note the Client ID and Client Secret
3. Add `http://localhost:8080/callback` as a Redirect URI in your Spotify app settings
4. Set environment variables:
   ```
   SPOTIPY_CLIENT_ID=your_client_id_here
   SPOTIPY_CLIENT_SECRET=your_client_secret_here
   ```

## Installation

```bash
pip install spotipy websockets
```

## Usage

Run the widget:
```bash
python spotify_stream_widget.py
```

The widget will open your browser for Spotify authentication. After authentication, it will start displaying track information and listen for WebSocket commands on port 8765.

## WebSocket Commands

The widget listens for commands on `ws://localhost:8765`:

- `{"command": "play"}` - Start playback
- `{"command": "pause"}` - Pause playback
- `{"command": "next"}` - Skip to next track
- `{"command": "previous"}` - Go to previous track
- `{"command": "volume", "value": 50}` - Set volume (0-100)
- `{"command": "seek", "value": 30000}` - Seek to position in milliseconds
- `{"command": "status"}` - Get current track status

## Configuration

The widget uses `config.json` for settings:
- `dark_mode`: Enable/disable dark mode
- `size`: Size of the display (small, normal, big)
- `progress_bar_style`: Style of progress bar (blocks, continuous, marquee, off)
- `progress_color`: Color of progress bar
- `export_mode`: Enable/disable exporting track details
- `api_calls`: Counter of API calls
- `local_dir`: Directory for local songs
- `window_color`: Color of the window

## OBS Studio Integration

1. Add a "Browser Source" to your OBS scene
2. Set the URL to `ws://localhost:8765` (or use a WebSocket plugin)
3. Configure the browser source to display the widget output
4. Use the WebSocket commands to control playback from OBS

## License

MIT License