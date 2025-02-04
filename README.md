`openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout server.key -out server.crt -config openssl.cnf`

`python3.10 client.py --path /Users/su/Downloads/esttdst`

`systemctl status backup_server.service`

`nano /etc/systemd/system/backup_server.service`

`icloud --username=your_mail@icloud.com`

`systemctl daemon-reload`

`(crontab -l 2>/dev/null; echo "*/10 * * * * python3 /root/client.py --path /root/...") | crontab -`

```
[Unit]
Description=Backup Server
After=network.target

[Service]
ExecStart=/usr/bin/python3 /root/icloud_backups/server.py
WorkingDirectory=/root/icloud_backups
Restart=always
User=root
Group=root
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```
