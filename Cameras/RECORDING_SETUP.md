# Camera Recording Setup Guide

## Installation Requirements

### 1. Install FFmpeg

**On Ubuntu/Debian (Pi or PC):**
```bash
sudo apt update
sudo apt install ffmpeg -y
```

**On macOS:**
```bash
brew install ffmpeg
```

**On Windows:**
Download from https://ffmpeg.org/download.html or use:
```bash
choco install ffmpeg
```

### 2. Verify FFmpeg Installation
```bash
ffmpeg -version
```

## How Recording Works

### Local Recording (Raspberry Pi)
- Recordings are saved to `~/GSWebUI/recordings/`
- Videos are encoded to H.264 MP4 format
- You can then download recordings from the web UI

### Network Recording (PC)
To save recordings to a network-connected PC:

#### Option A: Network Share (SMB/CIFS)
1. **On the PC:** Set up a shared folder (e.g., `C:\Recordings` or `/home/user/recordings`)
   - Windows: Share permissions with Everyone (Read/Write)
   - Linux: Set proper permissions: `chmod 777 /home/user/recordings`

2. **On the Raspberry Pi:** Mount the network share
   ```bash
   # Install SMB client
   sudo apt install cifs-utils
   
   # Create mount point
   mkdir -p ~/network_recordings
   
   # Mount the share (replace with your PC's IP and path)
   sudo mount -t cifs //192.168.1.100/Recordings ~/network_recordings -o username=user,password=pass
   ```

3. **Update the Python code to use the mount point:**
   Edit `main.py` and change:
   ```python
   RECORDINGS_DIR = os.path.expanduser('~/network_recordings')
   ```

#### Option B: SSH/SCP Upload
Configure automatic upload after recording (add to `main.py`):
```python
def upload_recording_to_pc(filepath, pc_user, pc_ip, pc_path):
    """Upload recording to PC via SCP"""
    import paramiko
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(pc_ip, username=pc_user)
    sftp = ssh.open_sftp()
    sftp.put(filepath, f'{pc_path}/{os.path.basename(filepath)}')
    sftp.close()
    ssh.close()
```

#### Option C: NFS Mount
1. **On PC (Linux):**
   ```bash
   # Export directory via NFS
   sudo apt install nfs-kernel-server
   echo '/home/user/recordings *(rw,sync,no_subtree_check)' | sudo tee -a /etc/exports
   sudo exportfs -a
   ```

2. **On Raspberry Pi:**
   ```bash
   sudo apt install nfs-common
   mkdir -p ~/nfs_recordings
   sudo mount -t nfs 192.168.1.100:/home/user/recordings ~/nfs_recordings
   ```

## Recording Settings

### Adjust Recording Quality

Edit `main.py` and modify the FFmpeg commands:

```python
# Fast encoding (lower quality, smaller files)
'-crf', '28'  # Change to higher value (0-51, lower = better quality)

# Slower encoding (higher quality)
'-preset', 'slow'  # Options: ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow
```

### Change Output Format

Add more codec options:
```python
# For H.265 (HEVC) - smaller files but slower
'-c:v', 'libx265'

# For VP9 - for web playback
'-c:v', 'libvpx-vp9'
```

## Usage

1. **Start Recording:**
   - Click the "🔴 Record" button on any camera
   - Button changes to "⏹️ Stop Recording" with orange animation

2. **Stop Recording:**
   - Click the "⏹️ Stop Recording" button
   - File is saved to the recordings directory

3. **Manage Recordings:**
   - View all recordings in the "📼 Recordings" section
   - Download videos to your PC
   - Delete recordings to free up space

## Troubleshooting

### FFmpeg not found
```bash
# Check PATH
which ffmpeg

# If not found, install it
sudo apt install ffmpeg -y
```

### Permission denied when saving
```bash
# Fix recording directory permissions
chmod 755 ~/GSWebUI/recordings
```

### Network share not accessible
```bash
# Test connection to network share
ping 192.168.1.100
smbclient -L //192.168.1.100 -U username
```

### Recording process hangs
- Kill orphaned FFmpeg processes:
  ```bash
  pkill -f ffmpeg
  ```

## Storage Considerations

- **MJPEG at 30fps, 1080p, 30min:** ~200-400 MB (depends on quality setting)
- **Plan storage:** Pi SD card + network storage recommended
- **Auto-cleanup:** Add cron job to delete old recordings:
  ```bash
  find ~/GSWebUI/recordings -mtime +7 -delete  # Delete files older than 7 days
  ```

## Performance Notes

- Raspberry Pi 4 can handle 1-2 simultaneous MJPEG recordings
- For 3+ cameras, consider dedicated PC with faster CPU
- Use `-preset veryfast` on Pi to reduce CPU load
