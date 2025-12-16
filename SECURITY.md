# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.4.x   | :white_check_mark: |
| < 1.4   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly:

1. **Do not** open a public issue
2. Send a private message to the maintainer via GitHub
3. Include details about the vulnerability and steps to reproduce

We will respond within 48 hours and work to address the issue promptly.

## Security Considerations

This integration communicates with Beurer lamps via Bluetooth Low Energy (BLE). Please be aware:

- BLE communication is local only (no cloud services)
- MAC addresses are stored in Home Assistant's configuration
- Diagnostic exports redact sensitive information (MAC addresses)
- No authentication data is transmitted or stored

## Best Practices

- Keep Home Assistant and this integration up to date
- Use a dedicated Bluetooth adapter for IoT devices if possible
- Monitor your Home Assistant logs for unusual activity
