# Home Assistant Server Info

## Raspberry Pi
- **Host:** 192.168.2.99
- **User:** pi
- **Password:** raspberry

## Docker Container
- **Container Name:** homeassistant
- **Image:** ghcr.io/home-assistant/home-assistant:stable

## Volumes
- **HA Config Volume:** ha_config
- **Host Path:** /var/lib/docker/volumes/ha_config/_data
- **Container Path:** /config
- **Custom Components:** /var/lib/docker/volumes/ha_config/_data/custom_components/

## Weitere Container
- **ESPHome:** esphome (Port 6052)
- **Matter Server:** matter-server

## Deployment Commands
```bash
# Integration kopieren
sshpass -p 'raspberry' scp -r /Users/michaelbanda/Nextcloud/www/untitled1/beurer_daylight_lamps/custom_components/beurer_daylight_lamps pi@192.168.2.99:/tmp/
sshpass -p 'raspberry' ssh pi@192.168.2.99 "sudo rm -rf /var/lib/docker/volumes/ha_config/_data/custom_components/beurer_daylight_lamps && sudo cp -r /tmp/beurer_daylight_lamps /var/lib/docker/volumes/ha_config/_data/custom_components/"

# HA neustarten
sshpass -p 'raspberry' ssh pi@192.168.2.99 "docker restart homeassistant"
```

## Home Assistant API
- **URL:** http://192.168.2.99:8123
- **Token:** siehe .ha_token Datei
