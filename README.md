# ADI Onboarding Checklist - Flask Application

A Flask-based web application for managing user onboarding checklists at Analog Devices, Inc. This application includes LDAP authentication and follows the ADI-Harmonic design system.

## Features

- **LDAP Authentication**: Secure login using LDAP credentials
- **User Onboarding Checks**: Automated verification of:
  - LDAP user existence
  - VDI availability
  - Nobackup area
  - Home directory
  - DG profile (for contractors)
- **Email Notifications**: Automatic onboarding emails with instructions
- **MongoDB Integration**: Logging of onboarding activities
- **ADI-Harmonic Design**: Professional UI following ADI design standards

## Prerequisites

- Python 3.8 or higher
- MongoDB running on localhost:27017
- Access to ADI LDAP servers
- Access to mail.analog.com SMTP server
- SSH access to adbldgtest-lx02.adbldesign.analog.com (for contractor checks)
- `/opt/onboardingdoc/` directory for attachment documents

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd onboarding_checklist
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Ensure MongoDB is running:
```bash
systemctl status mongod
```

4. Create the onboarding documents directory (if not exists):
```bash
sudo mkdir -p /opt/onboardingdoc/
```

## Configuration

The application uses the following LDAP configuration:
- **LDAP Server**: `ldap://adbihldap.adbidesign.analog.com`
- **Base DN**: `ou=Users,ou=global,dc=analog,dc=com`

These settings can be modified in `app.py` if needed.

## Running the Application

### Development Mode

```bash
python app.py
```

The application will be available at `http://localhost:5000`

### Production Mode

For production deployment, use a WSGI server like Gunicorn:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

Or use the systemd service file:

```bash
sudo cp onboarding_checklist.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable onboarding_checklist
sudo systemctl start onboarding_checklist
```

## Usage

1. Navigate to the application URL
2. Log in with your LDAP credentials
3. Enter the user ID to check
4. Optionally enter RITM/INC number and CC emails
5. Select an onboarding document to attach
6. Click "Run Checks"
7. Review the results and verify all checks pass
8. If successful, an email will be sent automatically

## File Structure

```
onboarding_checklist/
├── app.py                      # Main Flask application
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── templates/
│   ├── login.html             # Login page
│   └── home.html              # Main onboarding page
└── static/
    └── css/
        └── style.css          # ADI-Harmonic design styles
```

## Security Notes

- Session lifetime is set to 8 hours
- Passwords are never stored or logged
- LDAP authentication is required for all protected routes
- Session secret key is generated randomly on startup

## Migration from Streamlit

This Flask application replaces the previous Streamlit version with the following improvements:
- Proper LDAP authentication instead of open access
- Better session management
- More professional UI with ADI branding
- RESTful API design
- Better error handling
- Mobile-responsive design

## Troubleshooting

### LDAP Connection Issues
- Verify the LDAP server is accessible: `ping adbihldap.adbidesign.analog.com`
- Check firewall rules allow LDAP traffic (port 389)

### MongoDB Connection Issues
- Ensure MongoDB is running: `systemctl status mongod`
- Check MongoDB logs: `tail -f /var/log/mongodb/mongod.log`

### Email Sending Issues
- Verify SMTP server is accessible: `telnet mail.analog.com 25`
- Check email logs in application output

### Permission Issues
- Ensure the application has read access to `/opt/onboardingdoc/`
- Verify SSH keys are configured for adbldgtest-lx02 access

## Support

For issues or questions, contact:
- EIS Helpdesk: eis-helpdesk@analog.com

## License

Copyright © 2024 Analog Devices, Inc. All Rights Reserved.
