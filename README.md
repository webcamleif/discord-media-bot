# Discord Media Bot

A self-hosted **Discord bot** that integrates with your home media stack (Plex, Tautulli, qBittorrent, Radarr, Sonarr) and provides **status updates**, **statistics**, and **download monitoring** directly in your Discord server.

## ✨ Features

- 🎬 **Plex Streams**  
  Show currently active Plex streams in a dedicated Discord channel.

- 📊 **Plex Statistics**  
  Post daily/weekly/monthly top user and library activity reports.

- 🛠 **Plex Status Channels**  
  Keep Discord channel names updated with Plex stats (movie count, show count, user count).

- ⬇️ **qBittorrent Downloads**  
  Monitor and display active downloads in Discord.

- 🍿 **Radarr / Sonarr Posters**  
  Automatically fetch movie/show posters from Radarr and Sonarr to enrich embeds.

- 🔒 **SSL Support**  
  - Allow insecure connections (skip verification).  
  - Use a custom Root CA certificate (via WebUI config).

- 🌐 **Web Admin Interface**  
  - Configure bot settings via browser.  
  - Secure login with admin user/pass.  
  - Save & reload config without restarting the container.  
  - Restart the bot from the UI.

## 🏗 Architecture

- **Bot**: Python (FastAPI + Discord.py + qbittorrent-api)  
- **WebUI**: FastAPI (serves Admin panel)  
- **Persistence**: Stores message IDs and config in mounted volume  
- **Deployment**: Kubernetes (kustomize, ArgoCD compatible)

## ⚙️ Configuration

All bot settings are managed through the **Admin WebUI**:

1. Start the bot.  
2. Visit `http://<host>:8080/`.  
3. Create an admin account on first launch.  
4. Configure all required fields and save.

### General Settings

| Setting               | Description |
|------------------------|-------------|
| **Bot Token**         | Discord bot token from [Discord Developer Portal](https://discord.com/developers/applications). |
| **Timezone**          | Timezone string (e.g. `Europe/Stockholm`). |
| **Message ID File**   | Path to JSON file storing posted message IDs (default: `/data/message_ids.json`). |
| **CA Cert Path**      | Path to a Root CA file (if using self-signed certs). Leave empty to use system CA store. |
| **Allow insecure SSL**| Skip SSL verification. |

### Plex / Tautulli

- **Tautulli URL** & **API Key** are required for streams, statistics, and Plex status channels.  
- Plex statistics update interval is configurable.

### qBittorrent

- **Host URL**, **username**, and **password** required.  
- Supports both HTTP and HTTPS.  
- SSL verification behavior depends on General Settings.

### Radarr / Sonarr

- Optional, only needed if you want posters for embeds.  
- Provide API keys and base URLs.  

## 🔒 SSL Behavior

- ✅ If **Allow insecure SSL** is enabled → verification is disabled everywhere.  
- ✅ If **CA Cert Path** is provided → that certificate is used everywhere.  
- ✅ Otherwise → system CA trust is used.

Works consistently across:  
- qBittorrent  
- Tautulli  
- Radarr / Sonarr  

## 🚀 Deployment

### Kubernetes (with Kustomize)

Minimal Deployment (example):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: discord-media-bot
  namespace: bots
spec:
  replicas: 1
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: discord-media-bot
  template:
    metadata:
      labels:
        app: discord-media-bot
    spec:
      securityContext:
        fsGroup: 1000
      volumes:
        - name: discord-media-bot-data
          persistentVolumeClaim:
            claimName: discord-media-bot-data
        - name: mediabot-certs
          configMap:
            name: mediabot-rootca
      containers:
        - name: discord-media-bot
          image: your-registry/discord-mediabot:latest
          securityContext:
            runAsUser: 1000
            runAsGroup: 1000
          ports:
            - containerPort: 8080
          volumeMounts:
            - name: discord-media-bot-data
              mountPath: /data
            - name: mediabot-certs
              mountPath: /etc/mediabot-certs
              readOnly: true
```

Persistent storage (`/data`) keeps message IDs and config.  
Mount Root CA config map at `/etc/mediabot-certs/root_ca.crt` if needed.

### Local (Docker)

    docker run -d \
      --name=discord-media-bot \
      -p 8080:8080 \
      -v /path/to/data:/data \
      -v /path/to/root_ca.crt:/etc/mediabot-certs/root_ca.crt:ro \
      your-registry/discord-mediabot:latest

## 🔧 Development

- Requires **Python 3.12**
- Install dependencies:

    pip install -r requirements.txt

- Run locally:

    uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

Admin panel will be available at [http://localhost:8080](http://localhost:8080).

## 🐞 Troubleshooting

**SSL Errors (CERTIFICATE_VERIFY_FAILED)**  
- Ensure the correct CA cert is configured in the WebUI.  
- If using a self-signed CA, mount it inside the container and point `CA Cert Path` to it.  
- You can test connectivity manually inside the container:

    python - <<'EOF'
    import requests
    print(requests.get(
        "https://your.host/api/v2/app/version",
        verify="/etc/mediabot-certs/root_ca.crt"
    ).text)
    EOF

**Bot not posting messages**  
- Ensure the bot has correct Discord permissions:
  - `Send Messages`
  - `Embed Links`
- Check logs for errors:

    docker logs -f discord-media-bot

**qBittorrent connection fails**  
- If using HTTPS with a self-signed cert, make sure:
  - You uploaded the Root CA in the WebUI.  
  - The CA file is accessible inside the container.  
- If still failing, enable **Allow insecure SSL** to confirm if it’s a cert issue.

## 📜 License

MIT — feel free to fork, hack, and improve.
